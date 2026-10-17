#!/usr/bin/env python3
"""Bounded read-only D2-IDLE target sampler; JSONL is written to stdout only."""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import signal
import time
import ctypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CPU_ROOT = Path("/sys/devices/system/cpu")
HWMON_ROOT = Path("/sys/class/hwmon")
PRE_OBSERVATION_SECONDS = 30.0
FORMAL_OBSERVATION_SECONDS = 600.0
INTERVAL_SECONDS = 5.0
PRE_BUSY_LIMIT_PERCENT = 10.0
FORMAL_BUSY_LIMIT_PERCENT = 10.0
SUSTAINED_BUSY_LIMIT_PERCENT = 20.0
SUSTAINED_BUSY_WINDOWS = 3
THERMAL_STOP_C = 100.0
EXPECTED_SAMPLE_COUNT = 127
EXPECTED_TARGET_IDENTITY = {
    "hostname": "hepintelpc",
    "cpu_model": "Intel(R) Core(TM) Ultra 5 225U",
    "os_pretty_name": "Ubuntu 24.04.4 LTS",
    "kernel": "6.17.0-35-generic",
    "python_version": "3.12.3",
}
EXPECTED_THROTTLE_BASES = tuple(
    f"/sys/devices/system/cpu/cpu{cpu}/thermal_throttle/{kind}_throttle"
    for cpu in range(14)
    for kind in ("core", "package")
)
EXPECTED_FREQUENCY_PATHS = tuple(
    f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq"
    for cpu in range(14)
)
D3_LOAD_WORKERS = 12
D3_FORMAL_BUSY_MIN_PERCENT = 70.0
D3_LOW_BUSY_LIMIT_PERCENT = 60.0
D3_LOW_BUSY_WINDOWS = 3
D3_ENTRY_PACKAGE_MAX_C = 60.0
D3_ENTRY_SENSOR_MAX_C = 65.0


class CpuLoadController:
    """Forked standard-library CPU load with bounded cleanup and parent-death protection."""

    def __init__(self, worker_count: int) -> None:
        self.worker_count = worker_count
        self.pids: list[int] = []
        self.exits: dict[int, int] = {}
        self.read_fd: int | None = None
        self.write_fd: int | None = None

    @staticmethod
    def _worker(write_fd: int, expected_parent: int) -> None:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGTERM) != 0:  # PR_SET_PDEATHSIG
            os._exit(91)
        if os.getppid() != expected_parent:
            os._exit(92)
        running = True

        def stop(_signum: int, _frame: Any) -> None:
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        value = (os.getpid() ^ 0x9E3779B9) & 0xFFFFFFFF
        iterations = 0
        while running:
            for _ in range(10000):
                value = (value * 1664525 + 1013904223) & 0xFFFFFFFF
            iterations += 10000
        payload = json.dumps(
            {"pid": os.getpid(), "iterations": iterations, "checksum": value},
            sort_keys=True,
        ).encode("utf-8") + b"\n"
        try:
            os.write(write_fd, payload)
        except OSError:
            pass
        os.close(write_fd)
        os._exit(0)

    def start(self) -> list[int]:
        if self.pids:
            raise RuntimeError("load workers already started")
        read_fd, write_fd = os.pipe()
        os.set_blocking(read_fd, False)
        self.read_fd, self.write_fd = read_fd, write_fd
        parent_pid = os.getpid()
        for _ in range(self.worker_count):
            pid = os.fork()
            if pid == 0:
                os.close(read_fd)
                self._worker(write_fd, parent_pid)
            self.pids.append(pid)
        os.close(write_fd)
        self.write_fd = None
        return list(self.pids)

    def poll(self) -> dict[str, Any]:
        for pid in self.pids:
            if pid in self.exits:
                continue
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                self.exits[pid] = os.waitstatus_to_exitcode(status)
        return {
            "requested": self.worker_count,
            "started": len(self.pids),
            "alive": sum(pid not in self.exits for pid in self.pids),
            "exits": {str(pid): code for pid, code in sorted(self.exits.items())},
        }

    def stop(self) -> dict[str, Any]:
        for pid in self.pids:
            if pid not in self.exits:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and self.poll()["alive"]:
            time.sleep(0.02)
        recovery = "SIGTERM"
        for pid in self.pids:
            if pid not in self.exits:
                recovery = "SIGKILL"
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                waited, status = os.waitpid(pid, 0)
                if waited:
                    self.exits[pid] = os.waitstatus_to_exitcode(status)
        records: list[dict[str, Any]] = []
        if self.read_fd is not None:
            chunks = bytearray()
            while True:
                try:
                    chunk = os.read(self.read_fd, 65536)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                chunks.extend(chunk)
            os.close(self.read_fd)
            self.read_fd = None
            for line in bytes(chunks).splitlines():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    records.append({"parse_error": line.decode("utf-8", errors="replace")})
        return {**self.poll(), "recovery": recovery, "worker_records": records}
