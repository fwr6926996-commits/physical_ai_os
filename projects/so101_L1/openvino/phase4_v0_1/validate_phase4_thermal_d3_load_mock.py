#!/usr/bin/env python3
"""Validate D3-LOAD artificial classification and local worker cleanup without target access."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import phase4_thermal_d2_idle_remote_sampler as sampler
import phase4_thermal_d3_load_supervisor as supervisor
import validate_phase4_thermal_d2_idle_mock as d2_fixture


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "PHASE4_THERMAL_D3_LOAD_MOCK_PROTOCOL_20261014.md"
SUPERVISOR = HERE / "phase4_thermal_d3_load_supervisor.py"
REMOTE_SAMPLER = HERE / "phase4_thermal_d2_idle_remote_sampler.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def build_d3(
    busy: Callable[[int], float],
    terminal_type: str = "load_observation_completed",
    terminal_sequence: int = 126,
    sample_count: int = 127,
    include_load: bool = True,
) -> list[dict[str, Any]]:
    events = d2_fixture.build_sequence(
        busy_profile=busy,
        terminal_type=terminal_type,
        terminal_sequence=terminal_sequence,
        sample_count=sample_count,
    )
    events[0]["configuration"] = supervisor.expected_configuration()
    events[0]["actions"]["deliberate_load_generated"] = True
    if include_load:
        start_index = next(i for i, event in enumerate(events) if event.get("type") == "sample" and event.get("sequence") == 6) + 1
        events.insert(
            start_index,
            {"type": "load_started", "sequence": 6, "worker_count": 12, "worker_pids": list(range(1200, 1212))},
        )
        terminal_index = len(events) - 1
        events.insert(
            terminal_index,
            {
                "type": "load_stopped",
                "reason": "COMPLETE" if terminal_type == "load_observation_completed" else "MOCK_STOP",
                "requested": 12,
                "started": 12,
                "alive": 0,
                "exits": {str(pid): 0 for pid in range(1200, 1212)},
                "recovery": "SIGTERM",
                "worker_records": [
                    {"pid": pid, "iterations": 10000, "checksum": pid} for pid in range(1200, 1212)
                ],
            },
        )
    return events


def run_case(root: Path, name: str, events: list[dict[str, Any]], expected: str, returncode: int) -> dict[str, Any]:
    fixture = root / f"{name}.jsonl"
    d2_fixture.write_jsonl(fixture, events)
    evidence = root / f"{name}_evidence"
    completed = subprocess.run(
        [sys.executable, str(SUPERVISOR), "--run-id", name, "--evidence-root", str(evidence), "--test-fixture-sequence", str(fixture)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != returncode:
        raise AssertionError(f"{name}: returncode {completed.returncode} != {returncode}: {completed.stderr}")
    result = json.loads((evidence / name / "result.json").read_text(encoding="utf-8"))
    if result["status"] != expected:
        raise AssertionError(f"{name}: {result['status']} != {expected}")
    return {
        "returncode": completed.returncode,
        "status": result["status"],
        "sample_count": result["sample_count"],
        "detected_terminal": result["detected_terminal"],
        "classification_reasons": result["classification_reasons"],
        "pre_average_busy_percent": result["pre_average_busy_percent"],
        "formal_average_busy_percent": result["formal_average_busy_percent"],
        "max_sensor_c": result["max_sensor_c"],
    }


def local_worker_lifecycle() -> dict[str, Any]:
    load = sampler.CpuLoadController(12)
    pids = load.start()
    time.sleep(0.2)
    before = load.poll()
    stopped = load.stop()
    survivors = []
    for pid in pids:
        try:
            os.kill(pid, 0)
            survivors.append(pid)
        except ProcessLookupError:
            pass
    if before["alive"] != 12 or stopped["alive"] != 0 or survivors:
        raise AssertionError(f"worker cleanup failed: {before=} {stopped=} {survivors=}")
    if len(stopped["worker_records"]) != 12:
        raise AssertionError("not all worker records were collected")
    return {
        "started": len(pids),
        "alive_before_stop": before["alive"],
        "alive_after_stop": stopped["alive"],
        "worker_records": len(stopped["worker_records"]),
        "survivors": survivors,
        "recovery": stopped["recovery"],
    }


def parent_death_cleanup() -> dict[str, Any]:
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    manager = os.fork()
    if manager == 0:
        os.close(read_fd)
        load = sampler.CpuLoadController(12)
        pids = load.start()
        os.write(write_fd, (json.dumps(pids) + "\n").encode("utf-8"))
        time.sleep(0.1)
        os._exit(0)
    os.close(write_fd)
    raw = bytearray()
    deadline = time.monotonic() + 3.0
    while b"\n" not in raw and time.monotonic() < deadline:
        try:
            raw.extend(os.read(read_fd, 4096))
        except BlockingIOError:
            time.sleep(0.01)
    os.close(read_fd)
    os.waitpid(manager, 0)
    if not raw:
        raise AssertionError("manager did not report worker PIDs")
    pids = json.loads(bytes(raw).splitlines()[0])
    survivors = list(pids)
    deadline = time.monotonic() + 5.0
    while survivors and time.monotonic() < deadline:
        remaining = []
        for pid in survivors:
            try:
                os.kill(pid, 0)
                remaining.append(pid)
            except ProcessLookupError:
                pass
        survivors = remaining
        time.sleep(0.02)
    if survivors:
        for pid in survivors:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
        raise AssertionError(f"parent-death cleanup left workers: {survivors}")
    return {"workers_reported": len(pids), "survivors": survivors}


def main() -> int:
    args = arguments()
    cases: dict[str, Any] = {}
    quiet_then_load = lambda i: 5.0 if i <= 6 else 80.0
    with tempfile.TemporaryDirectory(prefix="d3_load_mock_") as raw_root:
        root = Path(raw_root)
        cases["complete_valid_load"] = run_case(root, "complete_valid_load", build_d3(quiet_then_load), "MOCK_LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING", 0)

        pre_busy = build_d3(lambda i: 15.0 if i <= 6 else 80.0, terminal_type="precondition_not_met", terminal_sequence=6, sample_count=7, include_load=False)
        cases["pre_busy_rejected"] = run_case(root, "pre_busy_rejected", pre_busy, "MOCK_PRECONDITION_NOT_MET_REVIEW_REQUIRED", 1)

        pre_throttle = build_d3(quiet_then_load, terminal_type="precondition_not_met", terminal_sequence=6, sample_count=7, include_load=False)
        pre_throttle[-2]["throttle_groups"][0]["values"]["throttle_count"] += 1
        cases["pre_throttle_rejected"] = run_case(root, "pre_throttle_rejected", pre_throttle, "MOCK_PRECONDITION_NOT_MET_REVIEW_REQUIRED", 1)

        entry_hot = build_d3(quiet_then_load, terminal_type="precondition_not_met", terminal_sequence=6, sample_count=7, include_load=False)
        entry_hot[-2]["temperature"]["sensors"][0]["current_c"] = 61.0
        entry_hot[-2]["temperature"]["max_sensor_c"] = 61.0
        cases["entry_package_hot"] = run_case(root, "entry_package_hot", entry_hot, "MOCK_PRECONDITION_NOT_MET_REVIEW_REQUIRED", 1)

        sensor_hot = build_d3(quiet_then_load, terminal_type="precondition_not_met", terminal_sequence=6, sample_count=7, include_load=False)
        sensor_hot[-2]["temperature"]["sensors"][1]["current_c"] = 66.0
        sensor_hot[-2]["temperature"]["max_sensor_c"] = 66.0
        cases["entry_sensor_hot"] = run_case(root, "entry_sensor_hot", sensor_hot, "MOCK_PRECONDITION_NOT_MET_REVIEW_REQUIRED", 1)

        under = build_d3(lambda i: 5.0 if i <= 6 else 50.0, terminal_type="load_control_invalid", terminal_sequence=11, sample_count=12)
        cases["sustained_under_delivery"] = run_case(root, "sustained_under_delivery", under, "MOCK_LOAD_CONTROL_INVALID_REVIEW_REQUIRED", 1)

        avg_under = build_d3(lambda i: 5.0 if i <= 6 else 65.0, terminal_type="load_control_invalid")
        cases["formal_average_under_delivery"] = run_case(root, "formal_average_under_delivery", avg_under, "MOCK_LOAD_CONTROL_INVALID_REVIEW_REQUIRED", 1)

        worker_exit = build_d3(quiet_then_load, terminal_type="load_control_invalid", terminal_sequence=10, sample_count=11)
        worker_exit[-1]["reason"] = "LOAD_WORKER_EXITED"
        cases["worker_exit"] = run_case(root, "worker_exit", worker_exit, "MOCK_LOAD_CONTROL_INVALID_REVIEW_REQUIRED", 1)

        thermal = build_d3(quiet_then_load, terminal_type="thermal_stop", terminal_sequence=10, sample_count=11)
        thermal[-3]["temperature"]["sensors"][1]["current_c"] = 100.0
        thermal[-3]["temperature"]["max_sensor_c"] = 100.0
        cases["thermal_stop"] = run_case(root, "thermal_stop", thermal, "MOCK_THERMAL_STOP_REVIEW_REQUIRED", 1)

        bad_stop = build_d3(quiet_then_load)
        stop_event = next(event for event in bad_stop if event.get("type") == "load_stopped")
        stop_event["alive"] = 1
        cases["worker_stop_evidence_invalid"] = run_case(root, "worker_stop_evidence_invalid", bad_stop, "MOCK_LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING", 1)

        negative = build_d3(quiet_then_load, terminal_type="interface_or_timebase_failure", terminal_sequence=10, sample_count=11)
        samples = [event for event in negative if event.get("type") == "sample"]
        samples[10]["throttle_groups"][0]["values"]["throttle_count"] -= 1
        cases["negative_counter"] = run_case(root, "negative_counter", negative, "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED", 1)

        guard_root = root / "target_guard"
        guarded = subprocess.run(
            [sys.executable, str(SUPERVISOR), "--run-id", "target_guard", "--evidence-root", str(guard_root)],
            text=True,
            capture_output=True,
            check=False,
        )
        if guarded.returncode == 0 or "requires authorization and dedicated SSH key" not in guarded.stderr or guard_root.exists():
            raise AssertionError(f"target guard failed: {guarded.stderr}")
        cases["target_guard"] = {"returncode_nonzero": True, "evidence_directory_created": False}
        cases["local_worker_lifecycle"] = local_worker_lifecycle()
        cases["parent_death_cleanup"] = parent_death_cleanup()

    output = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": supervisor.PROTOCOL_ID,
        "protocol_version": supervisor.PROTOCOL_VERSION,
        "status": "PASS_D3_LOAD_NO_TARGET_MOCK_VALIDATION",
        "scope": "Artificial classification and local child-process lifecycle only.",
        "implementation": {
            "remote_sampler_sha256": sha256(REMOTE_SAMPLER),
            "supervisor_sha256": sha256(SUPERVISOR),
            "validator_sha256": sha256(Path(__file__).resolve()),
            "protocol_sha256": sha256(PROTOCOL),
            "python": sys.version,
        },
        "cases": cases,
        "target_accessed": False,
        "execution_authorized": False,
        "interpretation_limits": [
            "No DK-2500 interface, SSH, OpenVINO or model was used.",
            "The short local lifecycle validates cleanup mechanics, not target load or thermal behavior.",
            "Target execution remains disabled pending a separate protocol and authorization.",
        ],
    }
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(output_path)
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
