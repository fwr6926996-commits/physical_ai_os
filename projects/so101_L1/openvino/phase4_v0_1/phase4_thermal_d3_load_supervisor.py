#!/usr/bin/env python3
"""D3-LOAD evidence supervisor; target execution remains disabled for mock review."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import phase4_thermal_d2_idle_remote_sampler as sampler
import phase4_thermal_d2_idle_supervisor as d2


HERE = Path(__file__).resolve().parent
PROTOCOL_PATH = HERE / "PHASE4_THERMAL_D3_LOAD_MOCK_PROTOCOL_20261014.md"
TARGET_PROTOCOL_PATH = HERE / "PHASE4_THERMAL_D3_LOAD_TARGET_PROTOCOL_20261014.md"
REMOTE_SAMPLER_PATH = HERE / "phase4_thermal_d2_idle_remote_sampler.py"
PROTOCOL_ID = "P4-DK2500-THERMAL-D3-LOAD-MOCK-001"
PROTOCOL_VERSION = "0.1"
TARGET_PROTOCOL_ID = "P4-DK2500-THERMAL-D3-LOAD-001"
TARGET_PROTOCOL_VERSION = "0.1"
TARGET = "hepintel@192.168.77.2"
TARGET_STAGE = "D3_LOAD"
EXPECTED_SSH_KEY = Path("/home/lucas/.ssh/id_ed25519_dk2500")
STARTUP_SECONDS = 30.0
WATCHDOG_SECONDS = 15.0
OVERALL_SECONDS = 660.0
TARGET_EXECUTION_ENABLED = True


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--test-fixture-sequence", type=Path)
    parser.add_argument("--authorization-file", type=Path)
    parser.add_argument("--ssh-key", type=Path)
    return parser.parse_args()


def expected_configuration() -> dict[str, Any]:
    return {
        "pre_observation_seconds": sampler.PRE_OBSERVATION_SECONDS,
        "formal_observation_seconds": sampler.FORMAL_OBSERVATION_SECONDS,
        "interval_seconds": sampler.INTERVAL_SECONDS,
        "thermal_stop_c": sampler.THERMAL_STOP_C,
        "expected_sample_count": sampler.EXPECTED_SAMPLE_COUNT,
        "load_workers": sampler.D3_LOAD_WORKERS,
        "pre_busy_limit_percent": sampler.PRE_BUSY_LIMIT_PERCENT,
        "formal_busy_min_percent": sampler.D3_FORMAL_BUSY_MIN_PERCENT,
        "low_busy_limit_percent": sampler.D3_LOW_BUSY_LIMIT_PERCENT,
        "low_busy_windows": sampler.D3_LOW_BUSY_WINDOWS,
        "entry_package_max_c": sampler.D3_ENTRY_PACKAGE_MAX_C,
        "entry_sensor_max_c": sampler.D3_ENTRY_SENSOR_MAX_C,
    }


def throttle_values(sample: dict[str, Any]) -> dict[tuple[str, str], int]:
    values: dict[tuple[str, str], int] = {}
    for group in sample.get("throttle_groups", []):
        base = group.get("base_path")
        fields = group.get("values", {})
        if isinstance(base, str) and isinstance(fields, dict):
            for field in d2.REQUIRED_THROTTLE_FIELDS:
                value = fields.get(field)
                if isinstance(value, int):
                    values[(base, field)] = value
    return values


def validate_authorization(args: argparse.Namespace) -> Path:
    if args.authorization_file is None or args.ssh_key is None:
        raise RuntimeError("D3-LOAD target mode requires authorization and dedicated SSH key")
    if args.ssh_key.resolve() != EXPECTED_SSH_KEY:
        raise RuntimeError("D3-LOAD received an unexpected SSH key path")
    path = args.authorization_file.resolve()
    authorization = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "protocol_id": TARGET_PROTOCOL_ID,
        "protocol_version": TARGET_PROTOCOL_VERSION,
        "run_id": args.run_id,
        "stage": TARGET_STAGE,
        "target": TARGET,
        "startup_seconds": STARTUP_SECONDS,
        "watchdog_seconds": WATCHDOG_SECONDS,
        "overall_seconds": OVERALL_SECONDS,
        "status": "AUTHORIZED_FOR_ONE_ATTEMPT",
        "automatic_retry": False,
        "supervisor_sha256": d2.sha256(Path(__file__).resolve()),
        "remote_sampler_sha256": d2.sha256(REMOTE_SAMPLER_PATH),
        "protocol_sha256": d2.sha256(TARGET_PROTOCOL_PATH),
    }
    for key, expected in required.items():
        if authorization.get(key) != expected:
            raise RuntimeError(f"Authorization mismatch for {key}: {authorization.get(key)!r} != {expected!r}")
    return path


def classify(events: list[dict[str, Any]], enforce_target_contract: bool = False) -> dict[str, Any]:
    reasons: list[str] = []
    identity = events[0] if events and events[0].get("type") == "runtime_identity" else {}
    if not identity:
        reasons.append("FIRST_EVENT_NOT_RUNTIME_IDENTITY")
    if identity.get("configuration") != expected_configuration():
        reasons.append("CONFIGURATION_MISMATCH")
    expected_actions = {
        "target_file_created": False,
        "openvino_or_model_accessed": False,
        "deliberate_load_generated": True,
        "system_configuration_changed": False,
    }
    if identity.get("actions") != expected_actions:
        reasons.append("PROTECTED_ACTION_DECLARATION_INVALID")
    if identity.get("startup_errors"):
        reasons.append("STARTUP_ERRORS_PRESENT")
    signature = identity.get("inventory_signature", {})
    boot_id = identity.get("boot_id")
    if enforce_target_contract:
        actual_identity = identity.get("identity", {})
        for field, expected in sampler.EXPECTED_TARGET_IDENTITY.items():
            if actual_identity.get(field) != expected:
                reasons.append(f"TARGET_IDENTITY_MISMATCH:{field}")
        if signature.get("throttle_bases") != sorted(sampler.EXPECTED_THROTTLE_BASES):
            reasons.append("TARGET_THROTTLE_INVENTORY_MISMATCH")
        if signature.get("frequency_paths") != sorted(sampler.EXPECTED_FREQUENCY_PATHS):
            reasons.append("TARGET_FREQUENCY_INVENTORY_MISMATCH")

    samples = [event for event in events if event.get("type") == "sample"]
    load_started = [event for event in events if event.get("type") == "load_started"]
    load_stopped = [event for event in events if event.get("type") == "load_stopped"]
    terminal_types = {
        "load_observation_completed",
        "load_control_invalid",
        "precondition_not_met",
        "thermal_stop",
        "interface_or_timebase_failure",
        "supervisor_or_transport_failure",
    }
    terminal = next((event for event in reversed(events) if event.get("type") in terminal_types), None)
    pre_busy: list[float] = []
    formal_busy: list[float] = []
    consecutive_low = 0
    first_detected: tuple[str, int, str] | None = None
    previous: dict[str, Any] | None = None
    max_sensor_c: float | None = None

    for index, sample in enumerate(samples):
        if sample.get("sequence") != index:
            reasons.append(f"SEQUENCE_MISMATCH:{index}")
            first_detected = first_detected or ("interface_or_timebase_failure", index, "SEQUENCE_MISMATCH")
        if sample.get("boot_id") != boot_id or sample.get("inventory_signature") != signature:
            reasons.append(f"IDENTITY_OR_INVENTORY_CHANGED:{index}")
            first_detected = first_detected or ("interface_or_timebase_failure", index, "IDENTITY_OR_INVENTORY_CHANGED")
        if sample.get("read_errors"):
            reasons.append(f"READ_ERRORS_PRESENT:{index}")
            first_detected = first_detected or ("interface_or_timebase_failure", index, "READ_OR_PARSE_ERROR")
        duration = sample.get("sample_read_duration_ms")
        lag = sample.get("schedule_lag_ms")
        if not isinstance(duration, (int, float)) or duration >= 5000 or not isinstance(lag, (int, float)) or lag >= 5000:
            reasons.append(f"SAMPLING_TIME_INVALID:{index}")
            first_detected = first_detected or ("interface_or_timebase_failure", index, "SAMPLING_TIME_INVALID")
        current_max = sample.get("temperature", {}).get("max_sensor_c")
        if isinstance(current_max, (int, float)):
            max_sensor_c = float(current_max) if max_sensor_c is None else max(max_sensor_c, float(current_max))
            if current_max >= sampler.THERMAL_STOP_C:
                first_detected = first_detected or ("thermal_stop", index, "THERMAL_STOP")
        else:
            reasons.append(f"TEMPERATURE_MISSING:{index}")
        if previous is not None:
            try:
                busy = sampler.busy_percent(previous["proc_stat"], sample["proc_stat"])
            except (KeyError, TypeError, ValueError) as exc:
                reasons.append(f"CPU_BUSY_INVALID:{index}:{exc}")
                first_detected = first_detected or ("interface_or_timebase_failure", index, "CPU_BUSY_INVALID")
                busy = None
            if busy is not None:
                if abs(float(sample.get("interval_busy_percent")) - busy) > 1e-9:
                    reasons.append(f"CPU_BUSY_RECOMPUTE_MISMATCH:{index}")
                if 1 <= index <= 6:
                    pre_busy.append(busy)
                elif index >= 7:
                    formal_busy.append(busy)
                    if len(formal_busy) > 2:
                        consecutive_low = consecutive_low + 1 if busy < sampler.D3_LOW_BUSY_LIMIT_PERCENT else 0
                        if consecutive_low >= sampler.D3_LOW_BUSY_WINDOWS:
                            first_detected = first_detected or ("load_control_invalid", index, "SUSTAINED_LOAD_BUSY_BELOW_MINIMUM")
            before, after = throttle_values(previous), throttle_values(sample)
            if set(before) != set(after) or any(after[key] < before[key] for key in set(before) & set(after)):
                reasons.append(f"THROTTLE_INTERFACE_OR_COUNTER_INVALID:{index}")
                first_detected = first_detected or ("interface_or_timebase_failure", index, "THROTTLE_INTERFACE_OR_COUNTER_INVALID")
        previous = sample

    if len(samples) >= 7:
        boundary = samples[6]
        first = throttle_values(samples[0])
        last_pre = throttle_values(boundary)
        package = [row.get("current_c") for row in boundary.get("temperature", {}).get("sensors", []) if row.get("is_cpu_package") and isinstance(row.get("current_c"), (int, float))]
        if len(pre_busy) == 6 and sum(pre_busy) / 6 > sampler.PRE_BUSY_LIMIT_PERCENT:
            first_detected = first_detected or ("precondition_not_met", 6, "PRE_OBSERVATION_AVERAGE_BUSY_EXCEEDED")
        elif any(last_pre.get(key, first[key]) > first[key] for key in first):
            first_detected = first_detected or ("precondition_not_met", 6, "PRE_OBSERVATION_THROTTLE_INCREMENT")
        elif not package or max(package) > sampler.D3_ENTRY_PACKAGE_MAX_C:
            first_detected = first_detected or ("precondition_not_met", 6, "ENTRY_PACKAGE_TEMPERATURE_EXCEEDED")
        elif boundary["temperature"]["max_sensor_c"] > sampler.D3_ENTRY_SENSOR_MAX_C:
            first_detected = first_detected or ("precondition_not_met", 6, "ENTRY_SENSOR_TEMPERATURE_EXCEEDED")

    if first_detected is None and len(samples) == sampler.EXPECTED_SAMPLE_COUNT:
        average = sum(formal_busy) / len(formal_busy) if formal_busy else 0.0
        if average < sampler.D3_FORMAL_BUSY_MIN_PERCENT:
            first_detected = ("load_control_invalid", 126, "FORMAL_AVERAGE_BUSY_BELOW_MINIMUM")
        else:
            first_detected = ("load_observation_completed", 126, "COMPLETE")
    if (
        terminal is not None
        and terminal.get("type") == "load_control_invalid"
        and terminal.get("reason") == "LOAD_WORKER_EXITED"
    ):
        first_detected = (
            "load_control_invalid",
            terminal.get("sequence", len(samples) - 1),
            "LOAD_WORKER_EXITED",
        )
    if first_detected is None:
        first_detected = ("interface_or_timebase_failure", len(samples) - 1, "SAMPLE_COUNT_INCOMPLETE")

    detected_type, detected_sequence, detected_reason = first_detected
    if terminal is None or terminal.get("type") != detected_type:
        reasons.append(f"TERMINAL_EVENT_MISMATCH:{None if terminal is None else terminal.get('type')}!={detected_type}")
    if load_started:
        if len(load_started) != 1 or load_started[0].get("worker_count") != sampler.D3_LOAD_WORKERS:
            reasons.append("LOAD_START_EVIDENCE_INVALID")
        valid_stop = (
            len(load_stopped) == 1
            and load_stopped[0].get("started") == sampler.D3_LOAD_WORKERS
            and load_stopped[0].get("alive") == 0
        )
        if not valid_stop:
            reasons.append("LOAD_STOP_EVIDENCE_INVALID")
        elif detected_type == "load_observation_completed":
            records = load_stopped[0].get("worker_records", [])
            exits = load_stopped[0].get("exits", {})
            if len(records) != sampler.D3_LOAD_WORKERS or any(code != 0 for code in exits.values()):
                reasons.append("LOAD_WORKER_COMPLETION_EVIDENCE_INVALID")
    status_map = {
        "load_observation_completed": "MOCK_LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING",
        "load_control_invalid": "MOCK_LOAD_CONTROL_INVALID_REVIEW_REQUIRED",
        "precondition_not_met": "MOCK_PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "thermal_stop": "MOCK_THERMAL_STOP_REVIEW_REQUIRED",
        "interface_or_timebase_failure": "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
        "supervisor_or_transport_failure": "MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED",
    }
    changes, summary = d2.throttle_deltas(samples[0] if samples else None, samples[-1] if samples else None)
    return {
        "status": status_map[detected_type],
        "classification_reasons": reasons,
        "sample_count": len(samples),
        "detected_terminal": {"type": detected_type, "sequence": detected_sequence, "reason": detected_reason},
        "pre_average_busy_percent": sum(pre_busy) / len(pre_busy) if pre_busy else None,
        "formal_average_busy_percent": sum(formal_busy) / len(formal_busy) if formal_busy else None,
        "max_sensor_c": max_sensor_c,
        "load_started": load_started,
        "load_stopped": load_stopped,
        "throttle_changes": changes,
        "throttle_change_summary": summary,
    }


def main() -> int:
    args = arguments()
    fixture_mode = args.test_fixture_sequence is not None
    if fixture_mode:
        if args.authorization_file is not None or args.ssh_key is not None:
            raise RuntimeError("Fixture mode must not receive authorization or SSH arguments")
        fixture = args.test_fixture_sequence.resolve()
        events = d2.load_jsonl(fixture)
        raw = fixture.read_text(encoding="utf-8")
        stderr = ""
        command = ["MOCK_FIXTURE", str(fixture)]
        stream_control = {"returncode": 0, "timeout_reason": None, "recovery": None}
        authorization_path = None
        target_accessed = False
    else:
        if not TARGET_EXECUTION_ENABLED:
            raise RuntimeError("D3-LOAD target execution is disabled pending target protocol review")
        authorization_path = validate_authorization(args)
        fixture = None
        command = [
            "/usr/bin/ssh", "-i", str(args.ssh_key.resolve()),
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            TARGET, "/usr/bin/python3", "-u", "-", "--load-workers", "12",
        ]
        streamed = d2.consume_process(
            command,
            REMOTE_SAMPLER_PATH.read_text(encoding="utf-8"),
            STARTUP_SECONDS,
            WATCHDOG_SECONDS,
            OVERALL_SECONDS,
        )
        raw, stderr = streamed["stdout"], streamed["stderr"]
        events, parse_errors = d2.parse_jsonl_text_tolerant(raw)
        stream_control = {
            "returncode": streamed["returncode"],
            "timeout_reason": streamed["timeout_reason"],
            "recovery": streamed["recovery"],
            "parse_errors": parse_errors,
            "raw_stdout_bytes": len(raw.encode("utf-8")),
        }
        if streamed["timeout_reason"] is not None or parse_errors or not events:
            last_sequence = max((event.get("sequence", -1) for event in events if event.get("type") == "sample"), default=-1)
            events.append({"type": "supervisor_or_transport_failure", "sequence": last_sequence, "reason": streamed["timeout_reason"] or ("STREAM_JSON_INVALID" if parse_errors else "NO_REMOTE_EVENT")})
        target_accessed = True
    analysis = classify(events, enforce_target_contract=not fixture_mode)
    if not fixture_mode:
        analysis["status"] = analysis["status"].removeprefix("MOCK_")
        expected_returncodes = {
            "load_observation_completed": 0,
            "interface_or_timebase_failure": 2,
            "thermal_stop": 3,
            "precondition_not_met": 4,
            "load_control_invalid": 4,
        }
        expected_returncode = expected_returncodes.get(analysis["detected_terminal"]["type"])
        if stream_control["timeout_reason"] is None and expected_returncode is not None and stream_control["returncode"] != expected_returncode:
            analysis["classification_reasons"].append(f"REMOTE_RETURNCODE_MISMATCH:{stream_control['returncode']}!={expected_returncode}")
            analysis["status"] = "SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED"
    root = args.evidence_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / args.run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    (run_dir / "raw_events.jsonl").write_text(raw, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    safe_command = list(command)
    if "-i" in safe_command:
        safe_command[safe_command.index("-i") + 1] = "<DEDICATED_DK2500_KEY>"
    d2.atomic_json(run_dir / "command.json", {"argv": safe_command})
    protocol_id = PROTOCOL_ID if fixture_mode else TARGET_PROTOCOL_ID
    protocol_version = PROTOCOL_VERSION if fixture_mode else TARGET_PROTOCOL_VERSION
    protocol_path = PROTOCOL_PATH if fixture_mode else TARGET_PROTOCOL_PATH
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": protocol_id,
        "protocol_version": protocol_version,
        "run_id": args.run_id,
        "stage": "D3_LOAD_MOCK" if fixture_mode else TARGET_STAGE,
        **analysis,
        "configuration": expected_configuration(),
        "implementation": {
            "supervisor_sha256": d2.sha256(Path(__file__).resolve()),
            "remote_sampler_sha256": d2.sha256(REMOTE_SAMPLER_PATH),
            "protocol_sha256": d2.sha256(protocol_path),
            "fixture_sha256": None if fixture is None else d2.sha256(fixture),
            "authorization_sha256": None if authorization_path is None else d2.sha256(authorization_path),
        },
        "target_accessed": target_accessed,
        "execution_authorized": not fixture_mode,
        "automatic_retry": False,
        "stream_control": stream_control,
    }
    d2.atomic_json(run_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    completion = "MOCK_LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING" if fixture_mode else "LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING"
    return 0 if analysis["status"] == completion and not analysis["classification_reasons"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)
