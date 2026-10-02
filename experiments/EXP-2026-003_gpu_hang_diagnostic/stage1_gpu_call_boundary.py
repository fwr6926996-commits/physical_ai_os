"""Bounded GPU.0 diagnostic with explicit call boundaries and best-effort snapshots."""

from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import multiprocessing as mp
import os
import platform
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
PACKAGE_DIR = PHASE3_DIR / "policy_package_v2_9"
IR_PATH = PACKAGE_DIR / "act_fp32.xml"
EVIDENCE_ROOT = HERE / "evidence" / "stage1"
RTOL = 1e-4
ATOL = 1e-5


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One bounded GPU.0 diagnostic run with infer enter/return evidence."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--duration-seconds", type=float, default=180.0)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--stall-seconds", type=float, default=15.0)
    parser.add_argument("--startup-seconds", type=float, default=90.0)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def send(connection: Any, event_type: str, **fields: object) -> None:
    connection.send(
        {
            "type": event_type,
            "worker_monotonic_s": time.monotonic(),
            **fields,
        }
    )


def gpu_worker(
    connection: Any,
    stack_path: str,
    duration_seconds: float,
    warmup: int,
) -> None:
    stack_stream = open(stack_path, "w", encoding="utf-8", buffering=1)
    faulthandler.enable(file=stack_stream, all_threads=True)
    faulthandler.register(signal.SIGUSR1, file=stack_stream, all_threads=True)
    try:
        import openvino as ov
        import torch

        send(connection, "worker_ready", pid=os.getpid())
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

        send(connection, "stage_enter", stage="read_model")
        model = core.read_model(IR_PATH)
        send(connection, "stage_return", stage="read_model")
        shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
        expected_shapes = {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}
        if shapes != expected_shapes:
            raise RuntimeError(f"Frozen input contract changed: {shapes}")

        config = {
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
            ov.properties.hint.inference_precision: ov.Type.f32,
        }
        send(connection, "stage_enter", stage="compile_model")
        compile_started = time.perf_counter_ns()
        compiled = core.compile_model(model, runtime_device, config)
        compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0
        send(connection, "stage_return", stage="compile_model", compile_ms=compile_ms)
        request = compiled.create_infer_request()

        model_input = torch.load(
            PACKAGE_DIR / "reference_model_input.pt", weights_only=False
        )
        expected = torch.load(
            PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False
        )["action_chunk"].numpy()
        inputs = {
            "state": model_input["observation.state"].numpy(),
            "wrist_image": model_input["observation.images.wrist"].numpy(),
        }
        versions = {
            name: {
                "build_number": value.build_number,
                "description": value.description,
            }
            for name, value in core.get_versions(runtime_device).items()
        }
        send(
            connection,
            "runtime_identity",
            available_devices=available,
            runtime_device=runtime_device,
            device_full_name=full_name,
            openvino_version=ov.__version__,
            platform=platform.platform(),
            plugin_versions=versions,
        )

        sequence = 0

        def infer_once(phase: str, phase_iteration: int) -> tuple[bool, float, float]:
            nonlocal sequence
            sequence += 1
            send(
                connection,
                "infer_enter",
                sequence=sequence,
                phase=phase,
                phase_iteration=phase_iteration,
            )
            started_ns = time.perf_counter_ns()
            request.infer(inputs)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
            send(
                connection,
                "infer_return",
                sequence=sequence,
                phase=phase,
                phase_iteration=phase_iteration,
                latency_ms=latency_ms,
            )
            actual = request.get_output_tensor(0).data.copy()
            finite = bool(np.isfinite(actual).all())
            if finite:
                error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
                max_abs_error = float(error.max())
                correct = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
            else:
                max_abs_error = float("inf")
                correct = False
            return correct, max_abs_error, latency_ms

        correct, max_abs_error, _ = infer_once("initial", 0)
        if not correct:
            raise RuntimeError(
                f"Initial GPU correctness failed: max_abs_error={max_abs_error}"
            )
        for index in range(1, warmup + 1):
            correct, max_abs_error, _ = infer_once("warmup", index)
            if not correct:
                raise RuntimeError(
                    f"Warmup correctness failed at {index}: max_abs_error={max_abs_error}"
                )

        send(connection, "measurement_ready", sequence=sequence)
        measurement_started = time.monotonic()
        iteration = 0
        while time.monotonic() - measurement_started < duration_seconds:
            iteration += 1
            correct, max_abs_error, latency_ms = infer_once("measurement", iteration)
            send(
                connection,
                "heartbeat",
                sequence=sequence,
                iteration=iteration,
                elapsed_s=time.monotonic() - measurement_started,
                latency_ms=latency_ms,
                correct=correct,
                max_abs_error=max_abs_error,
            )
            if not correct:
                send(
                    connection,
                    "validation_failure",
                    sequence=sequence,
                    iteration=iteration,
                    max_abs_error=max_abs_error,
                )
                return
        send(
            connection,
            "completed",
            sequence=sequence,
            iteration=iteration,
            elapsed_s=time.monotonic() - measurement_started,
        )
    except BaseException as exc:
        send(
            connection,
            "worker_exception",
            exception_type=type(exc).__name__,
            exception=str(exc),
        )
    finally:
        connection.close()
        stack_stream.close()


