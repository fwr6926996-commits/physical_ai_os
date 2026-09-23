"""Run a GPU inference worker under an external heartbeat watchdog."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import multiprocessing as mp
import queue
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_ROOT = HERE / "evidence" / "phase3_gpu_guarded_diagnostics"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
RTOL = 1e-4
ATOL = 1e-5


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded GPU.0 hang reproduction with an external watchdog.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--duration-minutes", type=float, default=5.0)
    parser.add_argument("--watchdog-seconds", type=float, default=5.0)
    parser.add_argument("--startup-seconds", type=float, default=60.0)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def worker(messages: mp.Queue, duration_seconds: float) -> None:
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
        if "Intel" not in full_name or "NVIDIA" in full_name:
            raise RuntimeError(f"GPU identity guard rejected {runtime_device}: {full_name}")

        model = core.read_model(IR_PATH)
        shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
        if shapes != {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}:
            raise RuntimeError(f"Frozen input contract changed: {shapes}")
        config = {
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
            ov.properties.hint.inference_precision: ov.Type.f32,
        }
        compiled = core.compile_model(model, runtime_device, config)
        request = compiled.create_infer_request()

        model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
        expected = torch.load(
            PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False
        )["action_chunk"].numpy()
        inputs = {
            "state": model_input["observation.state"].numpy(),
            "wrist_image": model_input["observation.images.wrist"].numpy(),
        }
        request.infer(inputs)
        actual = request.get_output_tensor(0).data.copy()
        initial_error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
        finite = bool(np.isfinite(actual).all())
        correct = finite and bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
        if not correct:
            raise RuntimeError(
                "Initial GPU correctness failed: "
                f"max_abs_error={float(initial_error.max())}"
            )
        versions = {
            name: {"build_number": value.build_number, "description": value.description}
            for name, value in core.get_versions(runtime_device).items()
        }
        messages.put({
            "type": "ready",
            "pid": __import__("os").getpid(),
            "available_devices": available,
            "runtime_device": runtime_device,
            "device_full_name": full_name,
            "openvino_version": ov.__version__,
            "plugin_versions": versions,
            "initial_max_abs_error": float(initial_error.max()),
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
                messages.put({"type": "validation_failure", "iteration": iteration})
                return
        messages.put({"type": "completed", "iteration": iteration, "elapsed_s": time.monotonic() - started})
    except BaseException as exc:
        messages.put({"type": "worker_exception", "exception_type": type(exc).__name__, "exception": str(exc)})


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
    if args.duration_minutes <= 0 or args.watchdog_seconds <= 0 or args.startup_seconds <= 0:
        raise ValueError("duration and timeout values must be > 0")
    run_dir = EVIDENCE_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    csv_path = run_dir / "heartbeats.csv"
    result_path = run_dir / "result.json"

    context = mp.get_context("spawn")
    messages = context.Queue()
    process = context.Process(target=worker, args=(messages, args.duration_minutes * 60.0))
    process.start()
    supervisor_started = time.monotonic()
    last_message_at = supervisor_started
    worker_ready = False
    ready_evidence = None
    last_heartbeat = None
    heartbeat_count = 0
    final_event = None
    recovery = None
    next_progress = 60.0

    fields = ("iteration", "elapsed_s", "latency_ms", "finite", "correct", "max_abs_error")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        while True:
            now = time.monotonic()
            timeout_limit = args.watchdog_seconds if worker_ready else args.startup_seconds
            if now - last_message_at > timeout_limit:
                final_event = {
                    "type": "watchdog_timeout",
                    "stage": "inference" if worker_ready else "startup",
                    "seconds_without_heartbeat": now - last_message_at,
                }
                recovery = stop_worker(process)
                break
            try:
                message = messages.get(timeout=0.25)
            except queue.Empty:
                if not process.is_alive():
                    final_event = {"type": "worker_exited_without_final_event", "exitcode": process.exitcode}
                    break
                continue
            last_message_at = time.monotonic()
            event_type = message["type"]
            if event_type == "ready":
                worker_ready = True
                ready_evidence = message
                print(
                    f"worker ready pid={message['pid']} device={message['device_full_name']} "
                    f"watchdog={args.watchdog_seconds}s",
                    flush=True,
                )
            elif event_type == "heartbeat":
                heartbeat_count += 1
                last_heartbeat = message
                writer.writerow({key: message[key] for key in fields})
                if message["elapsed_s"] >= next_progress:
                    stream.flush()
                    print(
                        f"progress elapsed={message['elapsed_s'] / 60:.1f}min "
                        f"iterations={message['iteration']} failures={0 if message['correct'] else 1}",
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

    if final_event and final_event["type"] == "completed":
        status = "COMPLETED_NO_HANG_REPRODUCED"
    elif final_event and final_event["type"] == "watchdog_timeout":
        status = "HANG_REPRODUCED_WATCHDOG_RECOVERED"
    else:
        status = "FAILED_OR_WORKER_EXITED"
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "status": status,
        "purpose": "Bounded reproduction only; this is not a 30-minute stability acceptance run.",
        "configuration": {
            "duration_minutes": args.duration_minutes,
            "watchdog_seconds": args.watchdog_seconds,
            "startup_seconds": args.startup_seconds,
            "device": "GPU.0",
            "precision": "f32",
        },
        "artifacts": {
            "ir_xml_sha256": sha256(IR_PATH),
            "ir_bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
        },
        "worker_ready": ready_evidence,
        "heartbeat_count": heartbeat_count,
        "last_completed_inference": last_heartbeat,
        "final_event": final_event,
        "worker_exitcode": process.exitcode,
        "recovery": recovery,
        "heartbeats_csv": "heartbeats.csv",
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved guarded diagnostic: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
