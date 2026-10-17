#!/usr/bin/env python3
"""One-shot, read-only DK-2500 interface probe; JSON is written to stdout only."""

from __future__ import annotations

import glob
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CPU_ROOT = Path("/sys/devices/system/cpu")
HWMON_ROOT = Path("/sys/class/hwmon")


def read_text(path: Path, errors: list[dict[str, str]]) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        errors.append(
            {"path": str(path), "error": f"{type(exc).__name__}: {exc}"}
        )
        return None


def read_integer(path: Path, errors: list[dict[str, str]]) -> int | None:
    raw = read_text(path, errors)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        errors.append(
            {"path": str(path), "error": f"{type(exc).__name__}: {exc}"}
        )
        return None


def os_release(errors: list[dict[str, str]]) -> dict[str, str]:
    raw = read_text(Path("/etc/os-release"), errors)
    values: dict[str, str] = {}
    if raw is None:
        return values
    for line in raw.splitlines():
        if "=" not in line:
            continue
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


def throttle_groups(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    discovered_bases: set[Path] = set()
    for suffix in ("_count", "_total_time_ms", "_max_time_ms"):
        for raw_path in glob.glob(
            str(CPU_ROOT / f"cpu[0-9]*/thermal_throttle/*_throttle{suffix}")
        ):
            discovered_bases.add(Path(raw_path[: -len(suffix)]))
    for base in sorted(discovered_bases):
        field_paths = {
            "throttle_count": Path(f"{base}_count"),
            "throttle_total_time_ms": Path(f"{base}_total_time_ms"),
            "throttle_max_time_ms": Path(f"{base}_max_time_ms"),
        }
        values = {name: read_integer(path, errors) for name, path in field_paths.items()}
        missing = [name for name, value in values.items() if value is None]
        groups.append(
            {
                "base_path": str(base),
                "field_paths": {name: str(path) for name, path in field_paths.items()},
                "values": values,
                "complete": not missing,
                "missing_or_unparseable": missing,
            }
        )
    return groups


def temperature_sensors(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    sensors: list[dict[str, Any]] = []
    for input_path in sorted(Path(path) for path in glob.glob(str(HWMON_ROOT / "hwmon*/temp*_input"))):
        stem = input_path.name.removesuffix("_input")
        name = read_text(input_path.parent / "name", errors)
        label_path = input_path.with_name(f"{stem}_label")
        label = read_text(label_path, errors) if label_path.exists() else None
        raw_millic = read_integer(input_path, errors)
        current_c = raw_millic / 1000.0 if raw_millic is not None else None
        normalized_label = (label or "").casefold()
        normalized_name = (name or "").casefold()
        is_cpu_package = "package" in normalized_label and (
            "coretemp" in normalized_name or "cpu" in normalized_name
        )
        sensors.append(
            {
                "input_path": str(input_path),
                "hwmon_name": name,
                "label": label,
                "current_c": current_c,
                "is_cpu_package": is_cpu_package,
            }
        )
    return sensors


def frequency_interfaces(
    online_cpus: list[int], errors: list[dict[str, str]]
) -> dict[str, Any]:
    readable: list[dict[str, Any]] = []
    missing: list[str] = []
    for cpu in online_cpus:
        path = CPU_ROOT / f"cpu{cpu}" / "cpufreq" / "scaling_cur_freq"
        if not path.exists():
            missing.append(str(path))
            continue
        value_khz = read_integer(path, errors)
        if value_khz is None:
            missing.append(str(path))
            continue
        readable.append({"path": str(path), "current_mhz": value_khz / 1000.0})
    total = len(online_cpus)
    return {
        "online_cpu_count": total,
        "readable_path_count": len(readable),
        "coverage_ratio": len(readable) / total if total else 0.0,
        "readable": readable,
        "missing_or_unparseable": missing,
    }


def collect() -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    release = os_release(errors)
    online_raw = read_text(CPU_ROOT / "online", errors)
    online_cpus: list[int] = []
    if online_raw is not None:
        try:
            online_cpus = parse_cpu_list(online_raw)
        except ValueError as exc:
            errors.append(
                {"path": str(CPU_ROOT / "online"), "error": f"ValueError: {exc}"}
            )
    sensors = temperature_sensors(errors)
    readable_temperatures = [
        float(sensor["current_c"])
        for sensor in sensors
        if sensor.get("current_c") is not None
    ]
    boot_id = read_text(Path("/proc/sys/kernel/random/boot_id"), errors)
    uptime_raw = read_text(Path("/proc/uptime"), errors)
    uptime_s = None
    if uptime_raw is not None:
        try:
            uptime_s = float(uptime_raw.split()[0])
        except (ValueError, IndexError) as exc:
            errors.append({"path": "/proc/uptime", "error": f"{type(exc).__name__}: {exc}"})
    return {
        "probe_schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "hostname": platform.node(),
            "cpu_model": cpu_model(errors),
            "os_pretty_name": release.get("PRETTY_NAME"),
            "os_version_id": release.get("VERSION_ID"),
            "kernel": platform.release(),
            "python_version": platform.python_version(),
            "boot_id": boot_id,
            "uptime_seconds": uptime_s,
        },
        "online_cpu_declaration": online_raw,
        "online_cpus": online_cpus,
        "throttle_groups": throttle_groups(errors),
        "temperature": {
            "sensors": sensors,
            "package_sensor_count": sum(
                bool(sensor.get("is_cpu_package"))
                and sensor.get("current_c") is not None
                for sensor in sensors
            ),
            "max_sensor_c": max(readable_temperatures) if readable_temperatures else None,
        },
        "frequency": frequency_interfaces(online_cpus, errors),
        "read_errors": errors,
        "actions": {
            "target_file_created": False,
            "openvino_or_model_accessed": False,
            "load_generated": False,
            "system_configuration_changed": False,
            "sampling_loop_used": False,
        },
    }


def main() -> int:
    print(json.dumps(collect(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
