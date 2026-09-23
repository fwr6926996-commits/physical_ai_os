"""Convert the V2.9 ACT ExportedProgram and capture distinct CPU deployment stages."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import openvino as ov
import torch


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_DIR = HERE / "evidence" / "phase3_1_policy_package"
EXPORTED_PROGRAM_PATH = PACKAGE_DIR / "act_tensor_wrapper.pt2"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"


def elapsed_ms(started_ns: int) -> float:
    return (time.perf_counter_ns() - started_ns) / 1_000_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if not EXPORTED_PROGRAM_PATH.is_file():
        raise FileNotFoundError(f"Run prepare_phase3_1_source.py first: {EXPORTED_PROGRAM_PATH}")

    started = time.perf_counter_ns()
    exported_program = torch.export.load(EXPORTED_PROGRAM_PATH)
    exported_program_load_ms = elapsed_ms(started)

    started = time.perf_counter_ns()
    converted_model = ov.convert_model(exported_program)
    converted_model.reshape({"state": [1, 6], "wrist_image": [1, 3, 480, 640]})
    conversion_ms = elapsed_ms(started)

    started = time.perf_counter_ns()
    ov.save_model(converted_model, IR_PATH, compress_to_fp16=False)
    ir_save_ms = elapsed_ms(started)

    core = ov.Core()
    started = time.perf_counter_ns()
    loaded_model = core.read_model(IR_PATH)
    ir_load_ms = elapsed_ms(started)

    started = time.perf_counter_ns()
    compiled = core.compile_model(
        loaded_model,
        "CPU",
        {ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY},
    )
    compile_ms = elapsed_ms(started)

    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    expected = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"].numpy()
    infer_inputs = {
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    }
    request = compiled.create_infer_request()
    started = time.perf_counter_ns()
    request.infer(infer_inputs)
    first_inference_ms = elapsed_ms(started)
    actual = request.get_output_tensor(0).data.copy()

    rtol, atol = 1e-4, 1e-5
    close = bool(np.allclose(actual, expected, rtol=rtol, atol=atol))
    absolute_error = np.abs(actual - expected)
    evidence = {
        "schema_version": 1,
        "phase": "Phase 3.1 OpenVINO conversion, load, compile and CPU correctness",
        "status": "PASS" if close else "FAIL",
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "openvino_version": ov.__version__,
        "device": "CPU",
        "precision": "FP32 IR (compress_to_fp16=False)",
        "timing_ms": {
            "exported_program_load": exported_program_load_ms,
            "conversion": conversion_ms,
            "ir_save": ir_save_ms,
            "ir_load": ir_load_ms,
            "compile": compile_ms,
            "first_inference": first_inference_ms,
        },
        "tensor_contract": {
            "state": [1, 6],
            "wrist_image": [1, 3, 480, 640],
            "normalized_action_chunk": list(actual.shape),
        },
        "correctness": {
            "comparison": "frozen PyTorch CPU vs OpenVINO CPU normalized ACT action chunk",
            "rtol": rtol,
            "atol": atol,
            "max_abs_error": float(absolute_error.max()),
            "mean_abs_error": float(absolute_error.mean()),
        },
        "ir": {
            "xml": str(IR_PATH),
            "xml_sha256": sha256(IR_PATH),
            "bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
        },
    }
    evidence_path = EVIDENCE_DIR / "conversion_compile_load_cpu.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(f"Saved evidence: {evidence_path}")
    if not close:
        raise SystemExit("PHASE 3.1 CPU CORRECTNESS GATE: FAIL")
    print("PHASE 3.1 CPU CORRECTNESS GATE: PASS")


if __name__ == "__main__":
    main()
