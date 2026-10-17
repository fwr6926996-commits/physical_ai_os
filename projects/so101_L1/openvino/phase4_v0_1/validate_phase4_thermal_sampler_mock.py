#!/usr/bin/env python3
"""Run the human-triggered, no-hardware D1 controls for the thermal sampler."""

from __future__ import annotations

import argparse
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
SAMPLER = HERE / "phase4_thermal_sampler.py"
PROTOCOL_ID = "P4-DK2500-THERMAL-D1-MOCK-001"
PROTOCOL_VERSION = "0.1"


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


def throttle_values(cpu: int, count: int, total_ms: int, max_ms: int) -> dict[str, int]:
    prefix = f"/sys/devices/system/cpu/cpu{cpu}/thermal_throttle/package_throttle"
    return {
        f"{prefix}_count": count,
        f"{prefix}_total_time_ms": total_ms,
        f"{prefix}_max_time_ms": max_ms,
    }


def sample(elapsed_s: float, count: int, total_ms: int, max_ms: int, temp_c: float) -> dict[str, Any]:
    throttle = {}
    for cpu in (0, 1):
        throttle.update(throttle_values(cpu, count, total_ms, max_ms))
    return {
        "elapsed_s": elapsed_s,
        "throttle": throttle,
        "temperature_c": {"coretemp:Package id 0": temp_c},
    }


def run_fixture(
    root: Path,
    name: str,
    sequence: list[dict[str, Any]],
    expected_status: str,
    expected_returncode: int,
) -> dict[str, Any]:
    fixture = root / f"{name}.json"
    fixture.write_text(json.dumps(sequence, indent=2) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        str(SAMPLER),
        "--run-id",
        name,
        "--evidence-root",
        str(root / "evidence"),
        "--test-fixture-sequence",
        str(fixture),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=5)
    if completed.returncode != expected_returncode:
        raise AssertionError(
            f"{name}: return code {completed.returncode} != {expected_returncode}; "
            f"stderr={completed.stderr!r}"
        )
    result_path = root / "evidence" / name / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["status"] != expected_status:
        raise AssertionError(
            f"{name}: {result['status']!r} != {expected_status!r}; stderr={completed.stderr!r}"
        )
    return {
        "returncode": completed.returncode,
        "status": result["status"],
        "sample_count": result["sample_count"],
        "target_accessed": result["target_accessed"],
        "interface_first": result["interface_first"],
        "change_summary": result["throttle_change_summary"],
    }


def target_mode_guard(root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SAMPLER),
        "--run-id",
        "forbidden_target_mode",
        "--evidence-root",
        str(root / "evidence"),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=5)
    expected = "--test-fixture-sequence"
    if completed.returncode == 0 or expected not in completed.stderr:
        raise AssertionError(
            f"D1 target-mode guard failed: rc={completed.returncode}, "
            f"stderr={completed.stderr!r}"
        )
    return {
        "returncode_nonzero": True,
        "required_fixture_error_present": True,
        "evidence_directory_created": (root / "evidence" / "forbidden_target_mode").exists(),
    }


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite validation evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase4_thermal_d1_mock_") as temporary:
        root = Path(temporary)
        pass_case = run_fixture(
            root,
            "mock_pass",
            [sample(0, 10, 100, 5, 40), sample(1, 12, 108, 6, 91)],
            "PASS_MOCK_THERMAL_SAMPLER",
            0,
        )
        summary = pass_case["change_summary"]
        expected_deltas = {
            "throttle_count": 2,
            "throttle_total_time_ms": 8,
            "throttle_max_time_ms": 1,
        }
        for kind, expected in expected_deltas.items():
            if summary[kind]["max_path_delta"] != expected:
                raise AssertionError(f"{kind} delta was not preserved")
            if summary[kind]["paths_compared"] != 2:
                raise AssertionError(f"{kind} duplicate paths were not preserved")
            if summary[kind]["sum_intentionally_omitted"] is not True:
                raise AssertionError(f"{kind} incorrectly permits summing duplicate paths")

        incomplete = sample(0, 10, 100, 5, 40)
        missing_path = next(
            path for path in incomplete["throttle"] if path.endswith("_max_time_ms")
        )
        del incomplete["throttle"][missing_path]
        incomplete_case = run_fixture(
            root,
            "mock_incomplete",
            [incomplete],
            "MOCK_INTERFACE_INCOMPLETE",
            1,
        )
        thermal_stop_case = run_fixture(
            root,
            "mock_thermal_stop",
            [sample(0, 10, 100, 5, 101)],
            "MOCK_THERMAL_STOP",
            1,
        )
        guard = target_mode_guard(root)

    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "status": "PASS_THERMAL_D1_MOCK_VALIDATION",
        "scope": "Artificial-input parser, evidence-boundary and target-mode guard only.",
        "implementation": {
            "sampler_sha256": sha256(SAMPLER),
            "validator_sha256": sha256(Path(__file__).resolve()),
            "python": sys.version,
        },
        "checks": {
            "known_delta_and_duplicate_path_sequence": pass_case,
            "missing_field_rejected": incomplete_case,
            "thermal_stop_classified": thermal_stop_case,
            "target_mode_unavailable": guard,
        },
        "target_accessed": False,
        "execution_authorized": False,
        "interpretation_limits": [
            "D1 used artificial data and did not access DK-2500, sysfs, OpenVINO or a model.",
            "D1 does not authorize D2, Stability, deployment, real-time or safety claims.",
        ],
    }
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    temporary_output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_output, output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
