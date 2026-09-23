"""Measure warm synchronous OpenVINO CPU inference latency for frozen ACT."""

from __future__ import annotations

import csv
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov
import torch


PACKAGE_DIR = Path(__file__).parent / "policy_package_v1"
IR_PATH = PACKAGE_DIR / "act_cpu_reference.xml"
RESULT_PATH = PACKAGE_DIR / "benchmark_cpu.json"
RAW_PATH = PACKAGE_DIR / "benchmark_cpu_latencies.csv"
DEVICE = "CPU"
WARMUP_ITERATIONS = 10
MEASURED_ITERATIONS = 100


def percentile(values: np.ndarray, value: float) -> float:
    return float(np.percentile(values, value))


def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return platform.processor()
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def main() -> None:
    core = ov.Core()
    available_devices = core.available_devices
    if DEVICE not in available_devices:
        raise RuntimeError(f"{DEVICE} is unavailable; detected: {available_devices}")

    model = core.read_model(IR_PATH)
    expected_shapes = {
        "state": "[1,6]",
        "wrist_image": "[1,3,480,640]",
    }
    actual_shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
    if actual_shapes != expected_shapes:
        raise RuntimeError(f"IR shape contract mismatch: {actual_shapes}")

    compile_started = time.perf_counter_ns()
    compiled = core.compile_model(
        model,
        DEVICE,
        {ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY},
    )
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000

    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    inputs = {
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    }
    request = compiled.create_infer_request()

    first_started = time.perf_counter_ns()
    request.infer(inputs)
    first_inference_ms = (time.perf_counter_ns() - first_started) / 1_000_000

    for _ in range(WARMUP_ITERATIONS):
        request.infer(inputs)

    latency_ms: list[float] = []
    for _ in range(MEASURED_ITERATIONS):
        started = time.perf_counter_ns()
        request.infer(inputs)
        latency_ms.append((time.perf_counter_ns() - started) / 1_000_000)

    values = np.asarray(latency_ms, dtype=np.float64)
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "OpenVINO model inference only; excludes load, compile, preprocessing, and postprocessing",
        "device": DEVICE,
        "available_devices": available_devices,
        "device_full_name": core.get_property(DEVICE, ov.properties.device.full_name),
        "cpu_model": cpu_model(),
        "platform": platform.platform(),
        "openvino_version": ov.__version__,
        "ir_path": str(IR_PATH),
        "input_shapes": actual_shapes,
        "precision": "FP32 IR (compress_to_fp16=False)",
        "performance_hint": "LATENCY",
        "warmup_iterations": WARMUP_ITERATIONS,
        "measured_iterations": MEASURED_ITERATIONS,
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
    }

    RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with RAW_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["iteration", "latency_ms"])
        writer.writerows(enumerate(latency_ms, start=1))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Saved summary: {RESULT_PATH}")
    print(f"Saved raw samples: {RAW_PATH}")


if __name__ == "__main__":
    main()
