#!/usr/bin/env python3
"""Artificial-input validation for the Phase 4 Stability readiness controls."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import phase4_stability_monitor as monitor
import phase4_thermal_d2_idle_remote_sampler as thermal


HERE = Path(__file__).resolve().parent


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sample(sequence: int) -> dict[str, Any]:
    signature = {
        "throttle_bases": sorted(thermal.EXPECTED_THROTTLE_BASES),
        "temperature_paths": ["/mock/package"],
        "frequency_paths": sorted(thermal.EXPECTED_FREQUENCY_PATHS),
    }
    groups = []
    for base in thermal.EXPECTED_THROTTLE_BASES:
        groups.append(
            {
                "base_path": base,
                "field_paths": {
                    "throttle_count": f"{base}_count",
                    "throttle_total_time_ms": f"{base}_total_time_ms",
                    "throttle_max_time_ms": f"{base}_max_time_ms",
                },
                "values": {
                    "throttle_count": 10,
                    "throttle_total_time_ms": 2,
                    "throttle_max_time_ms": 1,
                },
                "complete": True,
                "missing_or_unparseable": [],
            }
        )
    return {
        "type": "sample",
        "sequence": sequence,
        "boot_id": "mock-boot",
        "inventory_signature": signature,
        "read_errors": [],
        "sample_read_duration_ms": 1.0,
        "schedule_lag_ms": 0.1,
        "target_monotonic_ns": 1_000_000_000 + sequence * 5_000_000_000,
        "temperature": {
            "package_sensor_count": 1,
            "max_sensor_c": 50.0,
            "sensors": [
                {
                    "input_path": "/mock/package",
                    "is_cpu_package": True,
                    "current_c": 50.0,
                }
            ],
        },
        "throttle_groups": groups,
        "frequency": {
            "readable": [
                {"path": path, "current_mhz": 1000.0}
                for path in thermal.EXPECTED_FREQUENCY_PATHS
            ]
        },
        "proc_stat": {
            "user": 100 + sequence,
            "nice": 0,
            "system": 10,
            "idle": 1000 + sequence * 9,
            "iowait": 0,
            "irq": 0,
            "softirq": 0,
            "steal": 0,
        },
        "interval_busy_percent": None if sequence == 0 else 5.0,
    }


def sequence() -> list[dict[str, Any]]:
    return [sample(index) for index in range(7)]


def evaluate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    return monitor.evaluate_pre_observation(
        samples,
        busy_limit_percent=10.0,
        package_limit_c=60.0,
        sensor_limit_c=65.0,
    )


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite mock evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    cases: dict[str, Any] = {}
    valid = sequence()
    cases["valid_pre_observation"] = evaluate(valid)

    busy = copy.deepcopy(valid)
    for row in busy[1:]:
        row["interval_busy_percent"] = 11.0
    cases["busy_rejected"] = evaluate(busy)

    throttle = copy.deepcopy(valid)
    throttle[-1]["throttle_groups"][0]["values"]["throttle_count"] += 1
    cases["throttle_increment_rejected"] = evaluate(throttle)

    package_hot = copy.deepcopy(valid)
    package_hot[-1]["temperature"]["sensors"][0]["current_c"] = 61.0
    package_hot[-1]["temperature"]["max_sensor_c"] = 61.0
    cases["package_entry_rejected"] = evaluate(package_hot)

    sensor_hot = copy.deepcopy(valid)
    sensor_hot[-1]["temperature"]["sensors"].append(
        {"input_path": "/mock/core", "is_cpu_package": False, "current_c": 66.0}
    )
    sensor_hot[-1]["temperature"]["max_sensor_c"] = 66.0
    cases["sensor_entry_rejected"] = evaluate(sensor_hot)

    interface = copy.deepcopy(valid)
    interface[3]["read_errors"] = [{"path": "/mock", "error": "fixture"}]
    cases["interface_failure"] = evaluate(interface)

    decreasing = copy.deepcopy(valid)
    decreasing[4]["throttle_groups"][0]["values"]["throttle_count"] = 9
    cases["counter_decrease"] = evaluate(decreasing)

    expected_authorization = {
        "stage_protocol_id": "P4-DK2500-CPU-FP32-STABILITY-002",
        "stage_protocol_version": "0.2",
        "target_hostname": platform.node(),
        "supervisor_sha256": "mock-supervisor",
    }
    monitor.validate_authorization(dict(expected_authorization), expected_authorization)
    authorization_mismatch_rejected = False
    invalid_authorization = dict(expected_authorization)
    invalid_authorization["supervisor_sha256"] = "different"
    try:
        monitor.validate_authorization(invalid_authorization, expected_authorization)
    except RuntimeError:
        authorization_mismatch_rejected = True

    expected_statuses = {
        "valid_pre_observation": "PASS_STABILITY_PRE_OBSERVATION",
        "busy_rejected": "PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "throttle_increment_rejected": "PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "package_entry_rejected": "PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "sensor_entry_rejected": "PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "interface_failure": "INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
        "counter_decrease": "INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
    }
    checks = {
        name: cases[name]["status"] == expected
        for name, expected in expected_statuses.items()
    }
    checks["authorization_match_accepted"] = True
    checks["authorization_mismatch_rejected"] = authorization_mismatch_rejected
    passed = all(checks.values())

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "P4-DK2500-CPU-FP32-STABILITY-MOCK-002",
        "status": "PASS_STABILITY_NO_TARGET_MOCK" if passed else "FAIL_STABILITY_NO_TARGET_MOCK",
        "scope": "Artificial pre-observation and authorization classification only; no target, OpenVINO or model access.",
        "implementation": {
            "monitor_sha256": monitor.sha256(HERE / "phase4_stability_monitor.py"),
            "validator_sha256": monitor.sha256(Path(__file__).resolve()),
            "python": sys.version,
        },
        "checks": checks,
        "cases": cases,
        "target_accessed": False,
        "execution_authorized": False,
        "interpretation_limits": [
            "Artificial validation does not establish DK-2500 entry state or Stability behavior.",
            "Supervisor process control remains covered by the separate Phase 4 harness tests.",
        ],
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