def read_text(path: Path) -> dict[str, object]:
    try:
        return {"status": "READ", "content": path.read_text(errors="replace")}
    except OSError as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


def proc_snapshot(pid: int) -> dict[str, object]:
    root = Path("/proc") / str(pid)
    snapshot: dict[str, object] = {
        "pid": pid,
        "status": read_text(root / "status"),
        "wchan": read_text(root / "wchan"),
        "syscall": read_text(root / "syscall"),
        "threads": [],
    }
    task_root = root / "task"
    try:
        task_dirs = sorted(task_root.iterdir(), key=lambda item: int(item.name))
    except OSError as exc:
        snapshot["threads_error"] = f"{type(exc).__name__}: {exc}"
        return snapshot
    for task_dir in task_dirs:
        snapshot["threads"].append(
            {
                "tid": int(task_dir.name),
                "status": read_text(task_dir / "status"),
                "wchan": read_text(task_dir / "wchan"),
                "stack": read_text(task_dir / "stack"),
            }
        )
    return snapshot


def stop_worker(process: mp.Process) -> str:
    process.terminate()
    process.join(timeout=5.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=5.0)
        return "SIGKILL_AFTER_SIGTERM_TIMEOUT"
    return "SIGTERM"


def capture_kernel_journal(started_at: datetime, destination: Path) -> dict[str, object]:
    command = [
        "journalctl",
        "-k",
        "--since",
        started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "--no-pager",
    ]
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10.0,
            check=False,
        )
        destination.write_text(completed.stdout, encoding="utf-8")
        return {"returncode": completed.returncode, "path": destination.name}
    except (OSError, subprocess.SubprocessError) as exc:
        destination.write_text(
            f"{type(exc).__name__}: {exc}\n", encoding="utf-8"
        )
        return {"returncode": None, "path": destination.name, "error": str(exc)}


