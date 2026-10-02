"""No-GPU mock validation for Stage 2B shared boundary classification."""

from __future__ import annotations

import functools
import json
import multiprocessing as mp
import time
from typing import Any

from run_stage2b_shared_boundary import classify_boundary, stable_snapshot


WARMUP = 10


def stalled_child(
    enter_sequence: Any,
    return_sequence: Any,
    ready: Any,
    enter_value: int,
    return_value: int,
) -> None:
    enter_sequence.value = enter_value
    return_sequence.value = return_value
    ready.set()
    while True:
        time.sleep(1.0)


def baseline_shape_child(
    enter_sequence: Any,
    return_sequence: Any,
    messages: Any,
    duration_seconds: float,
    warmup: int,
) -> None:
    enter_sequence.value = warmup + 1
    return_sequence.value = warmup + 1
    messages.put(
        {
            "type": "wiring_complete",
            "duration_seconds": duration_seconds,
            "warmup": warmup,
        }
    )


def hang_result(last_measurement_iteration: int) -> dict[str, object]:
    return {
        "status": "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED",
        "last_completed_inference": {"iteration": last_measurement_iteration},
        "execution": {"hard_gates": {"watchdog_timeout": True}},
        "worker_ready": {"type": "ready"},
    }


def recovered_snapshot(enter_value: int, return_value: int) -> dict[str, object]:
    context = mp.get_context("spawn")
    enter_sequence = context.RawValue("Q", 0)
    return_sequence = context.RawValue("Q", 0)
    ready = context.Event()
    process = context.Process(
        target=stalled_child,
        args=(
            enter_sequence,
            return_sequence,
            ready,
            enter_value,
            return_value,
        ),
    )
    process.start()
    if not ready.wait(timeout=2.0):
        process.terminate()
        process.join(timeout=2.0)
        raise RuntimeError("Mock child did not reach the frozen boundary")
    process.terminate()
    process.join(timeout=2.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=2.0)
    return stable_snapshot(enter_sequence, return_sequence)


def main() -> None:
    context = mp.get_context("spawn")
    wiring_enter = context.RawValue("Q", 0)
    wiring_return = context.RawValue("Q", 0)
    wiring_messages = context.Queue()
    wiring_target = functools.partial(
        baseline_shape_child,
        wiring_enter,
        wiring_return,
    )
    wiring_process = context.Process(
        target=wiring_target,
        args=(wiring_messages, 300.0, WARMUP),
    )
    wiring_process.start()
    wiring_process.join(timeout=2.0)
    if wiring_process.is_alive():
        wiring_process.kill()
        wiring_process.join(timeout=2.0)
        raise RuntimeError("Partial target wiring mock timed out")
    wiring_message = wiring_messages.get(timeout=1.0)
    if (
        wiring_process.exitcode != 0
        or wiring_enter.value != 11
        or wiring_return.value != 11
        or wiring_message.get("type") != "wiring_complete"
    ):
        raise AssertionError("Partial target wiring did not preserve baseline-shaped args")

    cases = [
        {
            "name": "infer_entered_not_returned",
            "enter": 13,
            "returned": 12,
            "heartbeat_iteration": 1,
            "expected": "HANG_INFER_ENTERED_NOT_RETURNED",
        },
        {
            "name": "after_infer_before_heartbeat",
            "enter": 13,
            "returned": 13,
            "heartbeat_iteration": 1,
            "expected": "HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT",
        },
        {
            "name": "after_heartbeat_before_next_infer",
            "enter": 12,
            "returned": 12,
            "heartbeat_iteration": 1,
            "expected": "HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER",
        },
        {
            "name": "inconsistent_gap",
            "enter": 14,
            "returned": 12,
            "heartbeat_iteration": 1,
            "expected": "BOUNDARY_EVIDENCE_INCONSISTENT",
        },
    ]
    results: list[dict[str, object]] = []
    for case in cases:
        snapshot = recovered_snapshot(int(case["enter"]), int(case["returned"]))
        classification, derived = classify_boundary(
            hang_result(int(case["heartbeat_iteration"])), snapshot, WARMUP
        )
        if classification != case["expected"]:
            raise AssertionError(
                f"{case['name']}: expected={case['expected']} actual={classification}"
            )
        results.append(
            {
                "name": case["name"],
                "classification": classification,
                "snapshot": snapshot,
                "derived": derived,
            }
        )

    complete_snapshot = {
        "first": {"enter_sequence": 14, "return_sequence": 14},
        "second": {"enter_sequence": 14, "return_sequence": 14},
        "stable": True,
    }
    complete_result = {
        "status": "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING",
        "last_completed_inference": {"iteration": 3},
        "execution": {
            "iterations": 3,
            "hard_gates": {
                "correctness_failures": 0,
                "nonfinite_outputs": 0,
            },
        },
        "worker_ready": {"type": "ready"},
    }
    classification, derived = classify_boundary(
        complete_result, complete_snapshot, WARMUP
    )
    if classification != "NO_HANG_REPRODUCED_5M_COMPLETE":
        raise AssertionError(f"complete case classified as {classification}")
    results.append(
        {
            "name": "complete",
            "classification": classification,
            "snapshot": complete_snapshot,
            "derived": derived,
        }
    )

    output = {
        "protocol_id": "EXP-2026-003-STAGE2B-MOCK-BOUNDARY-V1",
        "status": "PASS_ALL_BOUNDARY_CLASSIFICATIONS",
        "scope": "No OpenVINO or GPU access; mock shared-state and recovery only.",
        "partial_target_wiring": {
            "status": "PASS",
            "worker_exitcode": wiring_process.exitcode,
            "enter_sequence": wiring_enter.value,
            "return_sequence": wiring_return.value,
            "message": wiring_message,
        },
        "cases": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    mp.freeze_support()
    main()
