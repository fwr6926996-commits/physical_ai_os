"""Correctness-gated OpenVINO device benchmark for the V2.9 ACT package."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov
import psutil
import torch


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_DIR = HERE / "evidence" / "phase3_2_measurements"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
RTOL = 1e-4
ATOL = 1e-5
DEVICE_RULES = {
    "CPU": {"required": ("Intel",), "forbidden": ()},
    "GPU.0": {"required": ("Intel",), "forbidden": ("NVIDIA",)},
    "NPU": {"required": ("Intel",), "forbidden": ()},
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", required=True, choices=tuple(DEVICE_RULES))
    parser.add_argument("--inference-precision", choices=("default", "f32", "f16"), default="default")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    return parser.parse_args()


def stats(samples: list[float]) -> dict[str, float]:
    values = np.asarray(samples, dtype=np.float64)
    return {
        "min": float(values.min()), "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)), "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)), "max": float(values.max()),
    }


def temperature_snapshot() -> dict[str, list[dict]]:
    result = {}
    for group, entries in psutil.sensors_temperatures(fahrenheit=False).items():
        result[group] = [{"label": item.label, "current_c": item.current} for item in entries]
    return result


def verify_device(core: ov.Core, device: str) -> tuple[list[str], str, str]:
    available = core.available_devices
    runtime_device = device
    # Hiding the NVIDIA CUDA device can collapse OpenVINO's only remaining
    # Intel GPU name from GPU.0 to GPU. Preserve GPU.0 as the hardware-truth
    # logical name while recording the exact runtime string used.
    if device == "GPU.0" and device not in available and "GPU" in available:
        runtime_device = "GPU"
    if runtime_device not in available:
        raise RuntimeError(f"{device} unavailable; detected={available}")
    full_name = core.get_property(runtime_device, ov.properties.device.full_name)
    rules = DEVICE_RULES[device]
    if any(token.lower() not in full_name.lower() for token in rules["required"]):
        raise RuntimeError(f"Identity guard rejected {device}: {full_name}")
    if any(token.lower() in full_name.lower() for token in rules["forbidden"]):
        raise RuntimeError(f"RTX isolation guard rejected {device}: {full_name}")
    return available, runtime_device, full_name


def main() -> None:
    args = arguments()
    if args.warmup < 0 or args.iterations < 1:
        raise ValueError("--warmup must be >= 0 and --iterations must be >= 1")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    core = ov.Core()
    available, runtime_device, full_name = verify_device(core, args.device)
    model = core.read_model(IR_PATH)
    shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
    if shapes != {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}:
        raise RuntimeError(f"Frozen input contract changed: {shapes}")

    config = {ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY}
    if args.inference_precision != "default":
        config[ov.properties.hint.inference_precision] = {"f32": ov.Type.f32, "f16": ov.Type.f16}[args.inference_precision]
    compile_started = time.perf_counter_ns()
    try:
        compiled = core.compile_model(model, runtime_device, config)
    except Exception as exc:
        failure = {
            "schema_version": 1,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": args.run_id,
            "status": "FAIL",
            "failure_stage": "compile",
            "logical_device": args.device,
            "runtime_device": runtime_device,
            "device_full_name": full_name,
            "available_devices": available,
            "requested_inference_precision": args.inference_precision,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }
        failure_path = EVIDENCE_DIR / f"{args.run_id}_compile_failure.json"
        failure_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2))
        raise SystemExit(f"COMPILE GATE: FAIL; evidence={failure_path}") from exc
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    expected = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"].numpy()
    inputs = {"state": model_input["observation.state"].numpy(), "wrist_image": model_input["observation.images.wrist"].numpy()}
    request = compiled.create_infer_request()
    first_started = time.perf_counter_ns()
    request.infer(inputs)
    first_ms = (time.perf_counter_ns() - first_started) / 1_000_000
    actual = request.get_output_tensor(0).data.copy()
    error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
    close = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))

    base = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "device": args.device,
        "runtime_device": runtime_device,
        "device_full_name": full_name,
        "available_devices": available,
        "openvino_version": ov.__version__,
        "platform": platform.platform(),
        "requested_inference_precision": args.inference_precision,
        "compile_ms": compile_ms,
        "first_inference_ms": first_ms,
        "correctness": {
            "rtol": RTOL, "atol": ATOL,
            "max_abs_error": float(error.max()), "mean_abs_error": float(error.mean()),
            "status": "PASS" if close else "FAIL",
        },
    }
    correctness_path = EVIDENCE_DIR / f"{args.run_id}_correctness.json"
    correctness_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    if not close:
        print(json.dumps(base, indent=2))
        raise SystemExit("CORRECTNESS GATE: FAIL; performance measurement skipped")

    for _ in range(args.warmup):
        request.infer(inputs)
    process = psutil.Process()
    memory_before = psutil.virtual_memory()
    rss_before = process.memory_info().rss
    temp_before = temperature_snapshot()
    samples = []
    for _ in range(args.iterations):
        started = time.perf_counter_ns()
        request.infer(inputs)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    temp_after = temperature_snapshot()
    rss_after = process.memory_info().rss
    memory_after = psutil.virtual_memory()
    base.update({
        "status": "PASS",
        "scope": "OpenVINO synchronous model inference only; preprocessing/postprocessing excluded.",
        "warmup_iterations": args.warmup,
        "measured_iterations": args.iterations,
        "latency_ms": stats(samples),
        "resources": {
            "process_rss_bytes": {"before": rss_before, "after": rss_after, "delta": rss_after - rss_before},
            "system_available_memory_bytes": {"before": memory_before.available, "after": memory_after.available},
            "temperatures": {"before": temp_before, "after": temp_after},
        },
        "correctness_evidence": str(correctness_path),
    })
    result_path = EVIDENCE_DIR / f"{args.run_id}_inference.json"
    result_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    with (EVIDENCE_DIR / f"{args.run_id}_inference.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream); writer.writerow(["iteration", "latency_ms"]); writer.writerows(enumerate(samples, 1))
    print(json.dumps(base, indent=2))
    print(f"Saved inference evidence: {result_path}")


if __name__ == "__main__":
    main()
