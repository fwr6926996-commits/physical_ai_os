#!/usr/bin/env python3
"""Local supervisor for one authorized D2-PREFLIGHT or a no-target fixture control."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "PHASE4_THERMAL_D2_PREFLIGHT_PROTOCOL_20261013.md"
REMOTE_PROBE = HERE / "phase4_thermal_d2_remote_probe.py"
PROTOCOL_ID = "P4-DK2500-THERMAL-D2-PREFLIGHT-001"
PROTOCOL_VERSION = "0.1"
STAGE = "D2_PREFLIGHT"
TARGET = "hepintel@192.168.77.2"
TIMEOUT_SECONDS = 30.0
THERMAL_STOP_C = 100.0
EXPECTED_IDENTITY = {
    "hostname": "hepintelpc",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 225U",
    "os_pretty_name": "Ubuntu 24.04.4 LTS",
    "kernel": "6.17.0-35-generic",
    "python_version": "3.12.3",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--authorization-file", type=Path)
    parser.add_argument("--ssh-key", type=Path)
    parser.add_argument(
        "--test-fixture",
        type=Path,
        help="No-target mock payload. Mutually exclusive with authorization and SSH.",
    )
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


def validate_authorization(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    if args.authorization_file is None:
        raise RuntimeError("Target D2-PREFLIGHT requires an explicit one-attempt authorization")
    if args.ssh_key is None:
        raise RuntimeError("Target D2-PREFLIGHT requires the dedicated SSH key path")
    path = args.authorization_file.resolve()
    authorization = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "stage": STAGE,
        "target": TARGET,
        "timeout_seconds": TIMEOUT_SECONDS,
        "status": "AUTHORIZED_FOR_ONE_ATTEMPT",
        "automatic_retry": False,
        "runner_sha256": sha256(Path(__file__).resolve()),
        "remote_probe_sha256": sha256(REMOTE_PROBE),
        "protocol_sha256": sha256(PROTOCOL_PATH),
    }
    for key, expected in required.items():
        if authorization.get(key) != expected:
            raise RuntimeError(
                f"Authorization mismatch for {key}: "
                f"{authorization.get(key)!r} != {expected!r}"
            )
    return path, authorization


def identity_checks(payload: dict[str, Any]) -> dict[str, Any]:
    actual = payload.get("identity", {})
    return {
        key: {"expected": expected, "actual": actual.get(key), "pass": actual.get(key) == expected}
        for key, expected in EXPECTED_IDENTITY.items()
    }


def evaluate_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    identity = identity_checks(payload)
    for key, check in identity.items():
        if not check["pass"]:
            reasons.append(f"IDENTITY_MISMATCH:{key}")
    boot_id = payload.get("identity", {}).get("boot_id")
    uptime = payload.get("identity", {}).get("uptime_seconds")
    if not boot_id:
        reasons.append("BOOT_ID_MISSING")
    if not isinstance(uptime, (int, float)):
        reasons.append("UPTIME_MISSING_OR_UNPARSEABLE")

    groups = payload.get("throttle_groups")
    if not isinstance(groups, list) or not groups:
        reasons.append("NO_THROTTLE_GROUP")
        groups = []
    incomplete_groups = [
        group.get("base_path") for group in groups if not bool(group.get("complete"))
    ]
    if incomplete_groups:
        reasons.append("INCOMPLETE_THROTTLE_GROUP")

    temperature = payload.get("temperature", {})
    package_count = temperature.get("package_sensor_count")
    if not isinstance(package_count, int) or package_count < 1:
        reasons.append("NO_CPU_PACKAGE_TEMPERATURE")
    max_sensor_c = temperature.get("max_sensor_c")
    if not isinstance(max_sensor_c, (int, float)):
        reasons.append("NO_READABLE_TEMPERATURE")
    elif float(max_sensor_c) >= THERMAL_STOP_C:
        reasons.append("THERMAL_ABNORMAL_STATE")

    frequency = payload.get("frequency", {})
    readable_frequency = frequency.get("readable_path_count")
    if not isinstance(readable_frequency, int) or readable_frequency < 1:
        reasons.append("NO_READABLE_CPU_FREQUENCY")

    expected_actions = {
        "target_file_created": False,
        "openvino_or_model_accessed": False,
        "load_generated": False,
        "system_configuration_changed": False,
        "sampling_loop_used": False,
    }
    actions = payload.get("actions", {})
    action_checks = {
        key: {"expected": expected, "actual": actions.get(key), "pass": actions.get(key) is expected}
        for key, expected in expected_actions.items()
    }
    for key, check in action_checks.items():
        if not check["pass"]:
            reasons.append(f"PROTECTED_BOUNDARY_VIOLATION:{key}")

    checks = {
        "identity": identity,
        "boot_id_present": bool(boot_id),
        "uptime_present": isinstance(uptime, (int, float)),
        "throttle_group_count": len(groups),
        "incomplete_throttle_groups": incomplete_groups,
        "package_sensor_count": package_count,
        "max_sensor_c": max_sensor_c,
        "thermal_stop_c": THERMAL_STOP_C,
        "frequency_online_cpu_count": frequency.get("online_cpu_count"),
        "frequency_readable_path_count": readable_frequency,
        "frequency_coverage_ratio": frequency.get("coverage_ratio"),
        "reported_read_errors": payload.get("read_errors", []),
        "protected_actions": action_checks,
    }
    return reasons, checks


def write_text_exclusive(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)


def execute_target(ssh_key: Path) -> tuple[list[str], list[str], int | None, bool, str | None]:
    command = [
        "/usr/bin/ssh",
        "-i",
        str(ssh_key.resolve()),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        TARGET,
        "/usr/bin/python3",
        "-",
    ]
    probe_source = REMOTE_PROBE.read_text(encoding="utf-8")
    try:
        completed = subprocess.run(
            command,
            input=probe_source,
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        return command, [completed.stdout, completed.stderr], completed.returncode, False, None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return command, [stdout, stderr], None, True, f"TimeoutExpired: {exc}"


def main() -> int:
    args = arguments()
    fixture_mode = args.test_fixture is not None
    if fixture_mode:
        if args.authorization_file is not None or args.ssh_key is not None:
            raise RuntimeError("Fixture mode must not receive authorization or SSH arguments")
        authorization_path = None
        command = ["MOCK_FIXTURE", str(args.test_fixture.resolve())]
        stdout = args.test_fixture.resolve().read_text(encoding="utf-8")
        stderr = ""
        returncode: int | None = 0
        timeout = False
        execution_error = None
        target_accessed = False
    else:
        authorization_path, _ = validate_authorization(args)
        command, streams, returncode, timeout, execution_error = execute_target(args.ssh_key)
        stdout, stderr = streams
        target_accessed = True

    evidence_root = args.evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_dir = evidence_root / args.run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    write_text_exclusive(run_dir / "remote_stdout.txt", stdout)
    write_text_exclusive(run_dir / "remote_stderr.txt", stderr)
    safe_command = ["<DEDICATED_DK2500_KEY>" if item.endswith("id_ed25519_dk2500") else item for item in command]
    atomic_json(run_dir / "command.json", {"argv": safe_command})

    payload = None
    parse_error = None
    if returncode == 0 and not timeout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            parse_error = f"JSONDecodeError: {exc}"

    if timeout:
        reasons = ["SSH_OR_PROBE_TIMEOUT"]
        checks: dict[str, Any] = {}
    elif returncode != 0:
        reasons = ["SSH_OR_REMOTE_PROBE_FAILED"]
        checks = {}
    elif payload is None:
        reasons = ["REMOTE_PAYLOAD_INVALID_JSON"]
        checks = {}
    else:
        reasons, checks = evaluate_payload(payload)

    status = "PREFLIGHT_PASS_REVIEW_PENDING" if not reasons else "PREFLIGHT_FAIL_REVIEW_REQUIRED"
    if fixture_mode:
        status = "MOCK_" + status
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "stage": STAGE,
        "classification": "MOCK_CONTROL_FLOW_ONLY" if fixture_mode else "EXPLORATORY_TARGET_PREFLIGHT",
        "status": status,
        "hard_fail_reasons": reasons,
        "configuration": {
            "target": None if fixture_mode else TARGET,
            "timeout_seconds": TIMEOUT_SECONDS,
            "thermal_stop_c": THERMAL_STOP_C,
            "automatic_retry": False,
            "one_shot": True,
        },
        "implementation": {
            "runner_sha256": sha256(Path(__file__).resolve()),
            "remote_probe_sha256": sha256(REMOTE_PROBE),
            "protocol_sha256": sha256(PROTOCOL_PATH),
            "authorization_sha256": None
            if authorization_path is None
            else sha256(authorization_path),
            "fixture_sha256": None
            if not fixture_mode
            else sha256(args.test_fixture.resolve()),
        },
        "target_accessed": target_accessed,
        "remote_returncode": returncode,
        "timeout": timeout,
        "execution_error": execution_error,
        "payload_parse_error": parse_error,
        "checks": checks,
        "payload": payload,
        "evidence_files": {
            "remote_stdout": "remote_stdout.txt",
            "remote_stderr": "remote_stderr.txt",
            "command": "command.json",
        },
        "interpretation_limits": [
            "A passing target preflight proves current interface readability only, not idle stability or thermal behavior.",
            "Instantaneous temperature, frequency and counters are diagnostic snapshots only.",
            "A mock result never authorizes or describes DK-2500.",
        ],
    }
    atomic_json(run_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if not reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
