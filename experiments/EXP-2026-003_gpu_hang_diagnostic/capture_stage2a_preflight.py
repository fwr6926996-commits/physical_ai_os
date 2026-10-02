"""Capture a read-only host snapshot before one Stage 2A reproduction attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
PACKAGE_DIR = PHASE3_DIR / "policy_package_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2a_preflight"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
RUN_ID_PATTERN = re.compile(r"^stage2a_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Stage 2A context without initializing OpenVINO or the GPU."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> dict[str, object]:
    try:
        return {"status": "READ", "value": path.read_text(errors="replace").strip()}
    except OSError as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


def run_read_only(command: list[str]) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10.0,
            check=False,
        )
        return {
            "status": "CAPTURED",
            "command": command,
            "returncode": completed.returncode,
            "output": completed.stdout.strip(),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "UNAVAILABLE",
            "command": command,
            "error": f"{type(exc).__name__}: {exc}",
        }


def matching_processes() -> list[dict[str, object]]:
    keywords = ("gpu", "python", "train", "infer", "benchmark", "openvino", "torch")
    matches: list[dict[str, object]] = []
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        try:
            command = (proc_dir / "comm").read_text(errors="replace").strip()
            parent_pid = None
            for line in (proc_dir / "status").read_text(errors="replace").splitlines():
                if line.startswith("PPid:"):
                    parent_pid = int(line.split()[1])
                    break
        except (OSError, ValueError):
            continue
        if any(keyword in command.lower() for keyword in keywords):
            matches.append(
                {"pid": int(proc_dir.name), "ppid": parent_pid, "command_name": command}
            )
    return sorted(matches, key=lambda item: int(item["pid"]))


def dri_usage() -> dict[str, object]:
    dri_root = Path("/dev/dri")
    try:
        devices = sorted(path for path in dri_root.iterdir() if path.is_char_device())
    except OSError as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}
    if not devices:
        return {"status": "UNAVAILABLE", "error": "No character devices found in /dev/dri"}
    names = [str(path) for path in devices]
    return {
        "status": "CAPTURED",
        "devices": names,
        "fuser": run_read_only(["fuser", "-v", *names]),
        "lsof": run_read_only(["lsof", *names]),
    }


def power_context() -> dict[str, object]:
    online_files = sorted(Path("/sys/class/power_supply").glob("*/online"))
    online = {str(path): read_text(path) for path in online_files}
    return {
        "ac_online": online if online else {"status": "UNAVAILABLE"},
        "platform_profile": read_text(Path("/sys/firmware/acpi/platform_profile")),
    }


def main() -> None:
    args = arguments()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError(
            "run-id must match stage2a_r1_..., stage2a_r2_..., or stage2a_r3_..."
        )
    destination = PREFLIGHT_ROOT / f"{args.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Preflight evidence already exists: {destination}")

    baseline_hash = sha256(BASELINE_SCRIPT)
    artifacts = {
        "baseline_script": baseline_hash,
        "ir_xml": sha256(PACKAGE_DIR / "act_fp32.xml"),
        "ir_bin": sha256(PACKAGE_DIR / "act_fp32.bin"),
        "reference_input": sha256(PACKAGE_DIR / "reference_model_input.pt"),
        "reference_output": sha256(PACKAGE_DIR / "reference_output_normalized.pt"),
    }
    snapshot = {
        "schema_version": 1,
        "protocol_id": "EXP-2026-003-STAGE2A-CURRENT-REPRODUCTION-BASELINE-V1",
        "run_id": args.run_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "captured_at_local": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "scope": "Read-only preflight context; OpenVINO and GPU are intentionally not initialized here.",
        "platform": platform.uname()._asdict(),
        "uptime": read_text(Path("/proc/uptime")),
        "memory": read_text(Path("/proc/meminfo")),
        "artifacts_sha256": artifacts,
        "baseline_hash_matches_frozen_manifest": baseline_hash
        == EXPECTED_BASELINE_SHA256,
        "matching_process_names": matching_processes(),
        "dri_usage_best_effort": dri_usage(),
        "power_context_best_effort": power_context(),
        "interpretation_limits": [
            "A process-name filter cannot prove that no other GPU workload exists.",
            "Empty fuser or lsof output means no user was observed by that command, not that GPU idleness is proven.",
            "OpenVINO identity is captured by the historical worker result to avoid an extra pre-run runtime initialization.",
        ],
    }
    destination.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"Saved Stage 2A preflight evidence: {destination}")


if __name__ == "__main__":
    main()