def main() -> None:
    args = arguments()
    if args.duration_seconds <= 0 or args.warmup < 0:
        raise ValueError("duration must be > 0 and warmup must be >= 0")
    if min(args.stall_seconds, args.startup_seconds) <= 0:
        raise ValueError("stall and startup timeouts must be > 0")

    run_dir = EVIDENCE_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    stack_path = run_dir / "python_stack.txt"
    proc_path = run_dir / "proc_snapshot.json"
    journal_path = run_dir / "kernel_journal.txt"
    result_path = run_dir / "result.json"
    started_at = datetime.now(timezone.utc)

    context = mp.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=gpu_worker,
        args=(
            child_connection,
            str(stack_path),
            args.duration_seconds,
            args.warmup,
        ),
    )
    process.start()
    child_connection.close()

    supervisor_started = time.monotonic()
    last_message_at = supervisor_started
    worker_ready = False
    events: list[dict[str, object]] = []
    last_infer_enter: dict[str, object] | None = None
    last_infer_return: dict[str, object] | None = None
    last_heartbeat: dict[str, object] | None = None
    runtime_identity: dict[str, object] | None = None
    final_event: dict[str, object] | None = None
    recovery: str | None = None
    diagnostic_snapshot: dict[str, object] | None = None

    with events_path.open("w", encoding="utf-8") as event_stream:
        while True:
            now = time.monotonic()
            timeout = args.stall_seconds if worker_ready else args.startup_seconds
            if now - last_message_at > timeout:
                final_event = {
                    "type": "watchdog_timeout",
                    "stage": (
                        str(last_infer_enter.get("phase"))
                        if last_infer_enter
                        else "startup"
                    ),
                    "seconds_without_message": now - last_message_at,
                }
                try:
                    os.kill(process.pid, signal.SIGUSR1)
                    time.sleep(0.3)
                except OSError:
                    pass
                diagnostic_snapshot = proc_snapshot(process.pid)
                proc_path.write_text(
                    json.dumps(diagnostic_snapshot, indent=2) + "\n",
                    encoding="utf-8",
                )
                recovery = stop_worker(process)
                break

            if parent_connection.poll(0.05):
                try:
                    message = parent_connection.recv()
                except EOFError:
                    final_event = {
                        "type": "worker_pipe_closed",
                        "exitcode": process.exitcode,
                    }
                    break
                observed = {
                    **message,
                    "supervisor_elapsed_s": time.monotonic() - supervisor_started,
                }
                events.append(observed)
                event_stream.write(json.dumps(observed, sort_keys=True) + "\n")
                event_stream.flush()
                last_message_at = time.monotonic()
                event_type = str(message["type"])
                if event_type == "worker_ready":
                    worker_ready = True
                elif event_type == "runtime_identity":
                    runtime_identity = observed
                elif event_type == "infer_enter":
                    last_infer_enter = observed
                elif event_type == "infer_return":
                    last_infer_return = observed
                elif event_type == "heartbeat":
                    last_heartbeat = observed
                elif event_type in (
                    "completed",
                    "worker_exception",
                    "validation_failure",
                ):
                    final_event = observed
                    break
            elif not process.is_alive():
                final_event = {
                    "type": "worker_exited_without_final_event",
                    "exitcode": process.exitcode,
                }
                break

    if process.is_alive():
        process.join(timeout=2.0)
    if process.is_alive():
        recovery = stop_worker(process)
    parent_connection.close()

    journal_capture = capture_kernel_journal(started_at, journal_path)
    if not proc_path.exists():
        proc_path.write_text(
            json.dumps({"status": "NOT_CAPTURED_NO_WATCHDOG_TIMEOUT"}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    if not stack_path.exists():
        stack_path.write_text("No Python stack output was captured.\n", encoding="utf-8")

    entered_sequence = last_infer_enter.get("sequence") if last_infer_enter else None
    returned_sequence = last_infer_return.get("sequence") if last_infer_return else None
    first_missing_event = None
    if entered_sequence is not None and entered_sequence != returned_sequence:
        first_missing_event = {
            "expected": "infer_return",
            "sequence": entered_sequence,
            "phase": last_infer_enter.get("phase"),
            "phase_iteration": last_infer_enter.get("phase_iteration"),
        }

    if final_event and final_event["type"] == "watchdog_timeout":
        status = "HANG_REPRODUCED_AND_BOUNDED"
    elif final_event and final_event["type"] == "completed":
        status = "NO_HANG_REPRODUCED_SINGLE_RUN_COMPLETE"
    elif final_event and final_event["type"] == "worker_exception":
        status = "WORKER_EXCEPTION_CAPTURED"
    else:
        status = "UNEXPECTED_OR_INCOMPLETE"

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE1-GPU-CALL-BOUNDARY-V1",
        "run_id": args.run_id,
        "status": status,
        "scope": "One bounded exploratory GPU.0 call-boundary diagnostic; not qualification or admission evidence.",
        "configuration": {
            "duration_seconds": args.duration_seconds,
            "warmup": args.warmup,
            "stall_seconds": args.stall_seconds,
            "startup_seconds": args.startup_seconds,
            "device": "GPU.0",
            "precision": "f32",
            "performance_hint": "LATENCY",
        },
        "artifacts": {
            "ir_xml_sha256": sha256(IR_PATH),
            "ir_bin_sha256": sha256(IR_PATH.with_suffix(".bin")),
            "reference_input_sha256": sha256(
                PACKAGE_DIR / "reference_model_input.pt"
            ),
            "reference_output_sha256": sha256(
                PACKAGE_DIR / "reference_output_normalized.pt"
            ),
        },
        "runtime_identity": runtime_identity,
        "last_confirmed": {
            "infer_enter": last_infer_enter,
            "infer_return": last_infer_return,
            "heartbeat": last_heartbeat,
        },
        "first_missing_event": first_missing_event,
        "final_event": final_event,
        "worker_exitcode": process.exitcode,
        "recovery": recovery,
        "diagnostic_snapshot_captured": diagnostic_snapshot is not None,
        "kernel_journal_capture": journal_capture,
        "interpretation_limits": [
            "An entered inference without a return localizes loss of progress to that synchronous call only.",
            "Python, proc, and kernel evidence may narrow the boundary but do not automatically prove a causal component.",
            "A non-reproduced hang does not readmit GPU.0 or invalidate the prior failures.",
        ],
        "evidence_files": {
            "events": events_path.name,
            "python_stack": stack_path.name,
            "proc_snapshot": proc_path.name,
            "kernel_journal": journal_path.name,
        },
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved Stage 1 evidence: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
