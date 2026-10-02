"""Learn parent/worker heartbeat and watchdog reasoning without using a GPU."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import queue
import time
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFAULT_EVIDENCE_ROOT = HERE / "evidence"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bounded mock worker for learning heartbeat/watchdog diagnostics."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--scenario", choices=("normal", "hang", "exception"), required=True
    )
    parser.add_argument("--duration-seconds", type=float, default=4.0)
    parser.add_argument("--work-seconds", type=float, default=0.1)
    parser.add_argument("--hang-after", type=int, default=3)
    parser.add_argument("--watchdog-seconds", type=float, default=1.0)
    parser.add_argument("--startup-seconds", type=float, default=5.0)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    return parser.parse_args()


def emit(messages: mp.Queue, event_type: str, **fields: object) -> None:
    messages.put(
        {
            "type": event_type,
            "worker_monotonic_s": time.monotonic(),
            **fields,
        }
    )


def mock_worker(
    messages: mp.Queue,
    scenario: str,
    duration_seconds: float,
    work_seconds: float,
    hang_after: int,
) -> None:
    """Emit explicit boundaries around a mock work call.

    The hang scenario intentionally stops after work_enter. It does not access a GPU.
    """
    try:
        emit(messages, "worker_ready", pid=os.getpid(), scenario=scenario)
        started = time.monotonic()
        iteration = 0
        while time.monotonic() - started < duration_seconds:
            iteration += 1
            emit(messages, "work_enter", iteration=iteration)

            if scenario == "exception" and iteration == hang_after:
                raise RuntimeError(f"intentional mock exception at iteration {iteration}")

            if scenario == "hang" and iteration == hang_after:
                while True:
                    time.sleep(60.0)

            time.sleep(work_seconds)
            emit(messages, "work_return", iteration=iteration)
            emit(messages, "heartbeat", iteration=iteration)

        emit(messages, "completed", iteration=iteration)
    except BaseException as exc:
        emit(
            messages,
            "worker_exception",
            exception_type=type(exc).__name__,
            exception=str(exc),
        )


def stop_worker(process: mp.Process) -> str:
    process.terminate()
    process.join(timeout=2.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=2.0)
        return "SIGKILL_AFTER_SIGTERM_TIMEOUT"
    return "SIGTERM"


def main() -> None:
    args = arguments()
    if min(
        args.duration_seconds,
        args.work_seconds,
        args.watchdog_seconds,
        args.startup_seconds,
    ) <= 0:
        raise ValueError("duration, work, watchdog and startup values must be > 0")
    if args.hang_after <= 0:
        raise ValueError("hang-after must be > 0")

    run_dir = args.output_root.resolve() / args.run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    result_path = run_dir / "result.json"

    context = mp.get_context("spawn")
    messages = context.Queue()
    process = context.Process(
        target=mock_worker,
        args=(
            messages,
            args.scenario,
            args.duration_seconds,
            args.work_seconds,
            args.hang_after,
        ),
    )
    process.start()

    supervisor_started = time.monotonic()
    last_message_at = supervisor_started
    worker_ready = False
    events: list[dict[str, object]] = []
    last_work_enter: dict[str, object] | None = None
    last_work_return: dict[str, object] | None = None
    last_heartbeat: dict[str, object] | None = None
    final_event: dict[str, object] | None = None
    recovery: str | None = None

    with events_path.open("w", encoding="utf-8") as event_stream:
        while True:
            now = time.monotonic()
            timeout = args.watchdog_seconds if worker_ready else args.startup_seconds
            if now - last_message_at > timeout:
                final_event = {
                    "type": "watchdog_timeout",
                    "stage": "work" if worker_ready else "startup",
                    "seconds_without_message": now - last_message_at,
                }
                recovery = stop_worker(process)
                break

            try:
                message = messages.get(timeout=0.05)
            except queue.Empty:
                if not process.is_alive():
                    final_event = {
                        "type": "worker_exited_without_final_event",
                        "exitcode": process.exitcode,
                    }
                    break
                continue

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
            elif event_type == "work_enter":
                last_work_enter = observed
            elif event_type == "work_return":
                last_work_return = observed
            elif event_type == "heartbeat":
                last_heartbeat = observed
            elif event_type in ("completed", "worker_exception"):
                final_event = observed
                break

    if process.is_alive():
        process.join(timeout=1.0)
    if process.is_alive():
        recovery = stop_worker(process)

    if args.scenario == "normal" and final_event and final_event["type"] == "completed":
        status = "PASS_HARNESS_NORMAL_COMPLETION"
    elif (
        args.scenario == "hang"
        and final_event
        and final_event["type"] == "watchdog_timeout"
        and recovery is not None
    ):
        status = "PASS_HANG_DETECTED_AND_RECOVERED"
    elif (
        args.scenario == "exception"
        and final_event
        and final_event["type"] == "worker_exception"
    ):
        status = "PASS_EXCEPTION_CAPTURED"
    else:
        status = "FAIL_UNEXPECTED_HARNESS_BEHAVIOR"

    entered_iteration = last_work_enter.get("iteration") if last_work_enter else None
    returned_iteration = last_work_return.get("iteration") if last_work_return else None
    heartbeat_iteration = last_heartbeat.get("iteration") if last_heartbeat else None
    first_missing_event = None
    if entered_iteration is not None and entered_iteration != returned_iteration:
        first_missing_event = {
            "expected": "work_return",
            "iteration": entered_iteration,
        }

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE0-MOCK-HARNESS-V1",
        "run_id": args.run_id,
        "status": status,
        "scope": "Mock parent/worker diagnostic only; no OpenVINO or GPU access.",
        "configuration": {
            "scenario": args.scenario,
            "duration_seconds": args.duration_seconds,
            "work_seconds": args.work_seconds,
            "hang_after": args.hang_after,
            "watchdog_seconds": args.watchdog_seconds,
            "startup_seconds": args.startup_seconds,
        },
        "event_count": len(events),
        "last_confirmed": {
            "work_enter": last_work_enter,
            "work_return": last_work_return,
            "heartbeat": last_heartbeat,
        },
        "first_missing_event": first_missing_event,
        "final_event": final_event,
        "worker_exitcode": process.exitcode,
        "recovery": recovery,
        "interpretation_limits": [
            "A detected mock hang validates bounded loss-of-progress detection only.",
            "This result cannot identify or exclude a GPU, driver, plugin, runtime, or model fault.",
        ],
        "evidence_files": {"events": "events.jsonl"},
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved mock harness evidence: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
