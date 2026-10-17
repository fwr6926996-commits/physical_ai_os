#!/usr/bin/env python3
"""Structured external monitoring helpers for Phase 4 Stability qualification."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import phase4_thermal_d2_idle_remote_sampler as thermal


EXPECTED_SAMPLE_COUNT = 7


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def throttle_values(sample: dict[str, Any]) -> dict[str, int]:
    values: dict[str, int] = {}
    for group in sample["throttle_groups"]:
        for name, value in group["values"].items():
            if isinstance(value, int):
                values[f"{group['base_path']}:{name}"] = value
    return values


def package_temperatures(sample: dict[str, Any]) -> list[float]:
    return [
        float(sensor["current_c"])
        for sensor in sample["temperature"]["sensors"]
        if sensor.get("is_cpu_package") and isinstance(sensor.get("current_c"), (int, float))
    ]


def evaluate_pre_observation(
    samples: list[dict[str, Any]],
    *,
    busy_limit_percent: float,
    package_limit_c: float,
    sensor_limit_c: float,
) -> dict[str, Any]:
    reasons: list[str] = []
    if len(samples) != EXPECTED_SAMPLE_COUNT:
        reasons.append(f"SAMPLE_COUNT:{len(samples)}!={EXPECTED_SAMPLE_COUNT}")
        return {
            "status": "INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            "reasons": reasons,
        }

    expected_boot = samples[0].get("boot_id")
    expected_signature = samples[0].get("inventory_signature")
    signature_valid = (
        isinstance(expected_signature, dict)
        and expected_signature.get("throttle_bases")
        == sorted(thermal.EXPECTED_THROTTLE_BASES)
        and expected_signature.get("frequency_paths")
        == sorted(thermal.EXPECTED_FREQUENCY_PATHS)
        and bool(expected_signature.get("temperature_paths"))
    )
    if not signature_valid:
        reasons.append("TARGET_INTERFACE_SET_MISMATCH")

    previous = None
    for index, sample in enumerate(samples):
        if sample.get("sequence") != index:
            reasons.append(f"SEQUENCE_MISMATCH:{index}")
        if not isinstance(expected_signature, dict):
            reasons.append("INVENTORY_SIGNATURE_MISSING")
            break
        failure = thermal.sample_failure_reason(
            sample,
            expected_signature,
            expected_boot,
            previous,
        )
        if failure is not None:
            reasons.append(f"{failure}:{index}")
        previous = sample

    if reasons:
        return {
            "status": "INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED",
            "reasons": reasons,
        }

    busy = [float(sample["interval_busy_percent"]) for sample in samples[1:]]
    average_busy = sum(busy) / len(busy)
    before = throttle_values(samples[0])
    after = throttle_values(samples[-1])
    increment_paths = [key for key in before if after[key] > before[key]]
    package = package_temperatures(samples[-1])
    maximum_sensor = samples[-1]["temperature"].get("max_sensor_c")

    precondition_reasons: list[str] = []
    if average_busy > busy_limit_percent:
        precondition_reasons.append("PRE_OBSERVATION_AVERAGE_BUSY_EXCEEDED")
    if increment_paths:
        precondition_reasons.append("PRE_OBSERVATION_THROTTLE_INCREMENT")
    if not package or max(package) > package_limit_c:
        precondition_reasons.append("ENTRY_PACKAGE_TEMPERATURE_EXCEEDED")
    if not isinstance(maximum_sensor, (int, float)) or maximum_sensor > sensor_limit_c:
        precondition_reasons.append("ENTRY_SENSOR_TEMPERATURE_EXCEEDED")

    return {
        "status": "PASS_STABILITY_PRE_OBSERVATION"
        if not precondition_reasons
        else "PRECONDITION_NOT_MET_REVIEW_REQUIRED",
        "reasons": precondition_reasons,
        "average_busy_percent": average_busy,
        "busy_windows": busy,
        "throttle_increment_paths": increment_paths,
        "entry_package_max_c": max(package) if package else None,
        "entry_sensor_max_c": maximum_sensor,
    }


class StabilityMonitor:
    """Collect exact-path evidence on a fixed five-second schedule."""

    def __init__(self, path: Path, interval_seconds: float = 5.0) -> None:
        if interval_seconds != thermal.INTERVAL_SECONDS:
            raise ValueError("Stability monitor currently requires the frozen five-second interval")
        self.path = path
        self.interval_seconds = interval_seconds
        self.inventory, discovery_errors = thermal.inventory()
        if discovery_errors:
            raise RuntimeError(f"thermal interface discovery failed: {discovery_errors}")
        self.signature = thermal.inventory_signature(self.inventory)
        self.start_ns = time.monotonic_ns()
        self.previous_proc_stat: dict[str, int] | None = None
        self.previous_sample: dict[str, Any] | None = None
        self.expected_boot_id: str | None = None
        self.sequence = 0
        self.stream = path.open("x", encoding="utf-8", buffering=1)
        self._emit(
            {
                "type": "monitor_identity",
                "inventory": self.inventory,
                "inventory_signature": self.signature,
                "interval_seconds": self.interval_seconds,
            }
        )

    def _emit(self, payload: dict[str, Any]) -> None:
        self.stream.write(json.dumps(payload, sort_keys=True) + "\n")
        self.stream.flush()

    def _capture(self, sample_kind: str) -> tuple[dict[str, Any], str | None]:
        sample, proc_stat = thermal.read_sample(
            self.sequence,
            self.start_ns,
            self.inventory,
            self.previous_proc_stat,
        )
        sample["sample_kind"] = sample_kind
        if self.expected_boot_id is None:
            self.expected_boot_id = sample.get("boot_id")
        failure = thermal.sample_failure_reason(
            sample,
            self.signature,
            self.expected_boot_id,
            self.previous_sample,
        )
        sample["monitor_failure_reason"] = failure
        self._emit(sample)
        self.previous_proc_stat = proc_stat
        self.previous_sample = sample
        self.sequence += 1
        return sample, failure

    def capture_scheduled(self, sample_kind: str) -> tuple[dict[str, Any], str | None]:
        deadline_ns = self.start_ns + int(self.sequence * self.interval_seconds * 1_000_000_000)
        remaining_s = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
        if remaining_s > 0:
            time.sleep(remaining_s)
        return self._capture(sample_kind)

    def capture_if_due(self, sample_kind: str) -> tuple[dict[str, Any], str | None] | None:
        deadline_ns = self.start_ns + int(self.sequence * self.interval_seconds * 1_000_000_000)
        if time.monotonic_ns() < deadline_ns:
            return None
        return self._capture(sample_kind)

    def capture_final(self) -> tuple[dict[str, Any], str | None]:
        return self._capture("final")

    def close(self) -> None:
        self.stream.close()


def validate_authorization(
    authorization: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise RuntimeError(
                f"Stability authorization mismatch for {key}: "
                f"{authorization.get(key)!r} != {value!r}"
            )
