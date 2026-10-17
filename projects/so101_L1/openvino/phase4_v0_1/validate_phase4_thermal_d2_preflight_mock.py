#!/usr/bin/env python3
"""No-target integration controls for the D2-PREFLIGHT local supervisor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "phase4_thermal_d2_preflight.py"
REMOTE_PROBE = HERE / "phase4_thermal_d2_remote_probe.py"
PROTOCOL = HERE / "PHASE4_THERMAL_D2_PREFLIGHT_PROTOCOL_20261013.md"


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


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def valid_payload() -> dict[str, Any]:
    return {
        "probe_schema_version": 1,
        "timestamp_utc": "2026-10-13T00:00:00+00:00",
        "identity": {
            "hostname": "hepintelpc",
            "cpu_model": "Intel(R) Core(TM) Ultra 5 225U",
            "os_pretty_name": "Ubuntu 24.04.4 LTS",
            "os_version_id": "24.04",
            "kernel": "6.17.0-35-generic",
            "python_version": "3.12.3",
            "boot_id": "mock-boot-id",
            "uptime_seconds": 1234.5,
        },
        "online_cpu_declaration": "0-13",
        "online_cpus": list(range(14)),
        "throttle_groups": [
            {
                "base_path": "/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle",
                "field_paths": {
                    "throttle_count": "/mock/package_throttle_count",
                    "throttle_total_time_ms": "/mock/package_throttle_total_time_ms",
                    "throttle_max_time_ms": "/mock/package_throttle_max_time_ms",
                },
                "values": {
                    "throttle_count": 10,
                    "throttle_total_time_ms": 20,
                    "throttle_max_time_ms": 5,
                },
                "complete": True,
                "missing_or_unparseable": [],
            }
        ],
        "temperature": {
            "sensors": [
                {
                    "input_path": "/sys/class/hwmon/hwmon0/temp1_input",
                    "hwmon_name": "coretemp",
                    "label": "Package id 0",
                    "current_c": 40.0,
                    "is_cpu_package": True,
                }
            ],
            "package_sensor_count": 1,
            "max_sensor_c": 40.0,
        },
        "frequency": {
            "online_cpu_count": 14,
            "readable_path_count": 2,
            "coverage_ratio": 2 / 14,
            "readable": [
                {"path": "/mock/cpu0/scaling_cur_freq", "current_mhz": 1800.0},
                {"path": "/mock/cpu1/scaling_cur_freq", "current_mhz": 1750.0},
            ],
            "missing_or_unparseable": [f"/mock/cpu{cpu}/scaling_cur_freq" for cpu in range(2, 14)],
        },
        "read_errors": [],
        "actions": {
            "target_file_created": False,
            "openvino_or_model_accessed": False,
            "load_generated": False,
            "system_configuration_changed": False,
            "sampling_loop_used": False,
        },
    }


def run_fixture(
    root: Path,
    name: str,
    payload: dict[str, Any],
    expected_status: str,
    expected_returncode: int,
    expected_reason: str | None = None,
) -> dict[str, Any]:
    fixture = root / f"{name}.json"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        str(RUNNER),
        "--run-id",
        name,
        "--evidence-root",
        str(root / "evidence"),
        "--test-fixture",
        str(fixture),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=5)
    if completed.returncode != expected_returncode:
        raise AssertionError(
            f"{name}: rc={completed.returncode} != {expected_returncode}; stderr={completed.stderr!r}"
        )
    result = json.loads(
        (root / "evidence" / name / "result.json").read_text(encoding="utf-8")
    )
    if result["status"] != expected_status:
        raise AssertionError(f"{name}: {result['status']!r} != {expected_status!r}")
    if expected_reason is not None and expected_reason not in result["hard_fail_reasons"]:
        raise AssertionError(
            f"{name}: missing {expected_reason!r} in {result['hard_fail_reasons']!r}"
        )
    if result["target_accessed"] is not False:
        raise AssertionError(f"{name}: mock unexpectedly marked target access")
    return {
        "returncode": completed.returncode,
        "status": result["status"],
        "hard_fail_reasons": result["hard_fail_reasons"],
        "target_accessed": result["target_accessed"],
    }


def production_guard(root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(RUNNER),
        "--run-id",
        "unauthorized_target",
        "--evidence-root",
        str(root / "evidence"),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=5)
    expected = "requires an explicit one-attempt authorization"
    if completed.returncode == 0 or expected not in completed.stderr:
        raise AssertionError(
            f"Production guard failed: rc={completed.returncode}, stderr={completed.stderr!r}"
        )
    return {
        "returncode_nonzero": True,
        "authorization_error_present": True,
        "evidence_directory_created": (root / "evidence" / "unauthorized_target").exists(),
    }


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite mock evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase4_thermal_d2_mock_") as temporary:
        root = Path(temporary)
        valid = valid_payload()
        checks: dict[str, Any] = {}
        checks["valid_payload"] = run_fixture(
            root, "valid", valid, "MOCK_PREFLIGHT_PASS_REVIEW_PENDING", 0
        )

        identity_drift = copy.deepcopy(valid)
        identity_drift["identity"]["kernel"] = "unexpected-kernel"
        checks["identity_drift"] = run_fixture(
            root,
            "identity_drift",
            identity_drift,
            "MOCK_PREFLIGHT_FAIL_REVIEW_REQUIRED",
            1,
            "IDENTITY_MISMATCH:kernel",
        )

        incomplete = copy.deepcopy(valid)
        incomplete["throttle_groups"][0]["complete"] = False
        incomplete["throttle_groups"][0]["values"]["throttle_total_time_ms"] = None
        incomplete["throttle_groups"][0]["missing_or_unparseable"] = [
            "throttle_total_time_ms"
        ]
        checks["incomplete_throttle_group"] = run_fixture(
            root,
            "incomplete",
            incomplete,
            "MOCK_PREFLIGHT_FAIL_REVIEW_REQUIRED",
            1,
            "INCOMPLETE_THROTTLE_GROUP",
        )

        no_package = copy.deepcopy(valid)
        no_package["temperature"]["package_sensor_count"] = 0
        no_package["temperature"]["sensors"][0]["is_cpu_package"] = False
        checks["missing_package_temperature"] = run_fixture(
            root,
            "no_package",
            no_package,
            "MOCK_PREFLIGHT_FAIL_REVIEW_REQUIRED",
            1,
            "NO_CPU_PACKAGE_TEMPERATURE",
        )

        thermal = copy.deepcopy(valid)
        thermal["temperature"]["max_sensor_c"] = 101.0
        thermal["temperature"]["sensors"][0]["current_c"] = 101.0
        checks["thermal_abnormal_state"] = run_fixture(
            root,
            "thermal",
            thermal,
            "MOCK_PREFLIGHT_FAIL_REVIEW_REQUIRED",
            1,
            "THERMAL_ABNORMAL_STATE",
        )

        no_frequency = copy.deepcopy(valid)
        no_frequency["frequency"]["readable_path_count"] = 0
        no_frequency["frequency"]["coverage_ratio"] = 0.0
        no_frequency["frequency"]["readable"] = []
        checks["missing_frequency"] = run_fixture(
            root,
            "no_frequency",
            no_frequency,
            "MOCK_PREFLIGHT_FAIL_REVIEW_REQUIRED",
            1,
            "NO_READABLE_CPU_FREQUENCY",
        )
        checks["production_requires_authorization"] = production_guard(root)

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "P4-DK2500-THERMAL-D2-PREFLIGHT-001",
        "protocol_version": "0.1",
        "status": "PASS_D2_PREFLIGHT_NO_TARGET_MOCK",
        "scope": "No-target runner gate and authorization controls only.",
        "implementation": {
            "runner_sha256": sha256(RUNNER),
            "remote_probe_sha256": sha256(REMOTE_PROBE),
            "validator_sha256": sha256(Path(__file__).resolve()),
            "protocol_sha256": sha256(PROTOCOL),
            "python": sys.version,
        },
        "checks": checks,
        "target_accessed": False,
        "execution_authorized": False,
        "interpretation_limits": [
            "This validation used local artificial payloads and never invoked SSH.",
            "It does not prove DK-2500 interface availability or authorize target access.",
        ],
    }
    atomic_json(output, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
