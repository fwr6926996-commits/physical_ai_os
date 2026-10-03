#!/usr/bin/env python3
"""Validate the frozen Phase 4 target contract without reading or compiling the model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import openvino as ov
import psutil
import torch


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "phase4_frozen_config.json"
IMPLEMENTATION_FILES = (
    "phase4_frozen_config.json",
    "phase4_no_model_preflight.py",
    "phase4_prepost.py",
    "phase4_cpu_worker.py",
    "phase4_cpu_supervisor.py",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def readable_throttle_files() -> list[str]:
    return [
        str(path)
        for path in sorted(
            Path("/sys/devices/system/cpu").glob(
                "cpu[0-9]*/thermal_throttle/*throttle_count"
            )
        )
        if os.access(path, os.R_OK)
    ]


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite preflight evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    checks: dict[str, Any] = {}

    checks["openvino_version"] = {
        "expected": config["openvino_version"],
        "actual": ov.__version__,
        "pass": ov.__version__ == config["openvino_version"],
    }
    core = ov.Core()
    available = list(core.available_devices)
    full_name = (
        core.get_property(config["device"], ov.properties.device.full_name)
        if config["device"] in available
        else None
    )
    checks["device"] = {
        "expected": config["device"],
        "available": available,
        "pass": config["device"] in available,
    }
    checks["cpu_identity"] = {
        "expected": config["cpu_full_name"],
        "actual": full_name,
        "pass": full_name == config["cpu_full_name"],
    }
    package_dir = args.package_dir.resolve()
    artifact_checks = {}
    for name, expected in config["artifacts"].items():
        path = package_dir / name
        actual = sha256(path) if path.is_file() else None
        artifact_checks[name] = {
            "expected": expected,
            "actual": actual,
            "pass": actual == expected,
        }
    checks["artifacts"] = artifact_checks

    temperatures = psutil.sensors_temperatures(fahrenheit=False)
    labels = {
        group: [item.label for item in entries] for group, entries in temperatures.items()
    }
    checks["temperature_interface"] = {
        "groups": sorted(temperatures),
        "labels": labels,
        "pass": "coretemp" in temperatures
        and any(item.label == "Package id 0" for item in temperatures["coretemp"]),
    }
    throttle_files = readable_throttle_files()
    checks["throttle_interface"] = {
        "readable_file_count": len(throttle_files),
        "pass": bool(throttle_files),
    }
    checks["frequency_interface"] = {
        "sample_count": len(psutil.cpu_freq(percpu=True) or []),
        "pass": bool(psutil.cpu_freq(percpu=True) or []),
    }
    checks["dependencies"] = {
        "python": platform.python_version(),
        "openvino": ov.__version__,
        "numpy": np.__version__,
        "psutil": psutil.__version__,
        "torch": torch.__version__,
        "pass": True,
    }
    checks["implementation_hashes"] = {
        name: sha256(HERE / name) for name in IMPLEMENTATION_FILES
    }
    checks["output_parent_writable"] = {
        "path": str(output.parent),
        "pass": os.access(output.parent, os.W_OK),
    }

    def passed(value: Any) -> bool:
        if isinstance(value, dict) and "pass" in value:
            return bool(value["pass"])
        if isinstance(value, dict):
            return all(passed(item) for item in value.values())
        return True

    overall_pass = all(passed(value) for value in checks.values())
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": config["protocol_id"],
        "protocol_snapshot": config["protocol_snapshot"],
        "status": "PASS_NO_MODEL_PREFLIGHT" if overall_pass else "FAIL_NO_MODEL_PREFLIGHT",
        "scope": "Identity, dependency, artifact, sensor and path checks only; no model read, compile or inference.",
        "platform": platform.platform(),
        "python_executable": sys.executable,
        "package_dir": str(package_dir),
        "checks": checks,
        "execution_authorized": False,
        "interpretation_limits": [
            "A passing preflight does not prove model compatibility or correctness.",
            "A passing preflight does not authorize a qualification stage.",
        ],
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    print(json.dumps(result, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
