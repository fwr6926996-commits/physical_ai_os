#!/usr/bin/env python3
"""Mock-only sampler logic for the Phase 4 thermal diagnosis D1 gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


PROTOCOL_ID = "P4-DK2500-THERMAL-D1-MOCK-001"
PROTOCOL_VERSION = "0.1"
THERMAL_STOP_C = 100.0
FIELD_SUFFIXES = {
    "throttle_count": "_count",
    "throttle_total_time_ms": "_total_time_ms",
    "throttle_max_time_ms": "_max_time_ms",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument(
        "--test-fixture-sequence",
        required=True,
        type=Path,
        help="Artificial JSON samples. D1 has no target-reading mode.",
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


def metric_identity(path: str) -> tuple[str, str] | None:
    for kind, suffix in FIELD_SUFFIXES.items():
        if path.endswith(suffix):
            return path[: -len(suffix)], kind
    return None


def interface_report(sample: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, set[str]] = {}
    unknown_paths: list[str] = []
    for path in sample.get("throttle", {}):
        identity = metric_identity(path)
        if identity is None:
            unknown_paths.append(path)
            continue
        base, kind = identity
        groups.setdefault(base, set()).add(kind)
    required = set(FIELD_SUFFIXES)
    incomplete = {
        base: sorted(required - kinds)
        for base, kinds in groups.items()
        if kinds != required
    }
    return {
        "group_count": len(groups),
        "complete_group_count": sum(kinds == required for kinds in groups.values()),
        "incomplete_groups": incomplete,
        "unknown_paths": sorted(unknown_paths),
        "temperature_present": bool(sample.get("temperature_c")),
    }


def interface_complete(sample: dict[str, Any]) -> bool:
    report = interface_report(sample)
    return bool(
        report["group_count"]
        and report["group_count"] == report["complete_group_count"]
        and not report["unknown_paths"]
        and report["temperature_present"]
    )


def path_changes(first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
    first_values = first.get("throttle", {})
    last_values = last.get("throttle", {})
    shared = sorted(set(first_values) & set(last_values))
    changes: dict[str, Any] = {}
    for path in shared:
        identity = metric_identity(path)
        if identity is None:
            continue
        base, kind = identity
        before = int(first_values[path])
        after = int(last_values[path])
        changes[path] = {
            "group": base,
            "kind": kind,
            "before": before,
            "after": after,
            "delta": after - before,
        }
    return changes


def change_summary(changes: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for kind in FIELD_SUFFIXES:
        rows = [row for row in changes.values() if row.get("kind") == kind]
        deltas = [int(row["delta"]) for row in rows]
        summary[kind] = {
            "paths_compared": len(rows),
            "increment_paths": sum(delta > 0 for delta in deltas),
            "max_path_delta": max(deltas) if deltas else None,
            "min_path_delta": min(deltas) if deltas else None,
            "sum_intentionally_omitted": True,
        }
    return summary


def validate_fixture_sample(sample: Any, index: int) -> dict[str, Any]:
    if not isinstance(sample, dict):
        raise ValueError(f"Fixture sample {index} is not an object")
    required = {"elapsed_s", "throttle", "temperature_c"}
    missing = required - set(sample)
    if missing:
        raise ValueError(f"Fixture sample {index} is missing {sorted(missing)}")
    if not isinstance(sample["throttle"], dict) or not isinstance(
        sample["temperature_c"], dict
    ):
        raise ValueError(f"Fixture sample {index} fields have invalid types")
    normalized = dict(sample)
    normalized.setdefault(
        "max_sensor_c",
        max(sample["temperature_c"].values()) if sample["temperature_c"] else None,
    )
    return normalized


def load_fixture_sequence(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("Fixture sequence must be a non-empty JSON array")
    return [validate_fixture_sample(sample, index) for index, sample in enumerate(payload)]


def write_jsonl(path: Path, samples: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for sample in samples:
            stream.write(json.dumps(sample, sort_keys=True) + "\n")


def main() -> int:
    args = arguments()
    fixture_path = args.test_fixture_sequence.resolve()
    samples = load_fixture_sequence(fixture_path)

    evidence_root = args.evidence_root.resolve()
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_dir = evidence_root / args.run_id
    run_dir.mkdir(parents=False, exist_ok=False)
    write_jsonl(run_dir / "thermal_samples.jsonl", samples)

    first = samples[0]
    last = samples[-1]
    first_report = interface_report(first)
    last_report = interface_report(last)
    complete = interface_complete(first) and interface_complete(last)
    thermal_stop = any(
        sample.get("max_sensor_c") is not None
        and float(sample["max_sensor_c"]) >= THERMAL_STOP_C
        for sample in samples
    )
    if not complete:
        status = "MOCK_INTERFACE_INCOMPLETE"
        exit_code = 1
    elif thermal_stop:
        status = "MOCK_THERMAL_STOP"
        exit_code = 1
    else:
        status = "PASS_MOCK_THERMAL_SAMPLER"
        exit_code = 0

    changes = path_changes(first, last)
    result = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "stage": "D1_MOCK",
        "classification": "MOCK_CONTROL_FLOW_ONLY",
        "status": status,
        "configuration": {"thermal_stop_c": THERMAL_STOP_C},
        "implementation": {
            "sampler_sha256": sha256(Path(__file__).resolve()),
            "fixture_sha256": sha256(fixture_path),
        },
        "sample_count": len(samples),
        "interface_first": first_report,
        "interface_last": last_report,
        "max_sensor_c": max(
            float(sample["max_sensor_c"])
            for sample in samples
            if sample.get("max_sensor_c") is not None
        )
        if any(sample.get("max_sensor_c") is not None for sample in samples)
        else None,
        "throttle_changes": changes,
        "throttle_change_summary": change_summary(changes),
        "target_accessed": False,
        "execution_authorized": False,
        "evidence_files": {"samples": "thermal_samples.jsonl"},
        "interpretation_limits": [
            "This result used artificial input and contains no DK-2500 observation.",
            "Per-CPU package paths are preserved but never summed into independent events or duration.",
            "A passing D1 validates mock logic only and cannot authorize D2, Stability or deployment.",
        ],
    }
    atomic_json(run_dir / "result.json", result)
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
