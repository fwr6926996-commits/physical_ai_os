"""Capture a read-only Phase 3 V2.9 hardware and software baseline on the host."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openvino as ov


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EVIDENCE_DIR = HERE / "evidence" / "phase3_0_baseline"
L1_DOC = REPO / "docs/reference/l1/SO-101_PhysicalAI_Runtime_L1_最终执行书_V2.9_S1S2_EmploymentGate增强版.docx"
AGENT_POLICY = REPO / "AGENT.md"
LEROBOT_REPO = Path("/home/lucas/lerobot")
DATASET = Path("/data/datasets/so101_pick_place_cube_v1_20260803_014054")
CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")
POLICY_PACKAGE = HERE.parent / "policy_package_v1"


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None:
        return {
            "command": command,
            "status": "NOT_FOUND",
            "returncode": None,
            "stdout": "",
            "stderr": f"{command[0]} is not installed",
        }
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    return {
        "command": command,
        "status": "PASS" if completed.returncode == 0 else "COMMAND_FAILED",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def safe_dmi_identity() -> dict[str, str | None]:
    dmi = Path("/sys/class/dmi/id")
    result: dict[str, str | None] = {}
    for name in ("sys_vendor", "product_name", "product_version", "board_name", "bios_version"):
        path = dmi / name
        try:
            result[name] = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            result[name] = None
    # Keep a stable identity check without storing the raw machine UUID or serial.
    identity_parts: list[str] = []
    for name in ("product_uuid", "product_serial", "board_serial"):
        path = dmi / name
        try:
            value = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if value:
            identity_parts.append(value)
    result["identity_sha256"] = hashlib.sha256("|".join(identity_parts).encode()).hexdigest() if identity_parts else None
    return result


def openvino_devices() -> dict[str, Any]:
    core = ov.Core()
    devices: list[dict[str, Any]] = []
    for device in core.available_devices:
        record: dict[str, Any] = {"device": device}
        for label, prop in (
            ("full_name", ov.properties.device.full_name),
            ("architecture", ov.properties.device.architecture),
            ("capabilities", ov.properties.device.capabilities),
            ("type", ov.properties.device.type),
        ):
            try:
                value = core.get_property(device, prop)
                record[label] = list(value) if isinstance(value, tuple) else str(value) if not isinstance(value, (str, int, float, bool, list, dict, type(None))) else value
            except Exception as error:  # property support differs by plugin
                record[label] = {"status": "UNAVAILABLE", "error": str(error)}
        devices.append(record)
    return {
        "version": ov.__version__,
        "python": sys.version.replace("\n", " "),
        "available_devices": list(core.available_devices),
        "devices": devices,
    }


def artifact_identity() -> dict[str, Any]:
    files = {
        "l1_v2_9_document": L1_DOC,
        "agent_policy": AGENT_POLICY,
        "checkpoint_config": CHECKPOINT / "config.json",
        "checkpoint_model": CHECKPOINT / "model.safetensors",
        "checkpoint_preprocessor": CHECKPOINT / "policy_preprocessor.json",
        "checkpoint_postprocessor": CHECKPOINT / "policy_postprocessor.json",
        "policy_ir_xml": POLICY_PACKAGE / "act_cpu_reference.xml",
        "policy_ir_bin": POLICY_PACKAGE / "act_cpu_reference.bin",
        "frozen_model_input": POLICY_PACKAGE / "reference_model_input.pt",
        "frozen_model_output": POLICY_PACKAGE / "reference_output_normalized.pt",
    }
    return {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path),
        }
        for name, path in files.items()
    }


def main() -> None:
    timestamp = datetime.now(timezone.utc)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    output = EVIDENCE_DIR / f"baseline_{timestamp.strftime('%Y%m%dT%H%M%SZ')}.json"

    commands = {
        "os_release": run(["cat", "/etc/os-release"]),
        "kernel": run(["uname", "-a"]),
        "cpu": run(["lscpu"]),
        "memory": run(["free", "-b"]),
        "memory_blocks": run(["lsmem", "--json"]),
        "pci_drivers": run(["lspci", "-nnk"]),
        "identity": run(["id"]),
        "device_nodes_dri": run(["ls", "-la", "/dev/dri"]),
        "device_nodes_accel": run(["ls", "-la", "/dev/accel"]),
        "kernel_modules": run(["lsmod"]),
        "data_mount": run(["findmnt", "-J", "/data"]),
        "disk_space": run(["df", "-B1", "/", "/data"]),
        "block_devices": run(["lsblk", "-J", "-o", "NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,UUID,MOUNTPOINTS,ROTA,RO"]),
        "opencl_devices": run(["clinfo", "-l"]),
        "temperature_sensors": run(["sensors", "-j"]),
        "nvidia_smi": run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        "project_git_head": run(["git", "rev-parse", "HEAD"], cwd=REPO),
        "project_git_status": run(["git", "status", "--short"], cwd=REPO),
        "lerobot_git_describe": run(["git", "describe", "--tags", "--always", "--dirty"], cwd=LEROBOT_REPO),
        "lerobot_git_head": run(["git", "rev-parse", "HEAD"], cwd=LEROBOT_REPO),
        "lerobot_git_status": run(["git", "status", "--short"], cwd=LEROBOT_REPO),
        "python_packages": run([sys.executable, "-m", "pip", "freeze"]),
    }

    payload = {
        "schema_version": 1,
        "phase": "Phase 3 V2.9 baseline",
        "captured_at_utc": timestamp.isoformat(),
        "hostname": platform.node(),
        "execution_context": {
            "cwd": os.getcwd(),
            "python_executable": sys.executable,
            "expected_context": "ordinary host terminal, not a device-isolated sandbox",
        },
        "dmi": safe_dmi_identity(),
        "openvino": openvino_devices(),
        "artifacts": artifact_identity(),
        "dataset": {
            "path": str(DATASET),
            "exists": DATASET.exists(),
        },
        "checkpoint": {
            "path": str(CHECKPOINT),
            "exists": CHECKPOINT.exists(),
        },
        "commands": commands,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved baseline: {output}")
    print(f"OpenVINO: {payload['openvino']['version']}")
    print("available_devices:", payload["openvino"]["available_devices"])
    for item in payload["openvino"]["devices"]:
        print(f"  {item['device']} => {item.get('full_name')}")
    print("Memory summary:", commands["memory"]["stdout"].strip().splitlines()[:2])
    print("/data mount status:", commands["data_mount"]["status"])
    print("Temperature tool status:", commands["temperature_sensors"]["status"])
    print("Artifact hashes captured:", sum(1 for item in payload["artifacts"].values() if item["sha256"]))

    expected_devices = {"CPU", "GPU.0", "GPU.1", "NPU"}
    observed_devices = set(payload["openvino"]["available_devices"])
    if not expected_devices.issubset(observed_devices):
        print(
            "BASELINE GATE: NEEDS REVIEW; expected host devices are not all visible: "
            f"missing={sorted(expected_devices - observed_devices)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if commands["data_mount"]["status"] != "PASS":
        print("BASELINE GATE: NEEDS REVIEW; /data mount was not verified", file=sys.stderr)
        raise SystemExit(3)
    print("BASELINE GATE: PASS")


if __name__ == "__main__":
    main()
