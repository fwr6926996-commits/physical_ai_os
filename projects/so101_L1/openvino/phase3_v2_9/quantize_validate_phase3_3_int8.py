"""First-encounter INT8 PTQ and fidelity characterization; no performance ranking."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import nncf
import numpy as np
import openvino as ov


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
FP32_IR = PACKAGE_DIR / "act_fp32.xml"
INDEX_MANIFEST = HERE / "evidence" / "phase3_3_int8" / "index_manifest.json"
WORKER = HERE / "stream_phase3_3_samples.py"
POSTPROCESS_WORKER = HERE / "postprocess_phase3_3_outputs.py"
LEROBOT_PYTHON = "/home/lucas/miniconda3/envs/lerobot/bin/python"
EXPECTED_INDEX_HASH = "869697c9b02514380a50e8252ce667a16afb99652c76b2d30967993cc5545e90"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=("mixed", "performance"), default="mixed")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict:
    difference = candidate.astype(np.float32) - reference.astype(np.float32)
    absolute = np.abs(difference)
    return {
        "mae": float(absolute.mean()),
        "rmse": float(np.sqrt(np.mean(np.square(difference)))),
        "p95_abs_error": float(np.percentile(absolute, 95)),
        "max_abs_error": float(absolute.max()),
        "per_action_dimension": [
            {
                "dimension": dimension,
                "mae": float(absolute[..., dimension].mean()),
                "p95_abs_error": float(np.percentile(absolute[..., dimension], 95)),
                "max_abs_error": float(absolute[..., dimension].max()),
            }
            for dimension in range(absolute.shape[-1])
        ],
    }


class StreamedSamples:
    """Re-iterable bridge that launches the exact LeRobot preprocessor per pass."""

    def __init__(self, subset: str, manifest: dict) -> None:
        self.subset = subset
        self.selected = manifest[subset]

    def __len__(self) -> int:
        return len(self.selected)

    def __iter__(self) -> Iterator[dict[str, np.ndarray]]:
        environment = dict(os.environ)
        environment["CUDA_VISIBLE_DEVICES"] = "-1"
        environment["HF_HOME"] = "/tmp/so101_phase3_hf_cache"
        process = subprocess.Popen(
            [LEROBOT_PYTHON, str(WORKER), "--subset", self.subset],
            stdout=subprocess.PIPE,
            env=environment,
        )
        if process.stdout is None:
            raise RuntimeError("Failed to open LeRobot worker stream")
        completed = False
        try:
            for expected in self.selected:
                item = pickle.load(process.stdout)
                identity = {key: item[key] for key in ("episode_index", "frame_index", "dataset_index")}
                if identity != {key: expected[key] for key in identity}:
                    raise RuntimeError(f"Stream/index mismatch: expected={expected}, actual={identity}")
                yield {"state": item["state"], "wrist_image": item["wrist_image"]}
            completed = True
        finally:
            process.stdout.close()
            if completed:
                return_code = process.wait()
                if return_code != 0:
                    raise RuntimeError(f"LeRobot worker failed with exit code {return_code}")
            elif process.poll() is None:
                process.terminate()
                process.wait()


def main() -> None:
    args = arguments()
    manifest = json.loads(INDEX_MANIFEST.read_text(encoding="utf-8"))
    if manifest["content_sha256"] != EXPECTED_INDEX_HASH:
        raise RuntimeError("PTQ index manifest hash changed; review and freeze it again")
    if manifest["selection"] != {
        "calibration_fractions": [0.1, 0.25, 0.4, 0.6, 0.75, 0.9],
        "validation_fractions": [1 / 3, 2 / 3],
        "calibration_count": 300,
        "validation_count": 100,
        "overlap_count": 0,
    }:
        raise RuntimeError("PTQ sample policy changed")

    run_id = "int8_" + args.preset + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate_dir = PACKAGE_DIR / "int8_candidates" / run_id
    evidence_dir = HERE / "evidence" / "phase3_3_int8" / run_id
    candidate_dir.mkdir(parents=True, exist_ok=False)
    evidence_dir.mkdir(parents=True, exist_ok=False)
    int8_ir = candidate_dir / f"act_int8_{args.preset}.xml"
    fp32_hash_before = {"xml": sha256(FP32_IR), "bin": sha256(FP32_IR.with_suffix(".bin"))}
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        core = ov.Core()
        fp32_model = core.read_model(FP32_IR)
        calibration_source = StreamedSamples("calibration", manifest)
        calibration_dataset = nncf.Dataset(calibration_source)
        quantize_started = time.perf_counter_ns()
        int8_model = nncf.quantize(
            fp32_model,
            calibration_dataset,
            preset={
                "mixed": nncf.QuantizationPreset.MIXED,
                "performance": nncf.QuantizationPreset.PERFORMANCE,
            }[args.preset],
            target_device=nncf.TargetDevice.ANY,
            subset_size=300,
            model_type=nncf.ModelType.TRANSFORMER,
        )
        quantize_ms = (time.perf_counter_ns() - quantize_started) / 1_000_000
        ov.save_model(int8_model, int8_ir, compress_to_fp16=False)

        compile_config = {
            ov.properties.hint.execution_mode: ov.properties.hint.ExecutionMode.ACCURACY,
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
        }
        fp32_compiled = core.compile_model(core.read_model(FP32_IR), "CPU", compile_config)
        int8_compiled = core.compile_model(core.read_model(int8_ir), "CPU", compile_config)
        fp32_request = fp32_compiled.create_infer_request()
        int8_request = int8_compiled.create_infer_request()

        fp32_outputs = []
        int8_outputs = []
        validation_started = time.perf_counter_ns()
        for inputs in StreamedSamples("validation", manifest):
            fp32_request.infer(inputs)
            int8_request.infer(inputs)
            fp32_outputs.append(fp32_request.get_output_tensor(0).data.copy())
            int8_outputs.append(int8_request.get_output_tensor(0).data.copy())
        validation_ms = (time.perf_counter_ns() - validation_started) / 1_000_000
        fp32_values = np.concatenate(fp32_outputs, axis=0)
        int8_values = np.concatenate(int8_outputs, axis=0)
        if fp32_values.shape != (100, 100, 6) or int8_values.shape != fp32_values.shape:
            raise RuntimeError(f"Validation output contract changed: fp32={fp32_values.shape}, int8={int8_values.shape}")
        if not np.isfinite(fp32_values).all() or not np.isfinite(int8_values).all():
            raise RuntimeError("Validation output contains NaN or infinity")

        normalized_outputs = candidate_dir / "validation_outputs_normalized.npz"
        np.savez_compressed(normalized_outputs, fp32=fp32_values, int8=int8_values)
        postprocessed_outputs = candidate_dir / "validation_outputs_postprocessed.npz"
        post_env = dict(os.environ)
        post_env["CUDA_VISIBLE_DEVICES"] = "-1"
        post_env["HF_HOME"] = "/tmp/so101_phase3_hf_cache"
        subprocess.run([
            LEROBOT_PYTHON, str(POSTPROCESS_WORKER),
            "--input", str(normalized_outputs), "--output", str(postprocessed_outputs),
        ], check=True, env=post_env)
        postprocessed = np.load(postprocessed_outputs)

        fp32_hash_after = {"xml": sha256(FP32_IR), "bin": sha256(FP32_IR.with_suffix(".bin"))}
        if fp32_hash_after != fp32_hash_before:
            raise RuntimeError("Frozen FP32 artifact changed during PTQ")
        strict_rtol, strict_atol = 1e-4, 1e-5
        report = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "CHARACTERIZATION_COMPLETE_NO_ADMISSION_DECISION",
            "started_at_utc": started_at,
            "python": platform.python_version(),
            "openvino": ov.__version__,
            "nncf": nncf.__version__,
            "configuration": {
                "preset": args.preset,
                "target_device": "ANY",
                "model_type": "TRANSFORMER",
                "subset_size": 300,
                "compress_remaining_fp_weights_to_fp16": False,
                "validation_device": "CPU",
                "validation_execution_mode": "ACCURACY",
                "performance_ranking_performed": False,
            },
            "index_manifest": {"path": str(INDEX_MANIFEST), "content_sha256": manifest["content_sha256"]},
            "timing_ms_not_benchmark_scores": {"quantization": quantize_ms, "paired_validation": validation_ms},
            "artifact_bytes": {
                "fp32_xml_plus_bin": FP32_IR.stat().st_size + FP32_IR.with_suffix(".bin").stat().st_size,
                "int8_xml_plus_bin": int8_ir.stat().st_size + int8_ir.with_suffix(".bin").stat().st_size,
            },
            "artifact_sha256": {
                "fp32": fp32_hash_after,
                "int8": {"xml": sha256(int8_ir), "bin": sha256(int8_ir.with_suffix(".bin"))},
            },
            "strict_reference_gate_for_information": {
                "rtol": strict_rtol,
                "atol": strict_atol,
                "pass": bool(np.allclose(int8_values, fp32_values, rtol=strict_rtol, atol=strict_atol)),
            },
            "normalized_action_chunk_error": percentile_metrics(fp32_values, int8_values),
            "postprocessed_action_chunk_error": percentile_metrics(postprocessed["fp32"], postprocessed["int8"]),
            "decision": "Human must review the error distribution and freeze a task-relevant admission threshold before any qualified latency ranking.",
        }
        report["artifact_bytes"]["int8_to_fp32_ratio"] = (
            report["artifact_bytes"]["int8_xml_plus_bin"] / report["artifact_bytes"]["fp32_xml_plus_bin"]
        )
        report_path = evidence_dir / "int8_fidelity_report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"INT8 FEASIBILITY A: CHARACTERIZATION COMPLETE; NOT ADMITTED\nSaved: {report_path}")
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "run_id": run_id,
            "status": "FAIL",
            "started_at_utc": started_at,
            "failure_type": type(exc).__name__,
            "failure": str(exc),
            "traceback": traceback.format_exc(),
            "fp32_artifact_unchanged": {
                "before": fp32_hash_before,
                "after": {"xml": sha256(FP32_IR), "bin": sha256(FP32_IR.with_suffix(".bin"))},
            },
        }
        failure_path = evidence_dir / "failure.json"
        failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2))
        raise SystemExit(f"INT8 FEASIBILITY A: FAIL; evidence={failure_path}") from exc


if __name__ == "__main__":
    main()
