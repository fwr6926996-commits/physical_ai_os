"""Capture correctness-gated OpenVINO per-operation profiling evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov
import torch


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_DIR = HERE / "evidence" / "phase3_bottleneck_profiling"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
RTOL = 1e-4
ATOL = 1e-5
DEVICE_RULES = {
    "CPU": {"required": ("Intel",), "forbidden": ()},
    "GPU.0": {"required": ("Intel",), "forbidden": ("NVIDIA",)},
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile an admitted FP32 OpenVINO backend without replacing the formal latency benchmark."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", choices=tuple(DEVICE_RULES), default="CPU")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--top", type=int, default=25)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stats(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "min": float(array.min()),
        "mean": float(array.mean()),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(array.max()),
    }


def duration_ms(value: object) -> float:
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds()) * 1000.0
    return float(value) / 1_000_000.0


def verify_device(core: ov.Core, logical_device: str) -> tuple[list[str], str, str]:
    available = core.available_devices
    runtime_device = logical_device
    if logical_device == "GPU.0" and logical_device not in available and "GPU" in available:
        runtime_device = "GPU"
    if runtime_device not in available:
        raise RuntimeError(f"{logical_device} unavailable; detected={available}")
    full_name = core.get_property(runtime_device, ov.properties.device.full_name)
    rules = DEVICE_RULES[logical_device]
    if any(token.lower() not in full_name.lower() for token in rules["required"]):
        raise RuntimeError(f"Identity guard rejected {logical_device}: {full_name}")
    if any(token.lower() in full_name.lower() for token in rules["forbidden"]):
        raise RuntimeError(f"RTX isolation guard rejected {logical_device}: {full_name}")
    return available, runtime_device, full_name


def main() -> None:
    args = arguments()
    if args.warmup < 0 or args.iterations < 1 or args.top < 1:
        raise ValueError("--warmup must be >= 0; --iterations and --top must be >= 1")

    core = ov.Core()
    available, runtime_device, full_name = verify_device(core, args.device)
    model = core.read_model(IR_PATH)
    shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
    expected_shapes = {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}
    if shapes != expected_shapes:
        raise RuntimeError(f"Frozen input contract changed: {shapes}")

    config = {
        ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
        ov.properties.hint.inference_precision: ov.Type.f32,
        ov.properties.enable_profiling: True,
    }
    compile_started = time.perf_counter_ns()
    compiled = core.compile_model(model, runtime_device, config)
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0

    model_input_path = PACKAGE_DIR / "reference_model_input.pt"
    expected_output_path = PACKAGE_DIR / "reference_output_normalized.pt"
    model_input = torch.load(model_input_path, weights_only=False)
    expected = torch.load(expected_output_path, weights_only=False)["action_chunk"].numpy()
    inputs = {
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    }
    request = compiled.create_infer_request()

    request.infer(inputs)
    actual = request.get_output_tensor(0).data.copy()
    error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
    close = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
    if not close:
        raise RuntimeError(
            "Correctness gate failed before profiling: "
            f"max_abs_error={float(error.max())}, mean_abs_error={float(error.mean())}"
        )

    for _ in range(args.warmup):
        request.infer(inputs)

    wall_samples: list[float] = []
    raw_rows: list[dict[str, object]] = []
    grouped: dict[tuple[str, str, str], dict[str, object]] = defaultdict(
        lambda: {"real_time_ms": [], "cpu_time_ms": [], "statuses": defaultdict(int)}
    )
    per_iteration_profile_sum: list[float] = []

    for iteration in range(1, args.iterations + 1):
        started = time.perf_counter_ns()
        request.infer(inputs)
        wall_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        wall_samples.append(wall_ms)
        iteration_profile_sum = 0.0
        for info in request.get_profiling_info():
            real_ms = duration_ms(info.real_time)
            cpu_ms = duration_ms(info.cpu_time)
            status = str(info.status).split(".")[-1]
            key = (info.node_name, info.node_type, info.exec_type)
            grouped[key]["real_time_ms"].append(real_ms)
            grouped[key]["cpu_time_ms"].append(cpu_ms)
            grouped[key]["statuses"][status] += 1
            iteration_profile_sum += real_ms
            raw_rows.append({
                "iteration": iteration,
                "node_name": info.node_name,
                "node_type": info.node_type,
                "exec_type": info.exec_type,
                "status": status,
                "real_time_ms": real_ms,
                "cpu_time_ms": cpu_ms,
            })
        per_iteration_profile_sum.append(iteration_profile_sum)

    operations = []
    for (node_name, node_type, exec_type), values in grouped.items():
        operations.append({
            "node_name": node_name,
            "node_type": node_type,
            "exec_type": exec_type,
            "samples": len(values["real_time_ms"]),
            "status_counts": dict(values["statuses"]),
            "real_time_ms": stats(values["real_time_ms"]),
            "cpu_time_ms": stats(values["cpu_time_ms"]),
        })
    operations.sort(key=lambda item: item["real_time_ms"]["mean"], reverse=True)

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "status": "PASS",
        "scope": "OpenVINO synchronous FP32 inference with per-operation profiling enabled; preprocessing and postprocessing excluded.",
        "interpretation_limits": [
            "Profiling instrumentation changes runtime behavior and does not replace the formal latency benchmark.",
            "Per-operation times can overlap or run in parallel; their sum is not end-to-end latency.",
            "Plugin fusion may cause one reported execution node to represent multiple graph operations."
        ],
        "device": {
            "logical": args.device,
            "runtime": runtime_device,
            "full_name": full_name,
            "available_devices": available,
        },
        "environment": {
            "platform": platform.platform(),
            "openvino_version": ov.__version__,
        },
        "configuration": {
            "performance_hint": "LATENCY",
            "inference_precision": "f32",
            "profiling_enabled": True,
            "warmup_iterations": args.warmup,
            "measured_iterations": args.iterations,
        },
        "artifacts": {
            "ir_xml": str(IR_PATH),
            "ir_xml_sha256": sha256(IR_PATH),
            "ir_bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
            "reference_input_sha256": sha256(model_input_path),
            "reference_output_sha256": sha256(expected_output_path),
        },
        "correctness_gate": {
            "rtol": RTOL,
            "atol": ATOL,
            "max_abs_error": float(error.max()),
            "mean_abs_error": float(error.mean()),
            "status": "PASS",
        },
        "compile_ms": compile_ms,
        "wall_clock_latency_ms": stats(wall_samples),
        "per_iteration_sum_of_profiled_real_time_ms": stats(per_iteration_profile_sum),
        "operation_count": len(operations),
        "top_operations_by_mean_real_time": operations[: args.top],
        "raw_profile_csv": f"{args.run_id}_raw.csv",
        "operation_summary_csv": f"{args.run_id}_operations.csv",
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    result_path = EVIDENCE_DIR / f"{args.run_id}.json"
    raw_path = EVIDENCE_DIR / result["raw_profile_csv"]
    summary_path = EVIDENCE_DIR / result["operation_summary_csv"]
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    with raw_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(raw_rows[0]))
        writer.writeheader()
        writer.writerows(raw_rows)
    with summary_path.open("w", newline="", encoding="utf-8") as stream:
        fieldnames = (
            "rank", "node_name", "node_type", "exec_type", "samples",
            "mean_real_time_ms", "p50_real_time_ms", "p95_real_time_ms", "max_real_time_ms",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for rank, item in enumerate(operations, 1):
            writer.writerow({
                "rank": rank,
                "node_name": item["node_name"],
                "node_type": item["node_type"],
                "exec_type": item["exec_type"],
                "samples": item["samples"],
                "mean_real_time_ms": item["real_time_ms"]["mean"],
                "p50_real_time_ms": item["real_time_ms"]["p50"],
                "p95_real_time_ms": item["real_time_ms"]["p95"],
                "max_real_time_ms": item["real_time_ms"]["max"],
            })

    print(json.dumps(result, indent=2))
    print(f"Saved profile evidence: {result_path}")


if __name__ == "__main__":
    main()
