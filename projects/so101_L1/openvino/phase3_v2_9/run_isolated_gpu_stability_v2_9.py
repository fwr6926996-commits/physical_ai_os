"""Run the Phase 3 GPU.0 stability gate with an isolated inference worker."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import platform
import queue
import time
from array import array
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_ROOT = HERE / "evidence" / "phase3_stability"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
RTOL = 1e-4
ATOL = 1e-5


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate GPU.0 FP32 stability with inference isolated from evidence collection."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--stall-seconds", type=float, default=15.0)
    parser.add_argument("--startup-seconds", type=float, default=60.0)
    parser.add_argument("--telemetry-seconds", type=float, default=5.0)
    parser.add_argument("--window-seconds", type=float, default=60.0)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stats(values: array) -> dict[str, float]:
    data = np.asarray(values, dtype=np.float64)
    return {
        "min": float(data.min()),
        "mean": float(data.mean()),
        "p50": float(np.percentile(data, 50)),
        "p95": float(np.percentile(data, 95)),
        "p99": float(np.percentile(data, 99)),
        "max": float(data.max()),
    }


def latency_histogram(values: array) -> dict[str, int]:
    boundaries = (20.0, 40.0, 60.0, 80.0, 100.0)
    labels = ("<20", "20-40", "40-60", "60-80", "80-100", ">=100")
    counts = {label: 0 for label in labels}
    for value in values:
        index = next(
            (i for i, boundary in enumerate(boundaries) if value < boundary),
            len(boundaries),
        )
        counts[labels[index]] += 1
    return counts


def temperature_snapshot() -> dict[str, float | None]:
    readings: list[float] = []
    package_c = None
    for entries in psutil.sensors_temperatures(fahrenheit=False).values():
        for item in entries:
            if item.current is None:
                continue
            value = float(item.current)
            readings.append(value)
            if item.label == "Package id 0":
                package_c = value
    return {
        "package_temperature_c": package_c,
        "max_sensor_temperature_c": max(readings) if readings else None,
    }


def parent_telemetry(elapsed_s: float, child_pid: int) -> dict[str, float | int | None]:
    memory = psutil.virtual_memory()
    try:
        child_rss = psutil.Process(child_pid).memory_info().rss
    except psutil.Error:
        child_rss = None
    temperatures = temperature_snapshot()
    return {
        "elapsed_s": elapsed_s,
        "worker_rss_bytes": child_rss,
        "supervisor_rss_bytes": psutil.Process().memory_info().rss,
        "system_available_memory_bytes": memory.available,
        **temperatures,
    }


def summarize_numeric(rows: list[dict[str, object]], key: str) -> dict[str, float] | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return {
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
    }


def inference_worker(
    messages: mp.Queue,
    duration_seconds: float,
    warmup: int,
) -> None:
    """Own OpenVINO objects and inference only; do no file or sensor I/O."""
    try:
        import openvino as ov
        import torch

        core = ov.Core()
        available = core.available_devices
        runtime_device = "GPU.0"
        if runtime_device not in available and "GPU" in available:
            runtime_device = "GPU"
        if runtime_device not in available:
            raise RuntimeError(f"GPU.0 unavailable; detected={available}")
        full_name = core.get_property(runtime_device, ov.properties.device.full_name)
        if "intel" not in full_name.lower() or "nvidia" in full_name.lower():
            raise RuntimeError(f"GPU identity guard rejected {runtime_device}: {full_name}")

        model = core.read_model(IR_PATH)
        shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
        expected_shapes = {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}
        if shapes != expected_shapes:
            raise RuntimeError(f"Frozen input contract changed: {shapes}")
        config = {
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
            ov.properties.hint.inference_precision: ov.Type.f32,
        }
        compile_started = time.perf_counter_ns()
        compiled = core.compile_model(model, runtime_device, config)
        compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0
        request = compiled.create_infer_request()

        input_path = PACKAGE_DIR / "reference_model_input.pt"
        output_path = PACKAGE_DIR / "reference_output_normalized.pt"
        model_input = torch.load(input_path, weights_only=False)
        expected = torch.load(output_path, weights_only=False)["action_chunk"].numpy()
        inputs = {
            "state": model_input["observation.state"].numpy(),
            "wrist_image": model_input["observation.images.wrist"].numpy(),
        }

        request.infer(inputs)
        initial = request.get_output_tensor(0).data.copy()
        initial_error = np.abs(initial.astype(np.float32) - expected.astype(np.float32))
        initial_finite = bool(np.isfinite(initial).all())
        initial_correct = initial_finite and bool(
            np.allclose(initial, expected, rtol=RTOL, atol=ATOL)
        )
        if not initial_correct:
            raise RuntimeError(
                "Initial GPU correctness failed: "
                f"max_abs_error={float(initial_error.max())}"
            )
        for _ in range(warmup):
            request.infer(inputs)

        versions = {
            name: {
                "build_number": value.build_number,
                "description": value.description,
            }
            for name, value in core.get_versions(runtime_device).items()
        }
        messages.put({
            "type": "ready",
            "pid": __import__("os").getpid(),
            "available_devices": available,
            "runtime_device": runtime_device,
            "device_full_name": full_name,
            "openvino_version": ov.__version__,
            "platform": platform.platform(),
            "plugin_versions": versions,
            "compile_ms": compile_ms,
            "initial_correctness": {
                "rtol": RTOL,
                "atol": ATOL,
                "max_abs_error": float(initial_error.max()),
                "mean_abs_error": float(initial_error.mean()),
                "status": "PASS",
            },
        })

        started = time.monotonic()
        iteration = 0
        while time.monotonic() - started < duration_seconds:
            inference_started = time.perf_counter_ns()
            request.infer(inputs)
            latency_ms = (time.perf_counter_ns() - inference_started) / 1_000_000.0
            iteration += 1
            elapsed_s = time.monotonic() - started
            actual = request.get_output_tensor(0).data.copy()
            finite = bool(np.isfinite(actual).all())
            if finite:
                error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
                max_abs_error = float(error.max())
                correct = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
            else:
                max_abs_error = float("inf")
                correct = False
            messages.put({
                "type": "heartbeat",
                "iteration": iteration,
                "elapsed_s": elapsed_s,
                "latency_ms": latency_ms,
                "finite": finite,
                "correct": correct,
                "max_abs_error": max_abs_error,
            })
            if not finite or not correct:
                messages.put({
                    "type": "validation_failure",
                    "iteration": iteration,
                    "finite": finite,
                    "correct": correct,
                    "max_abs_error": max_abs_error,
                })
                return
        messages.put({
            "type": "completed",
            "iteration": iteration,
            "elapsed_s": time.monotonic() - started,
        })
    except BaseException as exc:
        messages.put({
            "type": "worker_exception",
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        })


def stop_worker(process: mp.Process) -> str:
    process.terminate()
    process.join(timeout=5.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=5.0)
        return "SIGKILL_AFTER_SIGTERM_TIMEOUT"
    return "SIGTERM"


def main() -> None:
    args = arguments()
    if args.duration_minutes <= 0 or args.warmup < 0:
        raise ValueError("duration must be > 0 and warmup must be >= 0")
    if min(
        args.stall_seconds,
        args.startup_seconds,
        args.telemetry_seconds,
        args.window_seconds,
    ) <= 0:
        raise ValueError("timeout, telemetry, and window values must be > 0")

    run_dir = EVIDENCE_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    latency_path = run_dir / "latencies.csv"
    telemetry_path = run_dir / "supervisor_telemetry.csv"
    result_path = run_dir / "result.json"
    started_at = datetime.now(timezone.utc)

    context = mp.get_context("spawn")
    messages = context.Queue()
    process = context.Process(
        target=inference_worker,
        args=(messages, args.duration_minutes * 60.0, args.warmup),
    )
    process.start()

    supervisor_started = time.monotonic()
    last_message_at = supervisor_started
    worker_ready = False
    ready_evidence = None
    final_event = None
    recovery = None
    next_progress = 60.0
    next_telemetry = 0.0
    latency_values = array("d")
    window_values: dict[int, array] = defaultdict(lambda: array("d"))
    telemetry_rows: list[dict[str, object]] = []
    correctness_failures = 0
    nonfinite_outputs = 0
    maximum_abs_error = 0.0
    last_heartbeat = None

    latency_fields = (
        "iteration",
        "elapsed_s",
        "window_index",
        "latency_ms",
        "finite",
        "correct",
        "max_abs_error",
    )
    telemetry_fields = (
        "elapsed_s",
        "worker_rss_bytes",
        "supervisor_rss_bytes",
        "system_available_memory_bytes",
        "package_temperature_c",
        "max_sensor_temperature_c",
    )
    with latency_path.open("w", newline="", encoding="utf-8") as latency_stream, telemetry_path.open(
        "w", newline="", encoding="utf-8"
    ) as telemetry_stream:
        latency_writer = csv.DictWriter(latency_stream, fieldnames=latency_fields)
        telemetry_writer = csv.DictWriter(telemetry_stream, fieldnames=telemetry_fields)
        latency_writer.writeheader()
        telemetry_writer.writeheader()
        while True:
            now = time.monotonic()
            supervisor_elapsed = now - supervisor_started
            if supervisor_elapsed >= next_telemetry:
                snapshot = parent_telemetry(supervisor_elapsed, process.pid)
                telemetry_rows.append(snapshot)
                telemetry_writer.writerow(snapshot)
                telemetry_stream.flush()
                latency_stream.flush()
                next_telemetry += args.telemetry_seconds

            timeout_limit = args.stall_seconds if worker_ready else args.startup_seconds
            if now - last_message_at > timeout_limit:
                try:
                    worker_snapshot = {
                        "status": psutil.Process(process.pid).status(),
                        "cpu_percent": psutil.Process(process.pid).cpu_percent(interval=0.2),
                        "memory_rss_bytes": psutil.Process(process.pid).memory_info().rss,
                        "num_threads": psutil.Process(process.pid).num_threads(),
                    }
                except psutil.Error as exc:
                    worker_snapshot = {"snapshot_error": f"{type(exc).__name__}: {exc}"}
                final_event = {
                    "type": "watchdog_timeout",
                    "stage": "inference" if worker_ready else "startup",
                    "seconds_without_heartbeat": now - last_message_at,
                    "worker_snapshot": worker_snapshot,
                }
                recovery = stop_worker(process)
                break

            try:
                message = messages.get(timeout=0.25)
            except queue.Empty:
                if not process.is_alive():
                    final_event = {
                        "type": "worker_exited_without_final_event",
                        "exitcode": process.exitcode,
                    }
                    break
                continue

            last_message_at = time.monotonic()
            event_type = message["type"]
            if event_type == "ready":
                worker_ready = True
                ready_evidence = message
                print(
                    f"worker ready pid={message['pid']} device={message['device_full_name']} "
                    f"watchdog={args.stall_seconds}s",
                    flush=True,
                )
            elif event_type == "heartbeat":
                last_heartbeat = message
                latency_ms = float(message["latency_ms"])
                elapsed_s = float(message["elapsed_s"])
                window_index = int(elapsed_s // args.window_seconds)
                latency_values.append(latency_ms)
                window_values[window_index].append(latency_ms)
                finite = bool(message["finite"])
                correct = bool(message["correct"])
                if not finite:
                    nonfinite_outputs += 1
                if not correct:
                    correctness_failures += 1
                maximum_abs_error = max(maximum_abs_error, float(message["max_abs_error"]))
                latency_writer.writerow({
                    "iteration": message["iteration"],
                    "elapsed_s": elapsed_s,
                    "window_index": window_index,
                    "latency_ms": latency_ms,
                    "finite": finite,
                    "correct": correct,
                    "max_abs_error": message["max_abs_error"],
                })
                if elapsed_s >= next_progress:
                    latency_stream.flush()
                    print(
                        f"progress elapsed={elapsed_s / 60:.1f}min "
                        f"iterations={message['iteration']} "
                        f"failures={correctness_failures + nonfinite_outputs}",
                        flush=True,
                    )
                    next_progress += 60.0
            else:
                final_event = message
                break

    if process.is_alive():
        process.join(timeout=2.0)
    if process.is_alive():
        recovery = stop_worker(process)

    completed = bool(final_event and final_event["type"] == "completed")
    hard_pass = (
        completed
        and bool(latency_values)
        and correctness_failures == 0
        and nonfinite_outputs == 0
        and process.exitcode == 0
    )
    if hard_pass:
        status = "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING"
    elif final_event and final_event["type"] == "watchdog_timeout":
        status = "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED"
    else:
        status = "FAIL"

    window_summaries = [
        {
            "window_index": index,
            "start_s": index * args.window_seconds,
            "end_s": (index + 1) * args.window_seconds,
            "iterations": len(values),
            "latency_ms": stats(values),
        }
        for index, values in sorted(window_values.items())
    ]
    result = {
        "schema_version": 1,
        "run_id": args.run_id,
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "scope": "Isolated-worker OpenVINO synchronous GPU.0 FP32 inference; parent-side evidence, telemetry, and watchdog; robot/system paths excluded.",
        "architecture": {
            "inference_worker": "OpenVINO load/compile, inference, output correctness, queue heartbeat only",
            "supervisor": "CSV evidence, telemetry, progress reporting, and watchdog recovery",
            "known_limitation": "A pass qualifies only this isolated-worker architecture; the monolithic worker remains a known failing path.",
        },
        "configuration": {
            "device": "GPU.0",
            "precision": "f32",
            "duration_minutes": args.duration_minutes,
            "warmup_iterations": args.warmup,
            "stall_seconds": args.stall_seconds,
            "startup_seconds": args.startup_seconds,
            "telemetry_seconds": args.telemetry_seconds,
            "window_seconds": args.window_seconds,
        },
        "artifacts": {
            "ir_xml_sha256": sha256(IR_PATH),
            "ir_bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
            "reference_input_sha256": sha256(PACKAGE_DIR / "reference_model_input.pt"),
            "reference_output_sha256": sha256(PACKAGE_DIR / "reference_output_normalized.pt"),
        },
        "worker_ready": ready_evidence,
        "worker_exitcode": process.exitcode,
        "recovery": recovery,
        "final_event": final_event,
        "last_completed_inference": last_heartbeat,
        "execution": {
            "iterations": len(latency_values),
            "maximum_abs_error": maximum_abs_error,
            "hard_gates": {
                "completed_requested_duration": completed,
                "worker_exitcode_zero": process.exitcode == 0,
                "nonfinite_outputs": nonfinite_outputs,
                "correctness_failures": correctness_failures,
                "watchdog_timeout": bool(
                    final_event and final_event["type"] == "watchdog_timeout"
                ),
            },
        },
        "latency_ms": stats(latency_values) if latency_values else None,
        "latency_histogram_ms": latency_histogram(latency_values) if latency_values else None,
        "window_summaries": window_summaries,
        "telemetry_summary": {
            "samples": len(telemetry_rows),
            "worker_rss_bytes": summarize_numeric(telemetry_rows, "worker_rss_bytes"),
            "supervisor_rss_bytes": summarize_numeric(telemetry_rows, "supervisor_rss_bytes"),
            "system_available_memory_bytes": summarize_numeric(
                telemetry_rows, "system_available_memory_bytes"
            ),
            "package_temperature_c": summarize_numeric(
                telemetry_rows, "package_temperature_c"
            ),
            "max_sensor_temperature_c": summarize_numeric(
                telemetry_rows, "max_sensor_temperature_c"
            ),
        },
        "evidence_files": {
            "latencies_csv": "latencies.csv",
            "supervisor_telemetry_csv": "supervisor_telemetry.csv",
        },
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved isolated GPU stability evidence: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
