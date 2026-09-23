"""Validate and benchmark the frozen ACT IR on an explicitly selected device."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov
import torch


PACKAGE_DIR = Path(__file__).parent / "policy_package_v1"
IR_PATH = PACKAGE_DIR / "act_cpu_reference.xml"
WARMUP_ITERATIONS = 10
MEASURED_ITERATIONS = 100
RTOL = 1e-4
ATOL = 1e-5

# Phase 3 is Intel-only. GPU.1 is the RTX 5060 and must not be selected here.
DEVICE_RULES = {
    "CPU": {"required": ("Intel",), "forbidden": ()},
    "GPU.0": {"required": ("Intel",), "forbidden": ("NVIDIA",)},
    "NPU": {"required": ("Intel",), "forbidden": ()},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ACT compile, correctness, and latency gate on CPU, GPU.0, or NPU."
    )
    parser.add_argument("--device", required=True, choices=tuple(DEVICE_RULES))
    parser.add_argument(
        "--inference-precision",
        choices=("default", "f32", "f16"),
        default="default",
        help="Internal inference precision hint; default leaves selection to OpenVINO.",
    )
    parser.add_argument("--warmup", type=int, default=WARMUP_ITERATIONS)
    parser.add_argument("--iterations", type=int, default=MEASURED_ITERATIONS)
    return parser.parse_args()


def percentile(values: np.ndarray, value: float) -> float:
    return float(np.percentile(values, value))


def device_slug(device: str) -> str:
    return device.lower().replace(".", "_")


def verify_device_identity(core: ov.Core, device: str) -> tuple[list[str], str]:
    available = core.available_devices
    if device not in available:
        raise RuntimeError(f"{device} is unavailable; detected: {available}")

    full_name = core.get_property(device, ov.properties.device.full_name)
    rule = DEVICE_RULES[device]
    missing = [token for token in rule["required"] if token.lower() not in full_name.lower()]
    forbidden = [token for token in rule["forbidden"] if token.lower() in full_name.lower()]
    if missing or forbidden:
        raise RuntimeError(
            f"Device identity guard rejected {device} => {full_name!r}; "
            f"missing={missing}, forbidden={forbidden}"
        )
    return available, full_name


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.warmup < 0 or args.iterations < 1:
        raise ValueError("--warmup must be >= 0 and --iterations must be >= 1")

    device = args.device
    slug = device_slug(device)
    precision_suffix = "" if args.inference_precision == "default" else f"_{args.inference_precision}"
    evidence_slug = f"{slug}{precision_suffix}"
    correctness_path = PACKAGE_DIR / f"correctness_{evidence_slug}.json"
    result_path = PACKAGE_DIR / f"benchmark_{evidence_slug}.json"
    raw_path = PACKAGE_DIR / f"benchmark_{evidence_slug}_latencies.csv"
    output_path = PACKAGE_DIR / f"reference_output_openvino_{evidence_slug}.npy"

    core = ov.Core()
    available_devices, device_full_name = verify_device_identity(core, device)

    model = core.read_model(IR_PATH)
    expected_shapes = {
        "state": "[1,6]",
        "wrist_image": "[1,3,480,640]",
    }
    actual_shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
    if actual_shapes != expected_shapes:
        raise RuntimeError(f"IR shape contract mismatch: {actual_shapes}")

    compile_config = {
        ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
    }
    if args.inference_precision != "default":
        compile_config[ov.properties.hint.inference_precision] = {
            "f32": ov.Type.f32,
            "f16": ov.Type.f16,
        }[args.inference_precision]

    compile_started = time.perf_counter_ns()
    compiled = core.compile_model(model, device, compile_config)
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    expected = torch.load(
        PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False
    )["action_chunk"].numpy()
    inputs = {
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    }
    request = compiled.create_infer_request()

    first_started = time.perf_counter_ns()
    request.infer(inputs)
    first_inference_ms = (time.perf_counter_ns() - first_started) / 1_000_000
    actual = request.get_output_tensor(0).data.copy()
    np.save(output_path, actual)

    absolute_error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
    close = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
    correctness = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "device": device,
        "device_full_name": device_full_name,
        "available_devices": available_devices,
        "requested_inference_precision": args.inference_precision,
        "comparison": f"normalized ACT action chunk: PyTorch CPU vs OpenVINO {device}",
        "input_shapes": actual_shapes,
        "output_shape": list(actual.shape),
        "output_dtype": str(actual.dtype),
        "rtol": RTOL,
        "atol": ATOL,
        "max_abs_error": float(absolute_error.max()),
        "mean_abs_error": float(absolute_error.mean()),
        "compile_ms": compile_ms,
        "first_inference_ms": first_inference_ms,
        "status": "PASS" if close else "FAIL",
    }
    write_json(correctness_path, correctness)
    print(json.dumps(correctness, indent=2, ensure_ascii=False))
    print(f"Saved correctness: {correctness_path}")

    # Correctness is a gate: do not produce performance evidence for a failing backend.
    if not close:
        print("CORRECTNESS GATE: FAIL; latency benchmark skipped", file=sys.stderr)
        raise SystemExit(2)

    for _ in range(args.warmup):
        request.infer(inputs)

    latency_ms: list[float] = []
    for _ in range(args.iterations):
        started = time.perf_counter_ns()
        request.infer(inputs)
        latency_ms.append((time.perf_counter_ns() - started) / 1_000_000)

    values = np.asarray(latency_ms, dtype=np.float64)
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "OpenVINO model inference only; excludes load, compile, preprocessing, and postprocessing",
        "device": device,
        "device_full_name": device_full_name,
        "available_devices": available_devices,
        "platform": platform.platform(),
        "openvino_version": ov.__version__,
        "ir_path": str(IR_PATH),
        "input_shapes": actual_shapes,
        "precision": "FP32 IR (compress_to_fp16=False)",
        "performance_hint": "LATENCY",
        "requested_inference_precision": args.inference_precision,
        "warmup_iterations": args.warmup,
        "measured_iterations": args.iterations,
        "compile_ms": compile_ms,
        "first_inference_ms": first_inference_ms,
        "latency_ms": {
            "min": float(values.min()),
            "mean": float(values.mean()),
            "p50": percentile(values, 50),
            "p95": percentile(values, 95),
            "p99": percentile(values, 99),
            "max": float(values.max()),
        },
        "correctness_evidence": str(correctness_path),
    }
    write_json(result_path, result)
    with raw_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["iteration", "latency_ms"])
        writer.writerows(enumerate(latency_ms, start=1))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Saved benchmark: {result_path}")
    print(f"Saved raw samples: {raw_path}")


if __name__ == "__main__":
    main()
