#!/usr/bin/env python3
"""Validate D2-IDLE classification and guards using artificial JSONL only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import phase4_thermal_d2_idle_remote_sampler as sampler


HERE = Path(__file__).resolve().parent
SUPERVISOR = HERE / "phase4_thermal_d2_idle_supervisor.py"
REMOTE_SAMPLER = HERE / "phase4_thermal_d2_idle_remote_sampler.py"
PROTOCOL = HERE / "PHASE4_THERMAL_D2_IDLE_MOCK_PROTOCOL_V0_3_20261014.md"
PROTOCOL_ID = "P4-DK2500-THERMAL-D2-IDLE-MOCK-001"
PROTOCOL_VERSION = "0.3"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def configuration() -> dict[str, Any]:
    return {
        "pre_observation_seconds": 30.0,
        "formal_observation_seconds": 600.0,
        "interval_seconds": 5.0,
        "pre_busy_limit_percent": 10.0,
        "formal_busy_limit_percent": 10.0,
        "sustained_busy_limit_percent": 20.0,
        "sustained_busy_windows": 3,
        "thermal_stop_c": 100.0,
        "expected_sample_count": 127,
    }


def base_identity() -> dict[str, Any]:
    throttle_groups = [
        {
            "base_path": "/mock/cpu0/core_throttle",
            "field_paths": {
                "throttle_count": "/mock/cpu0/core_throttle_count",
                "throttle_total_time_ms": "/mock/cpu0/core_throttle_total_time_ms",
                "throttle_max_time_ms": "/mock/cpu0/core_throttle_max_time_ms",
            },
        },
        {
            "base_path": "/mock/cpu0/package_throttle",
            "field_paths": {
                "throttle_count": "/mock/cpu0/package_throttle_count",
                "throttle_total_time_ms": "/mock/cpu0/package_throttle_total_time_ms",
                "throttle_max_time_ms": "/mock/cpu0/package_throttle_max_time_ms",
            },
        },
        {
            "base_path": "/mock/cpu1/package_throttle",
            "field_paths": {
                "throttle_count": "/mock/cpu1/package_throttle_count",
                "throttle_total_time_ms": "/mock/cpu1/package_throttle_total_time_ms",
                "throttle_max_time_ms": "/mock/cpu1/package_throttle_max_time_ms",
            },
        },
    ]
    temperature_sensors = [
        {
            "input_path": "/mock/hwmon/package_input",
            "hwmon_name": "coretemp",
            "label": "Package id 0",
            "is_cpu_package": True,
        },
        {
            "input_path": "/mock/hwmon/core_input",
            "hwmon_name": "coretemp",
            "label": "Core 0",
            "is_cpu_package": False,
        },
    ]
    frequency_paths = ["/mock/cpu0/scaling_cur_freq", "/mock/cpu1/scaling_cur_freq"]
    signature = {
        "throttle_bases": sorted(group["base_path"] for group in throttle_groups),
        "temperature_paths": sorted(sensor["input_path"] for sensor in temperature_sensors),
        "frequency_paths": sorted(frequency_paths),
    }
    return {
        "type": "runtime_identity",
        "identity": {
            "hostname": "mock-dk2500",
            "cpu_model": "mock-cpu",
            "os_pretty_name": "mock-os",
            "kernel": "mock-kernel",
            "python_version": "mock-python",
        },
        "boot_id": "mock-boot-id",
        "inventory": {
            "online_cpu_declaration": "0-1",
            "online_cpus": [0, 1],
            "throttle_groups": throttle_groups,
            "temperature_sensors": temperature_sensors,
            "frequency_paths": frequency_paths,
        },
        "inventory_signature": signature,
        "startup_errors": [],
        "configuration": configuration(),
        "actions": {
            "target_file_created": False,
            "openvino_or_model_accessed": False,
            "deliberate_load_generated": False,
            "system_configuration_changed": False,
        },
    }


def proc_stat_start() -> dict[str, int]:
    return {
        "user": 1000,
        "nice": 0,
        "system": 500,
        "idle": 10000,
        "iowait": 100,
        "irq": 50,
        "softirq": 50,
        "steal": 0,
    }


def advance_proc_stat(value: dict[str, int], busy: float) -> dict[str, int]:
    total_delta = 1000
    active_delta = int(round(total_delta * busy / 100.0))
    next_value = dict(value)
    next_value["user"] += active_delta
    next_value["idle"] += total_delta - active_delta
    return next_value


def busy_profile_quiet(index: int) -> float:
    return 5.0


def build_sequence(
    busy_profile: Callable[[int], float] = busy_profile_quiet,
    terminal_type: str = "completed",
    terminal_sequence: int = 126,
    sample_count: int = 127,
) -> list[dict[str, Any]]:
    identity = base_identity()
    events: list[dict[str, Any]] = [identity]
    stat = proc_stat_start()
    previous_stat: dict[str, int] | None = None
    base_ns = 10_000_000_000
    for sequence in range(sample_count):
        if sequence > 0:
            stat = advance_proc_stat(stat, busy_profile(sequence))
        reported_busy = None
        if previous_stat is not None:
            reported_busy = sampler.busy_percent(previous_stat, stat)
        if sequence < 6:
            phase = "pre_observation"
        elif sequence == 6:
            phase = "pre_formal_boundary"
        else:
            phase = "formal_observation"
        groups = []
        for offset, group in enumerate(identity["inventory"]["throttle_groups"]):
            count = 100 + offset
            groups.append(
                {
                    "base_path": group["base_path"],
                    "field_paths": group["field_paths"],
                    "values": {
                        "throttle_count": count,
                        "throttle_total_time_ms": 10 + offset,
                        "throttle_max_time_ms": 2,
                    },
                    "complete": True,
                    "missing_or_unparseable": [],
                }
            )
        target_ns = base_ns + sequence * 5_000_000_000
        events.append(
            {
                "type": "sample",
                "sequence": sequence,
                "phase": phase,
                "target_utc": f"2026-10-14T00:{sequence // 12:02d}:{(sequence % 12) * 5:02d}+00:00",
                "target_monotonic_ns": target_ns,
                "elapsed_s": sequence * 5.0,
                "scheduled_elapsed_s": sequence * 5.0,
                "schedule_lag_ms": 0.0,
                "sample_read_duration_ms": 8.0,
                "boot_id": "mock-boot-id",
                "inventory_signature": deepcopy(identity["inventory_signature"]),
                "throttle_groups": groups,
                "temperature": {
                    "sensors": [
                        {**identity["inventory"]["temperature_sensors"][0], "current_c": 40.0},
                        {**identity["inventory"]["temperature_sensors"][1], "current_c": 39.0},
                    ],
                    "max_sensor_c": 40.0,
                    "package_sensor_count": 1,
                },
                "frequency": {
                    "readable": [
                        {"path": path, "current_mhz": 400.0}
                        for path in identity["inventory"]["frequency_paths"]
                    ]
                },
                "proc_stat": dict(stat),
                "interval_busy_percent": reported_busy,
                "busy_calculation_error": None,
                "loadavg": [0.01, 0.02, 0.03],
                "read_errors": [],
            }
        )
        previous_stat = dict(stat)
    events.append(
        {
            "type": terminal_type,
            "sequence": terminal_sequence,
            "reason": "MOCK_EXPECTED_TERMINAL",
        }
    )
    return events


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, sort_keys=True) + "\n")


def run_case(
    root: Path,
    name: str,
    events: list[dict[str, Any]],
    expected_status: str,
    expected_returncode: int,
    stream_mode: bool = False,
    stall_after_lines: int = 0,
    partial_line: int = 0,
) -> dict[str, Any]:
    fixture = root / f"{name}.jsonl"
    write_jsonl(fixture, events)
    evidence_root = root / "evidence"
    command = [
        sys.executable,
        str(SUPERVISOR),
        "--run-id",
        name,
        "--evidence-root",
        str(evidence_root),
        "--test-stream-fixture-sequence" if stream_mode else "--test-fixture-sequence",
        str(fixture),
    ]
    if stream_mode:
        command.extend(
            [
                "--test-stream-stall-after-lines",
                str(stall_after_lines),
                "--test-watchdog-seconds",
                "0.05",
                "--test-stream-partial-line",
                str(partial_line),
            ]
        )
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    result_path = evidence_root / name / "result.json"
    if not result_path.exists():
        raise AssertionError(f"{name}: result.json missing: {completed.stderr}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if completed.returncode != expected_returncode:
        raise AssertionError(
            f"{name}: returncode {completed.returncode} != {expected_returncode}: {completed.stderr}"
        )
    if result["status"] != expected_status:
        raise AssertionError(f"{name}: {result['status']} != {expected_status}")
    if result["target_accessed"] or result["execution_authorized"]:
        raise AssertionError(f"{name}: target or execution flag unexpectedly true")
    return {
        "returncode": completed.returncode,
        "status": result["status"],
        "sample_count": result["sample_count"],
        "detected_terminal": result["detected_terminal"],
        "classification_reasons": result["classification_reasons"],
        "pre_average_busy_percent": result["pre_average_busy_percent"],
        "formal_average_busy_percent": result["formal_average_busy_percent"],
        "max_sensor_c": result["max_sensor_c"],
        "throttle_change_summary": result["throttle_change_summary"],
        "target_accessed": result["target_accessed"],
        "stream_control": result["stream_control"],
    }


def production_guard(root: Path) -> dict[str, Any]:
    evidence_root = root / "production_guard_evidence"
    completed = subprocess.run(
        [
            sys.executable,
            str(SUPERVISOR),
            "--run-id",
            "production_guard",
            "--evidence-root",
            str(evidence_root),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    expected = "requires authorization and dedicated SSH key"
    if completed.returncode == 0 or expected not in completed.stderr:
        raise AssertionError(f"production guard failed: {completed.stderr}")
    if evidence_root.exists():
        raise AssertionError("production guard created an evidence directory")
    return {
        "returncode_nonzero": True,
        "authorization_guard_error_present": True,
        "evidence_directory_created": False,
    }


def fixture_argument_guard(root: Path) -> dict[str, Any]:
    fixture = root / "fixture_guard.jsonl"
    write_jsonl(fixture, build_sequence())
    evidence_root = root / "fixture_guard_evidence"
    completed = subprocess.run(
        [
            sys.executable,
            str(SUPERVISOR),
            "--run-id",
            "fixture_guard",
            "--evidence-root",
            str(evidence_root),
            "--test-fixture-sequence",
            str(fixture),
            "--authorization-file",
            str(root / "forbidden-authorization.json"),
            "--ssh-key",
            str(root / "forbidden-key"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    expected = "Fixture mode must not receive authorization or SSH arguments"
    if completed.returncode == 0 or expected not in completed.stderr:
        raise AssertionError(f"fixture argument guard failed: {completed.stderr}")
    if evidence_root.exists():
        raise AssertionError("fixture argument guard created an evidence directory")
    return {
        "returncode_nonzero": True,
        "guard_error_present": True,
        "evidence_directory_created": False,
    }


def main() -> int:
    args = arguments()
    with tempfile.TemporaryDirectory(prefix="phase4_d2_idle_mock_") as temporary:
        root = Path(temporary)
        cases: dict[str, Any] = {}

        complete = build_sequence()
        cases["complete_quiet_sequence"] = run_case(
            root,
            "complete_quiet_sequence",
            complete,
            "MOCK_IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING",
            0,
        )

        stream_complete = build_sequence()
        cases["streaming_complete_sequence"] = run_case(
            root,
            "streaming_complete_sequence",
            stream_complete,
            "MOCK_IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING",
            0,
            stream_mode=True,
        )

        stream_watchdog = build_sequence()
        cases["streaming_watchdog_timeout"] = run_case(
            root,
            "streaming_watchdog_timeout",
            stream_watchdog,
            "MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED",
            1,
            stream_mode=True,
            stall_after_lines=2,
        )

        partial_line_watchdog = build_sequence()
        cases["streaming_partial_line_watchdog"] = run_case(
            root,
            "streaming_partial_line_watchdog",
            partial_line_watchdog,
            "MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED",
            1,
            stream_mode=True,
            partial_line=2,
        )
        partial_control = cases["streaming_partial_line_watchdog"]["stream_control"]
        if partial_control.get("recovery") != "SIGTERM":
            raise AssertionError("partial-line watchdog did not recover with SIGTERM")
        if not partial_control.get("parse_errors"):
            raise AssertionError("partial-line parse error was not preserved")
        if int(partial_control.get("raw_stdout_bytes", 0)) <= 0:
            raise AssertionError("partial raw stdout was not preserved")

        pre_busy = build_sequence(
            busy_profile=lambda index: 15.0 if index <= 6 else 5.0,
            terminal_type="idle_control_contaminated",
            terminal_sequence=6,
            sample_count=7,
        )
        cases["pre_observation_contaminated"] = run_case(
            root,
            "pre_observation_contaminated",
            pre_busy,
            "MOCK_IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED",
            1,
        )

        sustained = build_sequence(
            busy_profile=lambda index: 25.0 if 7 <= index <= 9 else 5.0,
            terminal_type="idle_control_contaminated",
            terminal_sequence=9,
            sample_count=10,
        )
        cases["sustained_formal_contamination"] = run_case(
            root,
            "sustained_formal_contamination",
            sustained,
            "MOCK_IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED",
            1,
        )

        formal_average = build_sequence(
            busy_profile=lambda index: 15.0 if index >= 7 else 5.0,
            terminal_type="idle_control_contaminated",
            terminal_sequence=126,
        )
        cases["formal_average_contaminated"] = run_case(
            root,
            "formal_average_contaminated",
            formal_average,
            "MOCK_IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED",
            1,
        )

        thermal = build_sequence(
            terminal_type="thermal_stop", terminal_sequence=10, sample_count=11
        )
        thermal[-2]["temperature"]["max_sensor_c"] = 100.0
        thermal[-2]["temperature"]["sensors"][0]["current_c"] = 100.0
        cases["thermal_stop"] = run_case(
            root,
            "thermal_stop",
            thermal,
            "MOCK_THERMAL_STOP_REVIEW_REQUIRED",
            1,
        )

        missing_path = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        missing_path[-2]["throttle_groups"].pop()
        cases["missing_path"] = run_case(
            root,
            "missing_path",
            missing_path,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        negative_counter = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        negative_counter[-2]["throttle_groups"][0]["values"]["throttle_count"] = 99
        cases["negative_counter"] = run_case(
            root,
            "negative_counter",
            negative_counter,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        boot_change = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        boot_change[-2]["boot_id"] = "different-boot"
        cases["boot_change"] = run_case(
            root,
            "boot_change",
            boot_change,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        monotonic = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        monotonic[-2]["target_monotonic_ns"] = monotonic[-3]["target_monotonic_ns"] - 1
        cases["monotonic_reversal"] = run_case(
            root,
            "monotonic_reversal",
            monotonic,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        read_duration = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        read_duration[-2]["sample_read_duration_ms"] = 5000.0
        cases["sample_read_consumed_interval"] = run_case(
            root,
            "sample_read_consumed_interval",
            read_duration,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        missed_deadline = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        missed_deadline[-2]["schedule_lag_ms"] = 5000.0
        cases["sample_deadline_missed"] = run_case(
            root,
            "sample_deadline_missed",
            missed_deadline,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        malformed_stat = build_sequence(
            terminal_type="interface_or_timebase_failure",
            terminal_sequence=10,
            sample_count=11,
        )
        malformed_stat[-2]["proc_stat"].pop("user")
        malformed_stat[-2]["interval_busy_percent"] = None
        cases["malformed_proc_stat"] = run_case(
            root,
            "malformed_proc_stat",
            malformed_stat,
            "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            1,
        )

        cases["production_authorization_guard"] = production_guard(root)
        cases["fixture_rejects_target_arguments"] = fixture_argument_guard(root)

        summary = cases["complete_quiet_sequence"]["throttle_change_summary"]
        if any(not item.get("sum_intentionally_omitted") for item in summary.values()):
            raise AssertionError("package/throttle path summation omission was not preserved")
        if any(item.get("paths_compared") != 3 for item in summary.values()):
            raise AssertionError("expected three independent mock throttle paths")

    output = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "status": "PASS_D2_IDLE_NO_TARGET_MOCK_VALIDATION",
        "scope": "Artificial JSONL timing, activity, counter and guard validation only.",
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
            "All samples were artificial and no DK-2500 interface was read.",
            "The mock cannot establish actual idle, thermal, timing or throttle behavior.",
            "Target mode cannot start without a matching reviewed protocol and explicit authorization.",
        ],
    }
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite {output_path}")
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