PROC_STAT_FIELDS = (
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def read_text(path: Path, errors: list[dict[str, str]]) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        return None


def read_integer(path: Path, errors: list[dict[str, str]]) -> int | None:
    raw = read_text(path, errors)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        return None


def os_release(errors: list[dict[str, str]]) -> dict[str, str]:
    raw = read_text(Path("/etc/os-release"), errors)
    values: dict[str, str] = {}
    if raw is None:
        return values
    for line in raw.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
    return values


def cpu_model(errors: list[dict[str, str]]) -> str | None:
    raw = read_text(Path("/proc/cpuinfo"), errors)
    if raw is None:
        return None
    for line in raw.splitlines():
        if line.lower().startswith("model name") and ":" in line:
            return line.split(":", 1)[1].strip()
    errors.append({"path": "/proc/cpuinfo", "error": "model name not found"})
    return None


def parse_cpu_list(raw: str) -> list[int]:
    cpus: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (int(value) for value in part.split("-", 1))
            cpus.extend(range(start, end + 1))
        else:
            cpus.append(int(part))
    return sorted(set(cpus))


def discover_throttle_groups() -> list[dict[str, Any]]:
    bases: set[Path] = set()
    for suffix in ("_count", "_total_time_ms", "_max_time_ms"):
        pattern = CPU_ROOT / f"cpu[0-9]*/thermal_throttle/*_throttle{suffix}"
        for raw_path in glob.glob(str(pattern)):
            bases.add(Path(raw_path[: -len(suffix)]))
    return [
        {
            "base_path": str(base),
            "field_paths": {
                "throttle_count": str(Path(f"{base}_count")),
                "throttle_total_time_ms": str(Path(f"{base}_total_time_ms")),
                "throttle_max_time_ms": str(Path(f"{base}_max_time_ms")),
            },
        }
        for base in sorted(bases)
    ]


def discover_temperature_sensors(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    sensors: list[dict[str, Any]] = []
    pattern = HWMON_ROOT / "hwmon*/temp*_input"
    for input_path in sorted(Path(path) for path in glob.glob(str(pattern))):
        stem = input_path.name.removesuffix("_input")
        name = read_text(input_path.parent / "name", errors)
        label_path = input_path.with_name(f"{stem}_label")
        label = read_text(label_path, errors) if label_path.exists() else None
        normalized_label = (label or "").casefold()
        normalized_name = (name or "").casefold()
        sensors.append(
            {
                "input_path": str(input_path),
                "hwmon_name": name,
                "label": label,
                "is_cpu_package": "package" in normalized_label
                and ("coretemp" in normalized_name or "cpu" in normalized_name),
            }
        )
    return sensors


def discover_frequency_paths(online_cpus: list[int]) -> list[str]:
    return [
        str(CPU_ROOT / f"cpu{cpu}" / "cpufreq" / "scaling_cur_freq")
        for cpu in online_cpus
        if (CPU_ROOT / f"cpu{cpu}" / "cpufreq" / "scaling_cur_freq").exists()
    ]


def read_proc_stat(errors: list[dict[str, str]]) -> dict[str, int] | None:
    raw = read_text(Path("/proc/stat"), errors)
    if raw is None:
        return None
    first = raw.splitlines()[0].split()
    if not first or first[0] != "cpu" or len(first) < len(PROC_STAT_FIELDS) + 1:
        errors.append({"path": "/proc/stat", "error": "aggregate cpu line incomplete"})
        return None
    try:
        values = [int(value) for value in first[1 : len(PROC_STAT_FIELDS) + 1]]
    except ValueError as exc:
        errors.append({"path": "/proc/stat", "error": f"ValueError: {exc}"})
        return None
    return dict(zip(PROC_STAT_FIELDS, values, strict=True))


def busy_percent(before: dict[str, int], after: dict[str, int]) -> float:
    deltas = {field: after[field] - before[field] for field in PROC_STAT_FIELDS}
    if any(delta < 0 for delta in deltas.values()):
        raise ValueError("/proc/stat component decreased")
    delta_total = sum(deltas.values())
    if delta_total <= 0:
        raise ValueError("/proc/stat total delta is not positive")
    delta_idle = deltas["idle"] + deltas["iowait"]
    value = 100.0 * (delta_total - delta_idle) / delta_total
    if not 0.0 <= value <= 100.0:
        raise ValueError("calculated CPU busy percent is outside 0..100")
    return value


def inventory() -> tuple[dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    online_raw = read_text(CPU_ROOT / "online", errors)
    online_cpus: list[int] = []
    if online_raw is not None:
        try:
            online_cpus = parse_cpu_list(online_raw)
        except ValueError as exc:
            errors.append({"path": str(CPU_ROOT / "online"), "error": f"ValueError: {exc}"})
    result = {
        "online_cpu_declaration": online_raw,
        "online_cpus": online_cpus,
        "throttle_groups": discover_throttle_groups(),
        "temperature_sensors": discover_temperature_sensors(errors),
        "frequency_paths": discover_frequency_paths(online_cpus),
    }
    return result, errors


def inventory_signature(value: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "throttle_bases": sorted(group["base_path"] for group in value["throttle_groups"]),
        "temperature_paths": sorted(sensor["input_path"] for sensor in value["temperature_sensors"]),
        "frequency_paths": sorted(value["frequency_paths"]),
    }


def read_sample(
    sequence: int,
    start_ns: int,
    frozen_inventory: dict[str, Any],
    previous_proc_stat: dict[str, int] | None,
) -> tuple[dict[str, Any], dict[str, int] | None]:
    read_started_ns = time.monotonic_ns()
    errors: list[dict[str, str]] = []
    boot_id = read_text(Path("/proc/sys/kernel/random/boot_id"), errors)
    current_inventory, inventory_errors = inventory()
    errors.extend(inventory_errors)

    throttle_groups: list[dict[str, Any]] = []
    for group in frozen_inventory["throttle_groups"]:
        values = {
            name: read_integer(Path(path), errors)
            for name, path in group["field_paths"].items()
        }
        missing = [name for name, value in values.items() if value is None]
        throttle_groups.append(
            {
                "base_path": group["base_path"],
                "field_paths": group["field_paths"],
                "values": values,
                "complete": not missing,
                "missing_or_unparseable": missing,
            }
        )

    temperatures: list[dict[str, Any]] = []
    for sensor in frozen_inventory["temperature_sensors"]:
        raw = read_integer(Path(sensor["input_path"]), errors)
        temperatures.append(
            {
                **sensor,
                "current_c": None if raw is None else raw / 1000.0,
            }
        )

    frequencies: list[dict[str, Any]] = []
    for path in frozen_inventory["frequency_paths"]:
        raw = read_integer(Path(path), errors)
        frequencies.append(
            {"path": path, "current_mhz": None if raw is None else raw / 1000.0}
        )

    proc_stat = read_proc_stat(errors)
    interval_busy_percent = None
    busy_error = None
    if previous_proc_stat is not None and proc_stat is not None:
        try:
            interval_busy_percent = busy_percent(previous_proc_stat, proc_stat)
        except ValueError as exc:
            busy_error = str(exc)
            errors.append({"path": "/proc/stat", "error": busy_error})

    loadavg_raw = read_text(Path("/proc/loadavg"), errors)
    loadavg = None
    if loadavg_raw is not None:
        try:
            loadavg = [float(value) for value in loadavg_raw.split()[:3]]
        except ValueError as exc:
            errors.append({"path": "/proc/loadavg", "error": f"ValueError: {exc}"})

    read_finished_ns = time.monotonic_ns()
    elapsed_s = (read_started_ns - start_ns) / 1_000_000_000
    scheduled_elapsed_s = sequence * INTERVAL_SECONDS
    schedule_lag_ms = max(0.0, (elapsed_s - scheduled_elapsed_s) * 1000.0)
    if sequence < 6:
        phase = "pre_observation"
    elif sequence == 6:
        phase = "pre_formal_boundary"
    else:
        phase = "formal_observation"
    values_c = [
        float(sensor["current_c"])
        for sensor in temperatures
        if sensor["current_c"] is not None
    ]
    sample = {
        "type": "sample",
        "sequence": sequence,
        "phase": phase,
        "target_utc": datetime.now(timezone.utc).isoformat(),
        "target_monotonic_ns": read_started_ns,
        "elapsed_s": elapsed_s,
        "scheduled_elapsed_s": scheduled_elapsed_s,
        "schedule_lag_ms": schedule_lag_ms,
        "sample_read_duration_ms": (read_finished_ns - read_started_ns) / 1_000_000,
        "boot_id": boot_id,
        "inventory_signature": inventory_signature(current_inventory),
        "throttle_groups": throttle_groups,
        "temperature": {
            "sensors": temperatures,
            "max_sensor_c": max(values_c) if values_c else None,
            "package_sensor_count": sum(
                bool(sensor["is_cpu_package"]) and sensor["current_c"] is not None
                for sensor in temperatures
            ),
        },
        "frequency": {"readable": frequencies},
        "proc_stat": proc_stat,
        "interval_busy_percent": interval_busy_percent,
        "busy_calculation_error": busy_error,
        "loadavg": loadavg,
        "read_errors": errors,
    }
    return sample, proc_stat


def sample_failure_reason(
    sample: dict[str, Any],
    expected_signature: dict[str, list[str]],
    expected_boot_id: str | None,
    previous_sample: dict[str, Any] | None,
) -> str | None:
    if sample["boot_id"] != expected_boot_id:
        return "BOOT_ID_CHANGED"
    if sample["inventory_signature"] != expected_signature:
        return "INTERFACE_INVENTORY_CHANGED"
    if sample["read_errors"]:
        return "READ_OR_PARSE_ERROR"
    if sample["sample_read_duration_ms"] >= INTERVAL_SECONDS * 1000:
        return "SAMPLE_READ_CONSUMED_INTERVAL"
    if sample["schedule_lag_ms"] >= INTERVAL_SECONDS * 1000:
        return "SAMPLE_DEADLINE_MISSED"
    if sample["temperature"]["package_sensor_count"] < 1:
        return "NO_CPU_PACKAGE_TEMPERATURE"
    if any(not group["complete"] for group in sample["throttle_groups"]):
        return "INCOMPLETE_THROTTLE_GROUP"
    if any(row["current_mhz"] is None for row in sample["frequency"]["readable"]):
        return "MISSING_CPU_FREQUENCY"
    if sample["proc_stat"] is None:
        return "PROC_STAT_INVALID"
    if previous_sample is not None:
        if sample["target_monotonic_ns"] <= previous_sample["target_monotonic_ns"]:
            return "MONOTONIC_TIME_REVERSED"
        if sample["interval_busy_percent"] is None:
            return "CPU_BUSY_INVALID"
        previous_groups = {
            group["base_path"]: group["values"] for group in previous_sample["throttle_groups"]
        }
        for group in sample["throttle_groups"]:
            before = previous_groups[group["base_path"]]
            for field, after in group["values"].items():
                if after < before[field]:
                    return "THROTTLE_COUNTER_DECREASED"
    return None


def identity_payload(errors: list[dict[str, str]]) -> dict[str, Any]:
    release = os_release(errors)
    return {
        "hostname": platform.node(),
        "cpu_model": cpu_model(errors),
        "os_pretty_name": release.get("PRETTY_NAME"),
        "kernel": platform.release(),
        "python_version": platform.python_version(),
    }


def main(load_workers: int = 0) -> int:
    d3_mode = load_workers > 0
    if d3_mode and load_workers != D3_LOAD_WORKERS:
        raise ValueError(f"D3 requires exactly {D3_LOAD_WORKERS} workers")
    frozen_inventory, discovery_errors = inventory()
    expected_signature = inventory_signature(frozen_inventory)
    identity_errors: list[dict[str, str]] = []
    identity = identity_payload(identity_errors)
    boot_errors: list[dict[str, str]] = []
    boot_id = read_text(Path("/proc/sys/kernel/random/boot_id"), boot_errors)
    startup_errors = discovery_errors + identity_errors + boot_errors
    for field, expected in EXPECTED_TARGET_IDENTITY.items():
        if identity.get(field) != expected:
            startup_errors.append(
                {
                    "path": f"identity.{field}",
                    "error": f"expected {expected!r}, got {identity.get(field)!r}",
                }
            )
    if expected_signature["throttle_bases"] != sorted(EXPECTED_THROTTLE_BASES):
        startup_errors.append(
            {
                "path": "inventory_signature.throttle_bases",
                "error": "does not match the 28-group D2-PREFLIGHT inventory",
            }
        )
    if expected_signature["frequency_paths"] != sorted(EXPECTED_FREQUENCY_PATHS):
        startup_errors.append(
            {
                "path": "inventory_signature.frequency_paths",
                "error": "does not match the 14-path D2-PREFLIGHT inventory",
            }
        )
    if not any(sensor["is_cpu_package"] for sensor in frozen_inventory["temperature_sensors"]):
        startup_errors.append(
            {
                "path": "inventory_signature.temperature_paths",
                "error": "no readable CPU package sensor discovered",
            }
        )
    configuration = {
        "pre_observation_seconds": PRE_OBSERVATION_SECONDS,
        "formal_observation_seconds": FORMAL_OBSERVATION_SECONDS,
        "interval_seconds": INTERVAL_SECONDS,
        "thermal_stop_c": THERMAL_STOP_C,
        "expected_sample_count": EXPECTED_SAMPLE_COUNT,
    }
    if d3_mode:
        configuration.update(
            {
                "load_workers": D3_LOAD_WORKERS,
                "pre_busy_limit_percent": PRE_BUSY_LIMIT_PERCENT,
                "formal_busy_min_percent": D3_FORMAL_BUSY_MIN_PERCENT,
                "low_busy_limit_percent": D3_LOW_BUSY_LIMIT_PERCENT,
                "low_busy_windows": D3_LOW_BUSY_WINDOWS,
                "entry_package_max_c": D3_ENTRY_PACKAGE_MAX_C,
                "entry_sensor_max_c": D3_ENTRY_SENSOR_MAX_C,
            }
        )
    else:
        configuration.update(
            {
                "pre_busy_limit_percent": PRE_BUSY_LIMIT_PERCENT,
                "formal_busy_limit_percent": FORMAL_BUSY_LIMIT_PERCENT,
                "sustained_busy_limit_percent": SUSTAINED_BUSY_LIMIT_PERCENT,
                "sustained_busy_windows": SUSTAINED_BUSY_WINDOWS,
            }
        )
    emit(
        {
            "type": "runtime_identity",
            "identity": identity,
            "boot_id": boot_id,
            "inventory": frozen_inventory,
            "inventory_signature": expected_signature,
            "startup_errors": startup_errors,
            "configuration": configuration,
            "actions": {
                "target_file_created": False,
                "openvino_or_model_accessed": False,
                "deliberate_load_generated": d3_mode,
                "system_configuration_changed": False,
            },
        }
    )
    if startup_errors or not boot_id or not expected_signature["throttle_bases"]:
        emit({"type": "interface_or_timebase_failure", "reason": "STARTUP_INTERFACE_FAILURE"})
        return 2

    start_ns = time.monotonic_ns()
    previous_sample: dict[str, Any] | None = None
    previous_proc_stat: dict[str, int] | None = None
    pre_busy: list[float] = []
    formal_busy: list[float] = []
    consecutive_high = 0
    consecutive_low = 0
    first_sample: dict[str, Any] | None = None
    load = CpuLoadController(load_workers) if d3_mode else None

    def stop_load(reason: str) -> None:
        if load is not None and load.pids:
            emit({"type": "load_stopped", "reason": reason, **load.stop()})

    for sequence in range(EXPECTED_SAMPLE_COUNT):
        deadline_ns = start_ns + int(sequence * INTERVAL_SECONDS * 1_000_000_000)
        remaining_ns = deadline_ns - time.monotonic_ns()
        if remaining_ns > 0:
            time.sleep(remaining_ns / 1_000_000_000)
        sample, current_proc_stat = read_sample(
            sequence, start_ns, frozen_inventory, previous_proc_stat
        )
        reason = sample_failure_reason(
            sample, expected_signature, boot_id, previous_sample
        )
        emit(sample)
        if first_sample is None:
            first_sample = sample
        if reason is not None:
            stop_load(reason)
            emit(
                {
                    "type": "interface_or_timebase_failure",
                    "sequence": sequence,
                    "reason": reason,
                }
            )
            return 2
        max_sensor_c = sample["temperature"]["max_sensor_c"]
        if max_sensor_c is not None and float(max_sensor_c) >= THERMAL_STOP_C:
            stop_load("THERMAL_STOP")
            emit(
                {
                    "type": "thermal_stop",
                    "sequence": sequence,
                    "max_sensor_c": max_sensor_c,
                }
            )
            return 3
        busy = sample["interval_busy_percent"]
        if sequence in range(1, 7) and busy is not None:
            pre_busy.append(float(busy))
        if sequence == 6:
            pre_average = sum(pre_busy) / len(pre_busy)
            if pre_average > PRE_BUSY_LIMIT_PERCENT:
                terminal_type = "precondition_not_met" if d3_mode else "idle_control_contaminated"
                emit(
                    {
                        "type": terminal_type,
                        "sequence": sequence,
                        "reason": "PRE_OBSERVATION_AVERAGE_BUSY_EXCEEDED",
                        "average_busy_percent": pre_average,
                    }
                )
                return 4
            if d3_mode:
                assert first_sample is not None
                first_groups = {
                    group["base_path"]: group["values"]
                    for group in first_sample["throttle_groups"]
                }
                pre_increment = any(
                    value > first_groups[group["base_path"]][field]
                    for group in sample["throttle_groups"]
                    for field, value in group["values"].items()
                )
                package_values = [
                    row["current_c"]
                    for row in sample["temperature"]["sensors"]
                    if row["is_cpu_package"] and row["current_c"] is not None
                ]
                precondition_reason = None
                if pre_increment:
                    precondition_reason = "PRE_OBSERVATION_THROTTLE_INCREMENT"
                elif not package_values or max(package_values) > D3_ENTRY_PACKAGE_MAX_C:
                    precondition_reason = "ENTRY_PACKAGE_TEMPERATURE_EXCEEDED"
                elif float(max_sensor_c) > D3_ENTRY_SENSOR_MAX_C:
                    precondition_reason = "ENTRY_SENSOR_TEMPERATURE_EXCEEDED"
                if precondition_reason is not None:
                    emit(
                        {
                            "type": "precondition_not_met",
                            "sequence": sequence,
                            "reason": precondition_reason,
                        }
                    )
                    return 4
                assert load is not None
                pids = load.start()
                emit(
                    {
                        "type": "load_started",
                        "sequence": sequence,
                        "worker_count": load_workers,
                        "worker_pids": pids,
                    }
                )
        if sequence >= 7 and busy is not None:
            formal_busy.append(float(busy))
            if d3_mode:
                assert load is not None
                worker_state = load.poll()
                if worker_state["alive"] != load_workers:
                    stop_load("LOAD_WORKER_EXITED")
                    emit(
                        {
                            "type": "load_control_invalid",
                            "sequence": sequence,
                            "reason": "LOAD_WORKER_EXITED",
                            "worker_state": worker_state,
                        }
                    )
                    return 4
                if len(formal_busy) > 2:
                    consecutive_low = (
                        consecutive_low + 1 if busy < D3_LOW_BUSY_LIMIT_PERCENT else 0
                    )
                    if consecutive_low >= D3_LOW_BUSY_WINDOWS:
                        stop_load("SUSTAINED_LOAD_BUSY_BELOW_MINIMUM")
                        emit(
                            {
                                "type": "load_control_invalid",
                                "sequence": sequence,
                                "reason": "SUSTAINED_LOAD_BUSY_BELOW_MINIMUM",
                                "consecutive_windows": consecutive_low,
                            }
                        )
                        return 4
            else:
                consecutive_high = consecutive_high + 1 if busy > SUSTAINED_BUSY_LIMIT_PERCENT else 0
            if not d3_mode and consecutive_high >= SUSTAINED_BUSY_WINDOWS:
                emit(
                    {
                        "type": "idle_control_contaminated",
                        "sequence": sequence,
                        "reason": "SUSTAINED_FORMAL_BUSY_EXCEEDED",
                        "consecutive_windows": consecutive_high,
                    }
                )
                return 4
        previous_sample = sample
        previous_proc_stat = current_proc_stat

    formal_average = sum(formal_busy) / len(formal_busy)
    if d3_mode and formal_average < D3_FORMAL_BUSY_MIN_PERCENT:
        stop_load("FORMAL_AVERAGE_BUSY_BELOW_MINIMUM")
        emit(
            {
                "type": "load_control_invalid",
                "sequence": EXPECTED_SAMPLE_COUNT - 1,
                "reason": "FORMAL_AVERAGE_BUSY_BELOW_MINIMUM",
                "average_busy_percent": formal_average,
            }
        )
        return 4
    if not d3_mode and formal_average > FORMAL_BUSY_LIMIT_PERCENT:
        emit(
            {
                "type": "idle_control_contaminated",
                "sequence": EXPECTED_SAMPLE_COUNT - 1,
                "reason": "FORMAL_AVERAGE_BUSY_EXCEEDED",
                "average_busy_percent": formal_average,
            }
        )
        return 4
    stop_load("COMPLETE")
    emit(
        {
            "type": "load_observation_completed" if d3_mode else "completed",
            "sequence": EXPECTED_SAMPLE_COUNT - 1,
            "sample_count": EXPECTED_SAMPLE_COUNT,
            "formal_average_busy_percent": formal_average,
        }
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-workers", type=int, default=0)
    raise SystemExit(main(parser.parse_args().load_workers))
