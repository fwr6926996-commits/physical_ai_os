"""Run a time-bounded, correctness-gated OpenVINO stability test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
import traceback
from array import array
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import openvino as ov
import psutil
import torch


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_ROOT = HERE / "evidence" / "phase3_stability"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
RTOL = 1e-4
ATOL = 1e-5
DEVICE_RULES = {
    "CPU": {"required": ("Intel",), "forbidden": ()},
    "GPU.0": {"required": ("Intel",), "forbidden": ("NVIDIA",)},
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen Phase 3 V2.9 stability design.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--device", required=True, choices=tuple(DEVICE_RULES))
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--telemetry-seconds", type=float, default=5.0)
    parser.add_argument("--window-seconds", type=float, default=60.0)
    parser.add_argument("--telemetry-mode", choices=("full", "none"), default="full")
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


def temperature_summary() -> dict[str, float | None]:
    readings = []
    package_c = None
    for entries in psutil.sensors_temperatures(fahrenheit=False).values():
        for item in entries:
            if item.current is None:
                continue
            readings.append(float(item.current))
            if item.label == "Package id 0":
                package_c = float(item.current)
    return {"package_c": package_c, "max_sensor_c": max(readings) if readings else None}


def telemetry_snapshot(elapsed_s: float, iteration: int, process: psutil.Process) -> dict[str, float | int | None]:
    memory = psutil.virtual_memory()
    temperatures = temperature_summary()
    return {
        "elapsed_s": elapsed_s,
        "iteration": iteration,
        "process_rss_bytes": process.memory_info().rss,
        "system_available_memory_bytes": memory.available,
        "package_temperature_c": temperatures["package_c"],
        "max_sensor_temperature_c": temperatures["max_sensor_c"],
    }


def latency_histogram(values: list[float]) -> dict[str, int]:
    boundaries = (20.0, 40.0, 60.0, 80.0, 100.0)
    labels = ("<20", "20-40", "40-60", "60-80", "80-100", ">=100")
    counts = {label: 0 for label in labels}
    for value in values:
        index = next((i for i, boundary in enumerate(boundaries) if value < boundary), len(boundaries))
        counts[labels[index]] += 1
    return counts


def main() -> None:
    args = arguments()
    if args.duration_minutes <= 0 or args.warmup < 0:
        raise ValueError("--duration-minutes must be > 0 and --warmup must be >= 0")
    if args.telemetry_seconds <= 0 or args.window_seconds <= 0:
        raise ValueError("telemetry and window intervals must be > 0")

    run_dir = EVIDENCE_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    core = ov.Core()
    available, runtime_device, full_name = verify_device(core, args.device)
    model = core.read_model(IR_PATH)
    shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
    if shapes != {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}:
        raise RuntimeError(f"Frozen input contract changed: {shapes}")

    compile_config = {
        ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
        ov.properties.hint.inference_precision: ov.Type.f32,
    }
    compile_started = time.perf_counter_ns()
    compiled = core.compile_model(model, runtime_device, compile_config)
    compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0

    input_path = PACKAGE_DIR / "reference_model_input.pt"
    output_path = PACKAGE_DIR / "reference_output_normalized.pt"
    model_input = torch.load(input_path, weights_only=False)
    expected = torch.load(output_path, weights_only=False)["action_chunk"].numpy()
    inputs = {
        "state": model_input["observation.state"].numpy(),
        "wrist_image": model_input["observation.images.wrist"].numpy(),
    }
    request = compiled.create_infer_request()

    request.infer(inputs)
    initial = request.get_output_tensor(0).data.copy()
    initial_error = np.abs(initial.astype(np.float32) - expected.astype(np.float32))
    if not np.isfinite(initial).all() or not np.allclose(initial, expected, rtol=RTOL, atol=ATOL):
        raise RuntimeError(
            "Initial correctness gate failed: "
            f"max_abs_error={float(initial_error.max())}, mean_abs_error={float(initial_error.mean())}"
        )
    for _ in range(args.warmup):
        request.infer(inputs)

    requested_s = args.duration_minutes * 60.0
    process = psutil.Process()
    telemetry_rows: list[dict[str, float | int | None]] = []
    latency_values = array("d")
    window_values: dict[int, array] = defaultdict(lambda: array("d"))
    correctness_failures = 0
    nonfinite_outputs = 0
    inference_exceptions = 0
    maximum_abs_error = 0.0
    interrupted = False
    failure_message = None
    failure_traceback = None
    loop_started = time.monotonic()
    next_telemetry = 0.0
    next_progress = 60.0
    iteration = 0

    latency_path = run_dir / "latencies.csv"
    telemetry_path = run_dir / "telemetry.csv"
    latency_fields = (
        "iteration", "elapsed_s", "window_index", "latency_ms",
        "finite", "correct", "max_abs_error",
    )
    try:
        with latency_path.open("w", newline="", encoding="utf-8") as latency_stream, telemetry_path.open(
            "w", newline="", encoding="utf-8"
        ) as telemetry_stream:
            latency_writer = csv.DictWriter(latency_stream, fieldnames=latency_fields)
            latency_writer.writeheader()
            telemetry_fields = (
                "elapsed_s", "iteration", "process_rss_bytes", "system_available_memory_bytes",
                "package_temperature_c", "max_sensor_temperature_c",
            )
            telemetry_writer = csv.DictWriter(telemetry_stream, fieldnames=telemetry_fields)
            telemetry_writer.writeheader()
            while True:
                elapsed_before = time.monotonic() - loop_started
                if elapsed_before >= requested_s:
                    break
                inference_started = time.perf_counter_ns()
                try:
                    request.infer(inputs)
                except Exception as exc:
                    inference_exceptions += 1
                    failure_message = f"{type(exc).__name__}: {exc}"
                    break
                latency_ms = (time.perf_counter_ns() - inference_started) / 1_000_000.0
                iteration += 1
                elapsed_s = time.monotonic() - loop_started
                actual = request.get_output_tensor(0).data.copy()
                finite = bool(np.isfinite(actual).all())
                if not finite:
                    nonfinite_outputs += 1
                    correct = False
                    max_abs_error = float("inf")
                else:
                    error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
                    max_abs_error = float(error.max())
                    maximum_abs_error = max(maximum_abs_error, max_abs_error)
                    correct = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
                if not correct:
                    correctness_failures += 1
                window_index = int(elapsed_s // args.window_seconds)
                latency_values.append(latency_ms)
                window_values[window_index].append(latency_ms)
                latency_writer.writerow({
                    "iteration": iteration,
                    "elapsed_s": elapsed_s,
                    "window_index": window_index,
                    "latency_ms": latency_ms,
                    "finite": str(finite),
                    "correct": str(correct),
                    "max_abs_error": max_abs_error,
                })
                if args.telemetry_mode == "full" and elapsed_s >= next_telemetry:
                    latency_stream.flush()
                    snapshot = telemetry_snapshot(elapsed_s, iteration, process)
                    telemetry_rows.append(snapshot)
                    telemetry_writer.writerow(snapshot)
                    telemetry_stream.flush()
                    next_telemetry += args.telemetry_seconds
                if elapsed_s >= next_progress:
                    print(
                        f"progress device={args.device} elapsed={elapsed_s / 60:.1f}min "
                        f"iterations={iteration} failures={correctness_failures + nonfinite_outputs + inference_exceptions}",
                        flush=True,
                    )
                    next_progress += 60.0
                if not finite or not correct:
                    failure_message = "Output validity or correctness gate failed during the stability run."
                    break
    except KeyboardInterrupt:
        interrupted = True
        failure_message = "Interrupted by user."
    except Exception as exc:
        failure_message = f"{type(exc).__name__}: {exc}"
        failure_traceback = traceback.format_exc()

    elapsed_s = time.monotonic() - loop_started
    if args.telemetry_mode == "full":
        final_telemetry = telemetry_snapshot(elapsed_s, iteration, process)
        telemetry_rows.append(final_telemetry)
        with telemetry_path.open("a", newline="", encoding="utf-8") as stream:
            csv.DictWriter(stream, fieldnames=tuple(final_telemetry)).writerow(final_telemetry)
    window_summaries = []
    for window_index in sorted(window_values):
        values = window_values[window_index]
        window_summaries.append({
            "window_index": window_index,
            "start_s": window_index * args.window_seconds,
            "end_s": (window_index + 1) * args.window_seconds,
            "iterations": len(values),
            "latency_ms": stats(values),
        })

    completed_duration = elapsed_s >= requested_s
    hard_gates = {
        "completed_requested_duration": completed_duration,
        "inference_exceptions": inference_exceptions,
        "nonfinite_outputs": nonfinite_outputs,
        "correctness_failures": correctness_failures,
        "process_crashes": 0,
        "interrupted": interrupted,
    }
    hard_pass = (
        completed_duration
        and inference_exceptions == 0
        and nonfinite_outputs == 0
        and correctness_failures == 0
        and not interrupted
        and bool(latency_values)
    )
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING" if hard_pass else "FAIL",
        "scope": "OpenVINO synchronous FP32 inference only; preprocessing, postprocessing, profiling and robot/system paths excluded.",
        "device": {
            "logical": args.device,
            "runtime": runtime_device,
            "full_name": full_name,
            "available_devices": available,
        },
        "environment": {"platform": platform.platform(), "openvino_version": ov.__version__},
        "configuration": {
            "performance_hint": "LATENCY",
            "inference_precision": "f32",
            "requested_duration_minutes": args.duration_minutes,
            "warmup_iterations": args.warmup,
            "telemetry_interval_seconds": args.telemetry_seconds,
            "latency_window_seconds": args.window_seconds,
            "telemetry_mode": args.telemetry_mode,
        },
        "artifacts": {
            "ir_xml_sha256": sha256(IR_PATH),
            "ir_bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
            "reference_input_sha256": sha256(input_path),
            "reference_output_sha256": sha256(output_path),
        },
        "compile_ms": compile_ms,
        "initial_correctness": {
            "rtol": RTOL,
            "atol": ATOL,
            "max_abs_error": float(initial_error.max()),
            "mean_abs_error": float(initial_error.mean()),
            "status": "PASS",
        },
        "execution": {
            "actual_duration_seconds": elapsed_s,
            "iterations": iteration,
            "maximum_abs_error": maximum_abs_error,
            "hard_gates": hard_gates,
            "failure_message": failure_message,
            "failure_traceback": failure_traceback,
        },
        "latency_ms": stats(latency_values) if latency_values else None,
        "latency_histogram_ms": latency_histogram(latency_values) if latency_values else None,
        "window_summaries": window_summaries,
        "telemetry_summary": {
            "samples": len(telemetry_rows),
            "process_rss_bytes": {
                "first": telemetry_rows[0]["process_rss_bytes"],
                "last": telemetry_rows[-1]["process_rss_bytes"],
                "min": min(row["process_rss_bytes"] for row in telemetry_rows),
                "max": max(row["process_rss_bytes"] for row in telemetry_rows),
            },
            "system_available_memory_bytes": {
                "first": telemetry_rows[0]["system_available_memory_bytes"],
                "last": telemetry_rows[-1]["system_available_memory_bytes"],
            },
            "package_temperature_c": {
                "first": telemetry_rows[0]["package_temperature_c"],
                "last": telemetry_rows[-1]["package_temperature_c"],
                "max": max(
                    (row["package_temperature_c"] for row in telemetry_rows if row["package_temperature_c"] is not None),
                    default=None,
                ),
            },
            "max_sensor_temperature_c": max(
                (row["max_sensor_temperature_c"] for row in telemetry_rows if row["max_sensor_temperature_c"] is not None),
                default=None,
            ),
        } if telemetry_rows else None,
        "latency_csv": "latencies.csv",
        "telemetry_csv": "telemetry.csv",
    }

    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved stability evidence: {result_path}")
    if not hard_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
