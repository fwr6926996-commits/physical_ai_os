#!/usr/bin/env python3
"""Local D2-IDLE evidence supervisor with a no-target fixture mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import selectors
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import phase4_thermal_d2_idle_remote_sampler as sampler


HERE = Path(__file__).resolve().parent
MOCK_PROTOCOL_PATH = HERE / "PHASE4_THERMAL_D2_IDLE_MOCK_PROTOCOL_V0_3_20261014.md"
TARGET_PROTOCOL_PATH = HERE / "PHASE4_THERMAL_D2_IDLE_TARGET_PROTOCOL_20261014.md"
REMOTE_SAMPLER_PATH = HERE / "phase4_thermal_d2_idle_remote_sampler.py"
MOCK_PROTOCOL_ID = "P4-DK2500-THERMAL-D2-IDLE-MOCK-001"
MOCK_PROTOCOL_VERSION = "0.3"
TARGET_PROTOCOL_ID = "P4-DK2500-THERMAL-D2-IDLE-001"
TARGET_PROTOCOL_VERSION = "0.1"
TARGET_STAGE = "D2_IDLE"
TARGET = "hepintel@192.168.77.2"
EXPECTED_SSH_KEY = Path("/home/lucas/.ssh/id_ed25519_dk2500")
STARTUP_SECONDS = 30.0
WATCHDOG_SECONDS = 15.0
OVERALL_SECONDS = 660.0
TARGET_EXECUTION_ENABLED = True
REQUIRED_THROTTLE_FIELDS = {
    "throttle_count",
    "throttle_total_time_ms",
    "throttle_max_time_ms",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--test-fixture-sequence", type=Path)
    parser.add_argument("--test-stream-fixture-sequence", type=Path)
    parser.add_argument("--test-stream-stall-after-lines", type=int, default=0)
    parser.add_argument("--test-stream-partial-line", type=int, default=0)
    parser.add_argument("--test-watchdog-seconds", type=float, default=15.0)
    parser.add_argument("--authorization-file", type=Path)
    parser.add_argument("--ssh-key", type=Path)
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
        raise RuntimeError("Target D2-IDLE requires an explicit one-attempt authorization")
    if args.ssh_key is None:
        raise RuntimeError("Target D2-IDLE requires the dedicated SSH key path")
    if args.ssh_key.resolve() != EXPECTED_SSH_KEY:
        raise RuntimeError(
            f"Unexpected SSH key path: {args.ssh_key.resolve()} != {EXPECTED_SSH_KEY}"
        )
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
        "supervisor_sha256": sha256(Path(__file__).resolve()),
        "remote_sampler_sha256": sha256(REMOTE_SAMPLER_PATH),
        "protocol_sha256": sha256(TARGET_PROTOCOL_PATH),
    }
    for key, expected in required.items():
        if authorization.get(key) != expected:
            raise RuntimeError(
                f"Authorization mismatch for {key}: "
                f"{authorization.get(key)!r} != {expected!r}"
            )
    return path, authorization


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        events.append(value)
    if not events:
        raise ValueError("fixture sequence contains no events")
    return events


def parse_jsonl_text_tolerant(raw: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    lines = raw.splitlines(keepends=True)
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if not line.endswith(("\n", "\r")):
            errors.append(f"INCOMPLETE_JSONL_TAIL:{line_number}")
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON_DECODE_ERROR:{line_number}:{exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"JSONL_LINE_NOT_OBJECT:{line_number}")
            continue
        events.append(value)
    return events, errors


def consume_process(
    command: list[str],
    stdin_text: str | None,
    startup_seconds: float,
    watchdog_seconds: float,
    overall_seconds: float,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        bufsize=0,
    )
    if stdin_text is not None:
        assert process.stdin is not None
        process.stdin.write(stdin_text.encode("utf-8"))
        process.stdin.close()
    assert process.stdout is not None
    assert process.stderr is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout_bytes = bytearray()
    stderr_bytes = bytearray()
    started = time.monotonic()
    last_complete_line = started
    received_line = False
    timeout_reason = None
    recovery = None
    while True:
        now = time.monotonic()
        if now - started >= overall_seconds:
            timeout_reason = "OVERALL_TIMEOUT"
            break
        if not received_line and now - started >= startup_seconds:
            timeout_reason = "STARTUP_TIMEOUT"
            break
        if received_line and now - last_complete_line >= watchdog_seconds:
            timeout_reason = "PROGRESS_WATCHDOG_TIMEOUT"
            break
        ready = selector.select(timeout=0.02)
        for key, _ in ready:
            chunk = os.read(key.fileobj.fileno(), 65536)
            if chunk:
                if key.data == "stdout":
                    stdout_bytes.extend(chunk)
                    if b"\n" in chunk:
                        received_line = True
                        last_complete_line = time.monotonic()
                else:
                    stderr_bytes.extend(chunk)
            else:
                try:
                    selector.unregister(key.fileobj)
                except KeyError:
                    pass
        if process.poll() is not None and not selector.get_map():
            break
    if timeout_reason is not None and process.poll() is None:
        process.terminate()
        recovery = "SIGTERM"
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            recovery = "SIGKILL"
            process.wait(timeout=5.0)
    if process.poll() is None:
        process.wait(timeout=5.0)
    stdout_remainder = process.stdout.read()
    stderr_remainder = process.stderr.read()
    if stdout_remainder:
        stdout_bytes.extend(stdout_remainder)
    if stderr_remainder:
        stderr_bytes.extend(stderr_remainder)
    selector.close()
    return {
        "command": command,
        "stdout": bytes(stdout_bytes).decode("utf-8", errors="replace"),
        "stderr": bytes(stderr_bytes).decode("utf-8", errors="replace"),
        "returncode": process.returncode,
        "timeout_reason": timeout_reason,
        "recovery": recovery,
    }


def local_stream_command(
    fixture_path: Path,
    stall_after_lines: int,
    partial_line: int,
    stall_seconds: float,
) -> list[str]:
    helper = (
        "import pathlib,sys,time\n"
        "lines=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()\n"
        "stall_after=int(sys.argv[2]); partial_line=int(sys.argv[3]); stall_seconds=float(sys.argv[4])\n"
        "for index,line in enumerate(lines,1):\n"
        " if partial_line and index==partial_line:\n"
        "  sys.stdout.write(line[:max(1,len(line)//2)]); sys.stdout.flush(); time.sleep(stall_seconds); break\n"
        " print(line,flush=True)\n"
        " if stall_after and index==stall_after: time.sleep(stall_seconds)\n"
    )
    return [
        sys.executable,
        "-u",
        "-c",
        helper,
        str(fixture_path),
        str(stall_after_lines),
        str(partial_line),
        str(stall_seconds),
    ]


def expected_configuration() -> dict[str, Any]:
    return {
        "pre_observation_seconds": sampler.PRE_OBSERVATION_SECONDS,
        "formal_observation_seconds": sampler.FORMAL_OBSERVATION_SECONDS,
        "interval_seconds": sampler.INTERVAL_SECONDS,
        "pre_busy_limit_percent": sampler.PRE_BUSY_LIMIT_PERCENT,
        "formal_busy_limit_percent": sampler.FORMAL_BUSY_LIMIT_PERCENT,
        "sustained_busy_limit_percent": sampler.SUSTAINED_BUSY_LIMIT_PERCENT,
        "sustained_busy_windows": sampler.SUSTAINED_BUSY_WINDOWS,
        "thermal_stop_c": sampler.THERMAL_STOP_C,
        "expected_sample_count": sampler.EXPECTED_SAMPLE_COUNT,
    }


def terminal_status(event_type: str | None) -> str | None:
    return {
        "completed": "MOCK_IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING",
        "idle_control_contaminated": "MOCK_IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED",
        "thermal_stop": "MOCK_THERMAL_STOP_REVIEW_REQUIRED",
        "interface_or_timebase_failure": "MOCK_INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
        "supervisor_or_transport_failure": "MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED",
    }.get(event_type)


def throttle_map(sample: dict[str, Any]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for group in sample.get("throttle_groups", []):
        base = group.get("base_path")
        values = group.get("values")
        if not isinstance(base, str) or not isinstance(values, dict):
            continue
        if set(values) == REQUIRED_THROTTLE_FIELDS and all(
            isinstance(value, int) for value in values.values()
        ):
            result[base] = values
    return result


def throttle_deltas(
    first: dict[str, Any] | None, last: dict[str, Any] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    if first is None or last is None:
        return {}, {}
    first_map = throttle_map(first)
    last_map = throttle_map(last)
    changes: dict[str, Any] = {}
    for base in sorted(set(first_map) & set(last_map)):
        for field in sorted(REQUIRED_THROTTLE_FIELDS):
            path_identity = f"{base}:{field}"
            before = first_map[base][field]
            after = last_map[base][field]
            changes[path_identity] = {
                "base_path": base,
                "kind": field,
                "before": before,
                "after": after,
                "delta": after - before,
            }
    summary: dict[str, Any] = {}
    for field in sorted(REQUIRED_THROTTLE_FIELDS):
        rows = [row for row in changes.values() if row["kind"] == field]
        deltas = [row["delta"] for row in rows]
        summary[field] = {
            "paths_compared": len(rows),
            "increment_paths": sum(delta > 0 for delta in deltas),
            "zero_delta_paths": sum(delta == 0 for delta in deltas),
            "negative_delta_paths": sum(delta < 0 for delta in deltas),
            "min_path_delta": min(deltas) if deltas else None,
            "max_path_delta": max(deltas) if deltas else None,
            "sum_intentionally_omitted": True,
        }
    return changes, summary


def classify(events: list[dict[str, Any]], enforce_target_contract: bool = False) -> dict[str, Any]:
    reasons: list[str] = []
    if events[0].get("type") != "runtime_identity":
        reasons.append("FIRST_EVENT_NOT_RUNTIME_IDENTITY")
        identity = {}
    else:
        identity = events[0]
    if enforce_target_contract:
        actual_identity = identity.get("identity", {})
        for field, expected in sampler.EXPECTED_TARGET_IDENTITY.items():
            if actual_identity.get(field) != expected:
                reasons.append(f"TARGET_IDENTITY_MISMATCH:{field}")
    expected_config = expected_configuration()
    if identity.get("configuration") != expected_config:
        reasons.append("CONFIGURATION_MISMATCH")
    if identity.get("startup_errors"):
        reasons.append("STARTUP_ERRORS_PRESENT")
    expected_actions = {
        "target_file_created": False,
        "openvino_or_model_accessed": False,
        "deliberate_load_generated": False,
        "system_configuration_changed": False,
    }
    if identity.get("actions") != expected_actions:
        reasons.append("PROTECTED_ACTION_DECLARATION_INVALID")
    expected_signature = identity.get("inventory_signature")
    if not isinstance(expected_signature, dict):
        reasons.append("INVENTORY_SIGNATURE_MISSING")
        expected_signature = {}
    if enforce_target_contract:
        if expected_signature.get("throttle_bases") != sorted(
            sampler.EXPECTED_THROTTLE_BASES
        ):
            reasons.append("TARGET_THROTTLE_INVENTORY_MISMATCH")
        if expected_signature.get("frequency_paths") != sorted(
            sampler.EXPECTED_FREQUENCY_PATHS
        ):
            reasons.append("TARGET_FREQUENCY_INVENTORY_MISMATCH")
    expected_boot_id = identity.get("boot_id")
    if not expected_boot_id:
        reasons.append("BOOT_ID_MISSING")

    terminal = events[-1] if events[-1].get("type") != "sample" else None
    samples = [event for event in events if event.get("type") == "sample"]
    if not samples:
        reasons.append("NO_SAMPLES")
    pre_busy: list[float] = []
    formal_busy: list[float] = []
    high_run = 0
    first_detected_terminal: tuple[str, int, str] | None = None
    previous: dict[str, Any] | None = None
    max_sensor_c: float | None = None

    for index, sample in enumerate(samples):
        if sample.get("sequence") != index:
            reasons.append(f"SEQUENCE_MISMATCH:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "SEQUENCE_MISMATCH",
            )
        if sample.get("boot_id") != expected_boot_id:
            reasons.append(f"BOOT_ID_CHANGED:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "BOOT_ID_CHANGED",
            )
        if sample.get("inventory_signature") != expected_signature:
            reasons.append(f"INTERFACE_INVENTORY_CHANGED:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "INTERFACE_INVENTORY_CHANGED",
            )
        if sample.get("read_errors"):
            reasons.append(f"READ_ERRORS_PRESENT:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "READ_OR_PARSE_ERROR",
            )
        duration_ms = sample.get("sample_read_duration_ms")
        if not isinstance(duration_ms, (int, float)) or duration_ms >= 5000.0:
            reasons.append(f"SAMPLE_READ_DURATION_INVALID:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "SAMPLE_READ_CONSUMED_INTERVAL",
            )
        schedule_lag_ms = sample.get("schedule_lag_ms")
        if not isinstance(schedule_lag_ms, (int, float)) or schedule_lag_ms >= 5000.0:
            reasons.append(f"SAMPLE_DEADLINE_MISSED:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "SAMPLE_DEADLINE_MISSED",
            )

        current_throttle = throttle_map(sample)
        expected_bases = set(expected_signature.get("throttle_bases", []))
        if set(current_throttle) != expected_bases:
            reasons.append(f"THROTTLE_FIELDS_INCOMPLETE:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "INCOMPLETE_THROTTLE_GROUP",
            )
        temperature = sample.get("temperature", {})
        current_max = temperature.get("max_sensor_c")
        if isinstance(current_max, (int, float)):
            max_sensor_c = float(current_max) if max_sensor_c is None else max(max_sensor_c, float(current_max))
            if float(current_max) >= sampler.THERMAL_STOP_C:
                first_detected_terminal = first_detected_terminal or (
                    "thermal_stop",
                    index,
                    "THERMAL_STOP",
                )
        else:
            reasons.append(f"TEMPERATURE_MISSING:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "TEMPERATURE_MISSING",
            )
        if temperature.get("package_sensor_count", 0) < 1:
            reasons.append(f"PACKAGE_TEMPERATURE_MISSING:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "NO_CPU_PACKAGE_TEMPERATURE",
            )
        temperature_paths = {
            row.get("input_path")
            for row in temperature.get("sensors", [])
            if row.get("current_c") is not None
        }
        if temperature_paths != set(expected_signature.get("temperature_paths", [])):
            reasons.append(f"TEMPERATURE_PATHS_INCOMPLETE:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "TEMPERATURE_PATHS_INCOMPLETE",
            )
        frequency_paths = {
            row.get("path")
            for row in sample.get("frequency", {}).get("readable", [])
            if row.get("current_mhz") is not None
        }
        if frequency_paths != set(expected_signature.get("frequency_paths", [])):
            reasons.append(f"FREQUENCY_PATHS_INCOMPLETE:{index}")
            first_detected_terminal = first_detected_terminal or (
                "interface_or_timebase_failure",
                index,
                "MISSING_CPU_FREQUENCY",
            )

        reported_busy = sample.get("interval_busy_percent")
        if previous is None:
            if reported_busy is not None:
                reasons.append("FIRST_SAMPLE_BUSY_MUST_BE_NULL")
        else:
            previous_ns = previous.get("target_monotonic_ns")
            current_ns = sample.get("target_monotonic_ns")
            if not isinstance(previous_ns, int) or not isinstance(current_ns, int) or current_ns <= previous_ns:
                reasons.append(f"MONOTONIC_TIME_REVERSED:{index}")
                first_detected_terminal = first_detected_terminal or (
                    "interface_or_timebase_failure",
                    index,
                    "MONOTONIC_TIME_REVERSED",
                )
            try:
                recomputed_busy = sampler.busy_percent(previous["proc_stat"], sample["proc_stat"])
            except (KeyError, TypeError, ValueError) as exc:
                reasons.append(f"CPU_BUSY_INVALID:{index}:{exc}")
                first_detected_terminal = first_detected_terminal or (
                    "interface_or_timebase_failure",
                    index,
                    "CPU_BUSY_INVALID",
                )
                recomputed_busy = None
            if recomputed_busy is not None:
                if not isinstance(reported_busy, (int, float)) or abs(float(reported_busy) - recomputed_busy) > 1e-9:
                    reasons.append(f"CPU_BUSY_RECOMPUTE_MISMATCH:{index}")
                    first_detected_terminal = first_detected_terminal or (
                        "interface_or_timebase_failure",
                        index,
                        "CPU_BUSY_RECOMPUTE_MISMATCH",
                    )
                if 1 <= index <= 6:
                    pre_busy.append(recomputed_busy)
                elif index >= 7:
                    formal_busy.append(recomputed_busy)
                    high_run = high_run + 1 if recomputed_busy > 20.0 else 0
                    if high_run >= 3:
                        first_detected_terminal = first_detected_terminal or (
                            "idle_control_contaminated",
                            index,
                            "SUSTAINED_FORMAL_BUSY_EXCEEDED",
                        )

            previous_throttle = throttle_map(previous)
            for base in set(previous_throttle) & set(current_throttle):
                for field in REQUIRED_THROTTLE_FIELDS:
                    if current_throttle[base][field] < previous_throttle[base][field]:
                        reasons.append(f"THROTTLE_COUNTER_DECREASED:{index}:{base}:{field}")
                        first_detected_terminal = first_detected_terminal or (
                            "interface_or_timebase_failure",
                            index,
                            "THROTTLE_COUNTER_DECREASED",
                        )
        if index == 6 and len(pre_busy) == 6 and sum(pre_busy) / len(pre_busy) > 10.0:
            first_detected_terminal = first_detected_terminal or (
                "idle_control_contaminated",
                index,
                "PRE_OBSERVATION_AVERAGE_BUSY_EXCEEDED",
            )
        previous = sample

    if (
        first_detected_terminal is None
        and terminal is not None
        and terminal.get("type") == "supervisor_or_transport_failure"
    ):
        first_detected_terminal = (
            "supervisor_or_transport_failure",
            terminal.get("sequence", len(samples) - 1),
            terminal.get("reason", "SUPERVISOR_OR_TRANSPORT_FAILURE"),
        )
    if first_detected_terminal is None:
        if len(samples) != sampler.EXPECTED_SAMPLE_COUNT:
            first_detected_terminal = (
                "interface_or_timebase_failure",
                len(samples) - 1,
                "SAMPLE_COUNT_INCOMPLETE",
            )
        elif len(formal_busy) != 120:
            first_detected_terminal = (
                "interface_or_timebase_failure",
                len(samples) - 1,
                "FORMAL_BUSY_WINDOW_COUNT_INVALID",
            )
        elif sum(formal_busy) / len(formal_busy) > 10.0:
            first_detected_terminal = (
                "idle_control_contaminated",
                len(samples) - 1,
                "FORMAL_AVERAGE_BUSY_EXCEEDED",
            )
        else:
            first_detected_terminal = (
                "completed",
                len(samples) - 1,
                "COMPLETE",
            )

    detected_type, detected_sequence, detected_reason = first_detected_terminal
    actual_type = terminal.get("type") if terminal is not None else None
    if actual_type != detected_type:
        reasons.append(f"TERMINAL_EVENT_MISMATCH:{actual_type}!={detected_type}")
    if terminal is not None and terminal.get("sequence") not in (None, detected_sequence):
        reasons.append("TERMINAL_SEQUENCE_MISMATCH")
    status = terminal_status(detected_type)
    if status is None:
        status = "MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED"
        reasons.append("UNKNOWN_DETECTED_TERMINAL")

    changes, change_summary = throttle_deltas(
        samples[0] if samples else None,
        samples[-1] if samples else None,
    )
    return {
        "status": status,
        "classification_reasons": reasons,
        "sample_count": len(samples),
        "terminal_event": terminal,
        "detected_terminal": {
            "type": detected_type,
            "sequence": detected_sequence,
            "reason": detected_reason,
        },
        "pre_average_busy_percent": sum(pre_busy) / len(pre_busy) if pre_busy else None,
        "formal_average_busy_percent": sum(formal_busy) / len(formal_busy) if formal_busy else None,
        "max_sensor_c": max_sensor_c,
        "throttle_changes": changes,
        "throttle_change_summary": change_summary,
    }


def main() -> int:
    args = arguments()
    if args.test_fixture_sequence is not None and args.test_stream_fixture_sequence is not None:
        raise RuntimeError("Choose exactly one fixture mode")
    fixture_mode = (
        args.test_fixture_sequence is not None
        or args.test_stream_fixture_sequence is not None
    )
    if fixture_mode:
        if args.authorization_file is not None or args.ssh_key is not None:
            raise RuntimeError("Fixture mode must not receive authorization or SSH arguments")
        fixture_argument = (
            args.test_fixture_sequence
            if args.test_fixture_sequence is not None
            else args.test_stream_fixture_sequence
        )
        assert fixture_argument is not None
        fixture_path = fixture_argument.resolve()
        stream_metadata = {
            "returncode": 0,
            "timeout_reason": None,
            "recovery": None,
        }
        if args.test_stream_fixture_sequence is None:
            events = load_jsonl(fixture_path)
            raw_text = fixture_path.read_text(encoding="utf-8")
            stderr_text = ""
            command = ["MOCK_FIXTURE", str(fixture_path)]
        else:
            stall_seconds = max(args.test_watchdog_seconds * 3.0, 0.15)
            command = local_stream_command(
                fixture_path,
                args.test_stream_stall_after_lines,
                args.test_stream_partial_line,
                stall_seconds,
            )
            streamed = consume_process(
                command,
                None,
                startup_seconds=max(args.test_watchdog_seconds, 0.05),
                watchdog_seconds=args.test_watchdog_seconds,
                overall_seconds=max(args.test_watchdog_seconds * 10.0, 1.0),
            )
            raw_text = streamed["stdout"]
            stderr_text = streamed["stderr"]
            events, stream_parse_errors = parse_jsonl_text_tolerant(raw_text)
            stream_metadata = {
                "returncode": streamed["returncode"],
                "timeout_reason": streamed["timeout_reason"],
                "recovery": streamed["recovery"],
                "parse_errors": stream_parse_errors,
                "raw_stdout_bytes": len(raw_text.encode("utf-8")),
            }
            if streamed["timeout_reason"] is not None or stream_parse_errors:
                last_sequence = max(
                    (
                        event.get("sequence", -1)
                        for event in events
                        if event.get("type") == "sample"
                    ),
                    default=-1,
                )
                events.append(
                    {
                        "type": "supervisor_or_transport_failure",
                        "sequence": last_sequence,
                        "reason": streamed["timeout_reason"] or "STREAM_JSON_INVALID",
                    }
                )
        target_accessed = False
        authorization_path = None
    else:
        if not TARGET_EXECUTION_ENABLED:
            raise RuntimeError(
                "D2-IDLE target execution is disabled until a separately reviewed executable "
                "protocol and run-specific authorization exist"
            )
        if args.authorization_file is None or args.ssh_key is None:
            raise RuntimeError("D2-IDLE target mode requires authorization and dedicated SSH key")
        authorization_path, _ = validate_authorization(args)
        command = [
            "/usr/bin/ssh",
            "-i",
            str(args.ssh_key.resolve()),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            TARGET,
            "/usr/bin/python3",
            "-u",
            "-",
        ]
        streamed = consume_process(
            command,
            REMOTE_SAMPLER_PATH.read_text(encoding="utf-8"),
            startup_seconds=STARTUP_SECONDS,
            watchdog_seconds=WATCHDOG_SECONDS,
            overall_seconds=OVERALL_SECONDS,
        )
        raw_text = streamed["stdout"]
        stderr_text = streamed["stderr"]
        events, stream_parse_errors = parse_jsonl_text_tolerant(raw_text)
        stream_metadata = {
            "returncode": streamed["returncode"],
            "timeout_reason": streamed["timeout_reason"],
            "recovery": streamed["recovery"],
            "parse_errors": stream_parse_errors,
            "raw_stdout_bytes": len(raw_text.encode("utf-8")),
        }
        if streamed["timeout_reason"] is not None or stream_parse_errors or not events:
            last_sequence = max(
                (
                    event.get("sequence", -1)
                    for event in events
                    if event.get("type") == "sample"
                ),
                default=-1,
            )
            events.append(
                {
                    "type": "supervisor_or_transport_failure",
                    "sequence": last_sequence,
                    "reason": streamed["timeout_reason"]
                    or ("STREAM_JSON_INVALID" if stream_parse_errors else "NO_REMOTE_EVENT"),
                }
            )
        target_accessed = True
        fixture_path = None

    analysis = classify(events, enforce_target_contract=not fixture_mode)
    if not fixture_mode:
        analysis["status"] = analysis["status"].removeprefix("MOCK_")
        expected_returncodes = {
            "completed": 0,
            "interface_or_timebase_failure": 2,
            "thermal_stop": 3,
            "idle_control_contaminated": 4,
        }
        detected_type = analysis["detected_terminal"]["type"]
        expected_returncode = expected_returncodes.get(detected_type)
        if (
            stream_metadata["timeout_reason"] is None
            and expected_returncode is not None
            and stream_metadata["returncode"] != expected_returncode
        ):
            analysis["classification_reasons"].append(
                "REMOTE_RETURNCODE_MISMATCH:"
                f"{stream_metadata['returncode']}!={expected_returncode}"
            )
            analysis["status"] = "SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED"
    evidence_root = args.evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_dir = evidence_root / args.run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    (run_dir / "raw_events.jsonl").write_text(raw_text, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr_text, encoding="utf-8")
    safe_command = list(command)
    if "-i" in safe_command:
        key_index = safe_command.index("-i") + 1
        if key_index < len(safe_command):
            safe_command[key_index] = "<DEDICATED_DK2500_KEY>"
    atomic_json(run_dir / "command.json", {"argv": safe_command})
    protocol_id = MOCK_PROTOCOL_ID if fixture_mode else TARGET_PROTOCOL_ID
    protocol_version = MOCK_PROTOCOL_VERSION if fixture_mode else TARGET_PROTOCOL_VERSION
    protocol_path = MOCK_PROTOCOL_PATH if fixture_mode else TARGET_PROTOCOL_PATH
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": protocol_id,
        "protocol_version": protocol_version,
        "run_id": args.run_id,
        "stage": "D2_IDLE_MOCK" if fixture_mode else TARGET_STAGE,
        "classification": "MOCK_CONTROL_FLOW_ONLY" if fixture_mode else "EXPLORATORY_TARGET_IDLE_CONTROL",
        **analysis,
        "configuration": expected_configuration(),
        "implementation": {
            "supervisor_sha256": sha256(Path(__file__).resolve()),
            "remote_sampler_sha256": sha256(REMOTE_SAMPLER_PATH),
            "protocol_sha256": sha256(protocol_path),
            "fixture_sha256": None if fixture_path is None else sha256(fixture_path),
            "authorization_sha256": None
            if authorization_path is None
            else sha256(authorization_path),
        },
        "target_accessed": target_accessed,
        "execution_authorized": not fixture_mode,
        "automatic_retry": False,
        "stream_control": stream_metadata,
        "evidence_files": {
            "raw_events": "raw_events.jsonl",
            "stderr": "stderr.txt",
            "command": "command.json",
        },
        "interpretation_limits": (
            [
                "Artificial fixture evidence validates local classification and evidence handling only.",
                "This result contains no DK-2500 observation and cannot describe idle or thermal behavior.",
                "Target execution requires a separately reviewed protocol and run-specific authorization.",
            ]
            if fixture_mode
            else [
                "D2-IDLE is one bounded no-deliberate-load control, not Stability qualification.",
                "Counter deltas and context do not establish the cause of a thermal event or hardware health.",
                "This result cannot support deployment, real-time or physical-safety claims.",
            ]
        ),
    }
    atomic_json(run_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    completion_status = (
        "MOCK_IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING"
        if fixture_mode
        else "IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING"
    )
    return 0 if analysis["status"] == completion_status and not analysis["classification_reasons"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
