#!/usr/bin/env python3
"""External supervisor for the frozen Phase 4 DK-2500 CPU worker."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

import phase4_stability_monitor as stability


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "phase4_frozen_config.json"
PRODUCTION_WORKER = (HERE / "phase4_cpu_worker.py").resolve()
MOCK_WORKER = (HERE / "phase4_mock_worker.py").resolve()
STABILITY_MONITOR = (HERE / "phase4_stability_monitor.py").resolve()
THERMAL_SAMPLER = (HERE / "phase4_thermal_d2_idle_remote_sampler.py").resolve()
STABILITY_PROTOCOL = (HERE / "PHASE4_STABILITY_PROTOCOL_V0_2_20261014.md").resolve()
PREPOST_PATH = (HERE / "phase4_prepost.py").resolve()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supervise one frozen Phase 4 stage.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True, choices=("correctness", "short", "stability"))
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--worker-path", type=Path, default=PRODUCTION_WORKER)
    parser.add_argument("--authorization-file", type=Path)
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument(
        "--mock-scenario",
        choices=("success", "hang", "startup_hang", "failure"),
        default="success",
    )
    parser.add_argument("--test-watchdog-seconds", type=float)
    parser.add_argument("--test-startup-seconds", type=float)
    parser.add_argument("--test-telemetry-seconds", type=float)
    parser.add_argument("--test-thermal-fixture-c", type=float)
    return parser.parse_args()


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_last_event(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last = None
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if line.strip():
                last = line
    if last is None:
        return None
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return {"type": "invalid_jsonl_tail", "raw": last.rstrip("\n")}


def throttle_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    root = Path("/sys/devices/system/cpu")
    for path in sorted(root.glob("cpu[0-9]*/thermal_throttle/*throttle_count")):
        try:
            counts[str(path)] = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
    return counts


def frequency_summary() -> dict[str, float | None]:
    frequencies = psutil.cpu_freq(percpu=True) or []
    values = [item.current for item in frequencies if item.current is not None]
    if not values:
        return {"min_mhz": None, "mean_mhz": None, "max_mhz": None}
    return {
        "min_mhz": min(values),
        "mean_mhz": sum(values) / len(values),
        "max_mhz": max(values),
    }


def temperatures(fixture_c: float | None) -> dict[str, float | None]:
    if fixture_c is not None:
        return {"package_c": fixture_c, "max_sensor_c": fixture_c}
    readings: list[float] = []
    package_c = None
    for entries in psutil.sensors_temperatures(fahrenheit=False).values():
        for item in entries:
            if item.current is None:
                continue
            value = float(item.current)
            readings.append(value)
            if item.label == "Package id 0":
                package_c = value
    return {
        "package_c": package_c,
        "max_sensor_c": max(readings) if readings else None,
    }


def telemetry_snapshot(
    elapsed_s: float, pid: int, thermal_fixture_c: float | None, sample_kind: str
) -> dict[str, Any]:
    memory = psutil.virtual_memory()
    temperature = temperatures(thermal_fixture_c)
    try:
        process = psutil.Process(pid)
        worker = {
            "worker_rss_bytes": process.memory_info().rss,
            "worker_status": process.status(),
            "worker_threads": process.num_threads(),
            "worker_snapshot_error": None,
        }
    except psutil.Error as exc:
        worker = {
            "worker_rss_bytes": None,
            "worker_status": None,
            "worker_threads": None,
            "worker_snapshot_error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "sample_kind": sample_kind,
        "elapsed_s": elapsed_s,
        **worker,
        "system_available_memory_bytes": memory.available,
        "system_cpu_percent": psutil.cpu_percent(interval=None),
        **temperature,
        **frequency_summary(),
    }


def numeric_summary(rows: list[dict[str, Any]], key: str) -> dict[str, float] | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return {"first": values[0], "last": values[-1], "min": min(values), "max": max(values)}


def process_snapshot(pid: int) -> dict[str, Any]:
    try:
        process = psutil.Process(pid)
        return {
            "pid": pid,
            "status": process.status(),
            "memory_rss_bytes": process.memory_info().rss,
            "num_threads": process.num_threads(),
        }
    except psutil.Error as exc:
        return {"pid": pid, "snapshot_error": f"{type(exc).__name__}: {exc}"}


def terminate_worker(child: subprocess.Popen[Any], grace_s: float) -> str:
    child.send_signal(signal.SIGTERM)
    try:
        child.wait(timeout=grace_s)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=grace_s)
        return "SIGKILL_AFTER_SIGTERM_TIMEOUT"


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def stability_hashes(worker_path: Path) -> dict[str, str]:
    return {
        "stage_protocol_sha256": sha256(STABILITY_PROTOCOL),
        "supervisor_sha256": sha256(Path(__file__).resolve()),
        "worker_sha256": sha256(worker_path),
        "monitor_sha256": sha256(STABILITY_MONITOR),
        "thermal_sampler_sha256": sha256(THERMAL_SAMPLER),
        "config_sha256": sha256(CONFIG_PATH),
        "prepost_sha256": sha256(PREPOST_PATH),
    }


def precondition_result(
    *,
    args: argparse.Namespace,
    config: dict[str, Any],
    started_at: datetime,
    decision: dict[str, Any],
    worker_path: Path,
    monitor_error: str | None,
) -> dict[str, Any]:
    stage_config = config["stages"]["stability"]
    return {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "protocol_snapshot": config["protocol_snapshot"],
        "stage_protocol_id": stage_config["stage_protocol_id"],
        "stage_protocol_version": stage_config["stage_protocol_version"],
        "run_id": args.run_id,
        "stage": args.stage,
        "classification": "QUALIFICATION",
        "status": decision["status"],
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "pre_observation_seconds": stage_config["pre_observation_seconds"],
            "pre_busy_limit_percent": stage_config["pre_busy_limit_percent"],
            "entry_package_max_c": stage_config["entry_package_max_c"],
            "entry_sensor_max_c": stage_config["entry_sensor_max_c"],
            "automatic_retry": False,
        },
        "implementation": {
            **stability_hashes(worker_path),
            "authorization_sha256": sha256(args.authorization_file.resolve()),
        },
        "precondition": decision,
        "monitor_error": monitor_error,
        "worker_started": False,
        "worker_pid": None,
        "worker_exitcode": None,
        "recovery": None,
        "evidence_files": {
            "stability_monitor": "stability_monitor.jsonl",
            "stability_precondition": "stability_precondition.json",
        },
        "interpretation_limits": [
            "A rejected pre-observation consumes this named attempt but is not a Stability execution result.",
            "No Worker, model read, compile or inference occurred after the failed precondition.",
        ],
    }


def main() -> int:
    args = arguments()
    config = load_config()
    worker_path = args.worker_path.resolve()
    if args.test_mode:
        if worker_path != MOCK_WORKER:
            raise RuntimeError("Test mode accepts only the frozen adjacent mock worker")
        if args.authorization_file is not None:
            raise RuntimeError("Mock mode must not consume a production authorization file")
        authorization = None
    elif worker_path != PRODUCTION_WORKER:
        raise RuntimeError("Production mode accepts only the frozen adjacent production worker")
    else:
        if args.authorization_file is None:
            raise RuntimeError("Production mode requires an explicit authorization file")
        authorization_path = args.authorization_file.resolve()
        authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
        required = {
            "protocol_id": config["protocol_id"],
            "protocol_snapshot": config["protocol_snapshot"],
            "run_id": args.run_id,
            "stage": args.stage,
            "status": "AUTHORIZED_FOR_ONE_ATTEMPT",
            "automatic_retry": False,
        }
        for key, expected in required.items():
            if authorization.get(key) != expected:
                raise RuntimeError(
                    f"Authorization mismatch for {key}: {authorization.get(key)!r} != {expected!r}"
                )
        if args.stage == "stability":
            stage_config = config["stages"]["stability"]
            if platform.node() != config["target_hostname"]:
                raise RuntimeError(
                    f"Stability target hostname mismatch: "
                    f"{platform.node()!r} != {config['target_hostname']!r}"
                )
            stability.validate_authorization(
                authorization,
                {
                    "stage_protocol_id": stage_config["stage_protocol_id"],
                    "stage_protocol_version": stage_config["stage_protocol_version"],
                    "target_hostname": config["target_hostname"],
                    "package_dir": str(args.package_dir.resolve()),
                    "pre_observation_seconds": stage_config["pre_observation_seconds"],
                    "duration_seconds": stage_config["duration_seconds"],
                    "watchdog_seconds": config["supervisor"]["infer_watchdog_seconds"],
                    "telemetry_seconds": config["supervisor"]["telemetry_interval_seconds"],
                    "overall_timeout_seconds": stage_config["overall_timeout_seconds"],
                    **stability_hashes(worker_path),
                },
            )

    supervisor_config = config["supervisor"]
    watchdog_s = float(supervisor_config["infer_watchdog_seconds"])
    startup_s = float(supervisor_config["startup_timeout_seconds"])
    telemetry_s = float(supervisor_config["telemetry_interval_seconds"])
    thermal_stop_c = float(supervisor_config["thermal_stop_c"])
    grace_s = float(supervisor_config["sigterm_grace_seconds"])
    if args.test_mode:
        watchdog_s = args.test_watchdog_seconds or 0.5
        startup_s = args.test_startup_seconds or 1.0
        telemetry_s = args.test_telemetry_seconds or 0.05

    evidence_root = args.evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_dir = evidence_root / args.run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    attempt_started = time.monotonic()
    stability_mode = args.stage == "stability" and not args.test_mode
    stability_session: stability.StabilityMonitor | None = None
    stability_precondition: dict[str, Any] | None = None
    stability_monitor_failure: str | None = None
    if stability_mode:
        stage_config = config["stages"]["stability"]
        pre_samples: list[dict[str, Any]] = []
        try:
            stability_session = stability.StabilityMonitor(
                run_dir / "stability_monitor.jsonl",
                float(config["supervisor"]["telemetry_interval_seconds"]),
            )
            for _ in range(stability.EXPECTED_SAMPLE_COUNT):
                sample, _failure = stability_session.capture_scheduled("pre_observation")
                pre_samples.append(sample)
            stability_precondition = stability.evaluate_pre_observation(
                pre_samples,
                busy_limit_percent=float(stage_config["pre_busy_limit_percent"]),
                package_limit_c=float(stage_config["entry_package_max_c"]),
                sensor_limit_c=float(stage_config["entry_sensor_max_c"]),
            )
        except Exception as exc:
            stability_monitor_failure = f"{type(exc).__name__}: {exc}"
            stability_precondition = {
                "status": "INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
                "reasons": ["PRE_OBSERVATION_MONITOR_EXCEPTION"],
            }
        atomic_json(run_dir / "stability_precondition.json", stability_precondition)
        if stability_precondition["status"] != "PASS_STABILITY_PRE_OBSERVATION":
            if stability_session is not None:
                stability_session.close()
            result = precondition_result(
                args=args,
                config=config,
                started_at=started_at,
                decision=stability_precondition,
                worker_path=worker_path,
                monitor_error=stability_monitor_failure,
            )
            atomic_json(run_dir / "supervisor_result.json", result)
            print(json.dumps(result, indent=2))
            return 1
    events_path = run_dir / "events.jsonl"
    telemetry_path = run_dir / "supervisor_telemetry.csv"
    stdout_path = run_dir / "worker_stdout.txt"
    stderr_path = run_dir / "worker_stderr.txt"
    throttle_before = throttle_counts()
    atomic_json(run_dir / "throttle_before.json", throttle_before)
    command = [
        sys.executable,
        str(worker_path),
        "--run-id",
        args.run_id,
        "--stage",
        args.stage,
        "--run-dir",
        str(run_dir),
    ]
    if args.test_mode:
        command.extend(["--scenario", args.mock_scenario])
    else:
        command.extend(["--package-dir", str(args.package_dir.resolve())])

    stdout_stream = stdout_path.open("w", encoding="utf-8")
    stderr_stream = stderr_path.open("w", encoding="utf-8")
    child = subprocess.Popen(command, stdout=stdout_stream, stderr=stderr_stream)
    supervisor_started = time.monotonic()
    last_event_size = -1
    last_progress = supervisor_started
    runtime_started = False
    next_telemetry = 0.0
    telemetry_rows: list[dict[str, Any]] = []
    stop_reason = None
    recovery = None
    diagnostic = None
    while child.poll() is None:
        now = time.monotonic()
        elapsed_s = now - supervisor_started
        if stability_session is not None:
            try:
                captured = stability_session.capture_if_due("worker_runtime")
            except Exception as exc:
                captured = None
                stability_monitor_failure = f"{type(exc).__name__}: {exc}"
                stop_reason = "THERMAL_EVIDENCE_FAILURE"
            if captured is not None:
                stability_sample, stability_monitor_failure = captured
                if stability_monitor_failure is not None:
                    stop_reason = "THERMAL_EVIDENCE_FAILURE"
                stability_max_sensor = stability_sample["temperature"].get("max_sensor_c")
                if (
                    stability_max_sensor is not None
                    and float(stability_max_sensor) >= thermal_stop_c
                ):
                    stop_reason = "THERMAL_STOP"
        if events_path.exists():
            size = events_path.stat().st_size
            if size != last_event_size:
                last_event_size = size
                last_progress = now
                last_event = read_last_event(events_path)
                if last_event and last_event.get("type") in {
                    "infer_enter",
                    "infer_return",
                    "measurement_started",
                }:
                    runtime_started = True
        if elapsed_s >= next_telemetry:
            snapshot = telemetry_snapshot(
                elapsed_s,
                child.pid,
                args.test_thermal_fixture_c if args.test_mode else None,
                "start" if not telemetry_rows else "periodic",
            )
            telemetry_rows.append(snapshot)
            next_telemetry += telemetry_s
            max_sensor = snapshot.get("max_sensor_c")
            if max_sensor is not None and float(max_sensor) >= thermal_stop_c:
                stop_reason = "THERMAL_STOP"
        timeout_s = watchdog_s if runtime_started else startup_s
        if (
            stop_reason is None
            and stability_mode
            and now - attempt_started
            > float(config["stages"]["stability"]["overall_timeout_seconds"])
        ):
            stop_reason = "OVERALL_TIMEOUT"
        if stop_reason is None and now - last_progress > timeout_s:
            stop_reason = "INFER_WATCHDOG_TIMEOUT" if runtime_started else "STARTUP_TIMEOUT"
        if stop_reason is not None:
            diagnostic = {
                "stop_reason": stop_reason,
                "seconds_without_event_growth": now - last_progress,
                "last_event": read_last_event(events_path),
                "process": process_snapshot(child.pid),
            }
            recovery = terminate_worker(child, grace_s)
            break
        time.sleep(min(0.1, telemetry_s))

    final_elapsed_s = time.monotonic() - supervisor_started
    final_snapshot = telemetry_snapshot(
        final_elapsed_s,
        child.pid,
        args.test_thermal_fixture_c if args.test_mode else None,
        "final",
    )
    telemetry_rows.append(final_snapshot)
    final_max_sensor = final_snapshot.get("max_sensor_c")
    final_thermal_limit = bool(
        stop_reason is None
        and final_max_sensor is not None
        and float(final_max_sensor) >= thermal_stop_c
    )
    stability_final_sample = None
    if stability_session is not None:
        try:
            stability_final_sample, final_monitor_failure = stability_session.capture_final()
            stability_monitor_failure = stability_monitor_failure or final_monitor_failure
            stability_final_max = stability_final_sample["temperature"].get("max_sensor_c")
            if (
                stop_reason is None
                and stability_final_max is not None
                and float(stability_final_max) >= thermal_stop_c
            ):
                final_thermal_limit = True
        except Exception as exc:
            stability_monitor_failure = stability_monitor_failure or f"{type(exc).__name__}: {exc}"
        finally:
            stability_session.close()

    stdout_stream.close()
    stderr_stream.close()
    throttle_after = throttle_counts()
    throttle_delta = {
        key: value - int(throttle_before.get(key, value)) for key, value in throttle_after.items()
    }
    if telemetry_rows:
        with telemetry_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=tuple(telemetry_rows[0]))
            writer.writeheader()
            writer.writerows(telemetry_rows)
    worker_result_path = run_dir / "worker_result.json"
    worker_result = None
    if worker_result_path.exists():
        worker_result = json.loads(worker_result_path.read_text(encoding="utf-8"))

    if stop_reason is not None:
        status = f"{stop_reason}_RECOVERED"
        exit_code = 1
    elif final_thermal_limit:
        status = "THERMAL_LIMIT_OBSERVED_AT_FINAL_SNAPSHOT"
        exit_code = 1
    elif stability_monitor_failure is not None:
        status = "THERMAL_EVIDENCE_FAILURE_REVIEW_REQUIRED"
        exit_code = 1
    elif child.returncode == 0 and worker_result and str(worker_result.get("status", "")).endswith(
        "SUPERVISOR_REVIEW_PENDING"
    ):
        status = "STAGE_PASS_REVIEW_PENDING"
        exit_code = 0
    else:
        status = "WORKER_FAILED_WITHOUT_SUPERVISOR_TIMEOUT"
        exit_code = 1
    if args.test_mode:
        status = "MOCK_" + status
    result = {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "protocol_snapshot": config["protocol_snapshot"],
        "stage_protocol_id": config["stages"]["stability"].get("stage_protocol_id")
        if args.stage == "stability"
        else None,
        "stage_protocol_version": config["stages"]["stability"].get(
            "stage_protocol_version"
        )
        if args.stage == "stability"
        else None,
        "run_id": args.run_id,
        "stage": args.stage,
        "classification": "MOCK_CONTROL_FLOW_ONLY" if args.test_mode else "QUALIFICATION",
        "status": status,
        "started_at_utc": started_at.isoformat(),
        "ended_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "watchdog_seconds": watchdog_s,
            "startup_seconds": startup_s,
            "telemetry_seconds": telemetry_s,
            "thermal_stop_c": thermal_stop_c,
            "sigterm_grace_seconds": grace_s,
            "worker_path": str(worker_path),
            "package_dir": None if args.test_mode else str(args.package_dir.resolve()),
            "automatic_retry": False,
            "overall_timeout_seconds": config["stages"]["stability"].get(
                "overall_timeout_seconds"
            )
            if args.stage == "stability"
            else None,
        },
        "implementation": {
            "supervisor_sha256": sha256(Path(__file__).resolve()),
            "worker_sha256": sha256(worker_path),
            "config_sha256": sha256(CONFIG_PATH),
            "prepost_sha256": sha256(PREPOST_PATH),
            "monitor_sha256": sha256(STABILITY_MONITOR)
            if args.stage == "stability"
            else None,
            "thermal_sampler_sha256": sha256(THERMAL_SAMPLER)
            if args.stage == "stability"
            else None,
            "stage_protocol_sha256": sha256(STABILITY_PROTOCOL)
            if args.stage == "stability"
            else None,
            "authorization_sha256": None
            if args.test_mode
            else sha256(args.authorization_file.resolve()),
        },
        "worker_pid": child.pid,
        "worker_exitcode": child.returncode,
        "recovery": recovery,
        "diagnostic": diagnostic,
        "stability_precondition": stability_precondition,
        "stability_monitor_failure": stability_monitor_failure,
        "stability_final_sample_sequence": stability_final_sample.get("sequence")
        if stability_final_sample
        else None,
        "last_event": read_last_event(events_path),
        "worker_result_status": worker_result.get("status") if worker_result else None,
        "throttle_counter_delta": throttle_delta,
        "throttle_counter_increment_paths": sum(1 for value in throttle_delta.values() if value > 0),
        "telemetry_summary": {
            "samples": len(telemetry_rows),
            "sample_kinds": [row["sample_kind"] for row in telemetry_rows],
            "package_c": numeric_summary(telemetry_rows, "package_c"),
            "max_sensor_c": numeric_summary(telemetry_rows, "max_sensor_c"),
            "worker_rss_bytes": numeric_summary(telemetry_rows, "worker_rss_bytes"),
            "system_available_memory_bytes": numeric_summary(
                telemetry_rows, "system_available_memory_bytes"
            ),
            "mean_mhz": numeric_summary(telemetry_rows, "mean_mhz"),
        },
        "evidence_files": {
            "events": "events.jsonl" if events_path.exists() else None,
            "worker_result": "worker_result.json" if worker_result else None,
            "supervisor_telemetry": "supervisor_telemetry.csv" if telemetry_rows else None,
            "worker_stdout": "worker_stdout.txt",
            "worker_stderr": "worker_stderr.txt",
            "stability_monitor": "stability_monitor.jsonl"
            if stability_mode
            else None,
            "stability_precondition": "stability_precondition.json"
            if stability_mode
            else None,
        },
        "interpretation_limits": [
            "Diagnostic-only latency/resource observations are not real-time or safety evidence.",
            "A mock result validates harness control flow only and cannot qualify OpenVINO or CPU inference."
            if args.test_mode
            else "This stage remains review-pending until evidence is independently checked.",
        ],
    }
    atomic_json(run_dir / "supervisor_result.json", result)
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
