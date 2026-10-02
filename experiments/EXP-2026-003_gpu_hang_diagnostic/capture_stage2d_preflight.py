"""Capture read-only host context before one Stage 2D attempt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from capture_stage2a_preflight import (
    BASELINE_SCRIPT,
    EXPECTED_BASELINE_SHA256,
    PACKAGE_DIR,
    dri_usage,
    matching_processes,
    power_context,
    read_text,
    sha256,
)


HERE = Path(__file__).resolve().parent
PREFLIGHT_ROOT = HERE / "evidence" / "stage2d_preflight"
WORKER_PATH = HERE / "stage2d_worker.py"
RUNNER_PATH = HERE / "run_stage2d_gdb_stack.py"
PREFLIGHT_PATH = HERE / "capture_stage2d_preflight.py"
MANIFEST_PATH = HERE / "STAGE2D_FROZEN_MANIFEST.json"
GDB_PATH = Path("/usr/bin/gdb")
RUN_ID_PATTERN = re.compile(r"^stage2d_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Stage 2D context without initializing OpenVINO or the GPU."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def command_output(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
        check=False,
    )
    return {"returncode": completed.returncode, "output": completed.stdout.strip()}


def build_id(path: Path) -> dict[str, object]:
    return command_output(["readelf", "-n", str(path)])


def main() -> None:
    args = arguments()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError("run-id must match stage2d_r1_..., r2_..., or r3_...")
    destination = PREFLIGHT_ROOT / f"{args.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Preflight evidence already exists: {destination}")
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError("Stage 2D frozen manifest is required")

    hashes = {
        "baseline": sha256(BASELINE_SCRIPT),
        "worker": sha256(WORKER_PATH),
        "runner": sha256(RUNNER_PATH),
        "preflight": sha256(PREFLIGHT_PATH),
        "gdb": sha256(GDB_PATH),
    }
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    openvino_lib = Path(
        "/home/lucas/intel_ws/openvino_env/lib/python3.12/site-packages/openvino/libs/libopenvino.so.2631"
    )
    gpu_plugin = Path(
        "/home/lucas/intel_ws/openvino_env/lib/python3.12/site-packages/openvino/libs/libopenvino_intel_gpu_plugin.so"
    )
    level_zero = Path("/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1")
    snapshot = {
        "schema_version": 1,
        "protocol_id": "EXP-2026-003-STAGE2D-BOUNDED-NATIVE-STACK-V1",
        "run_id": args.run_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "captured_at_local": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "scope": "Read-only preflight context; OpenVINO and GPU are intentionally not initialized here.",
        "platform": platform.uname()._asdict(),
        "uptime": read_text(Path("/proc/uptime")),
        "memory": read_text(Path("/proc/meminfo")),
        "ptrace_scope": read_text(Path("/proc/sys/kernel/yama/ptrace_scope")),
        "gdb_version": command_output([str(GDB_PATH), "--version"]),
        "artifacts_sha256": hashes,
        "frozen_manifest_matches": manifest.get("artifacts_sha256") == hashes,
        "baseline_hash_matches_historical_manifest": hashes["baseline"]
        == EXPECTED_BASELINE_SHA256,
        "model_artifacts_sha256": {
            "ir_xml": sha256(PACKAGE_DIR / "act_fp32.xml"),
            "ir_bin": sha256(PACKAGE_DIR / "act_fp32.bin"),
            "reference_input": sha256(PACKAGE_DIR / "reference_model_input.pt"),
            "reference_output": sha256(PACKAGE_DIR / "reference_output_normalized.pt"),
        },
        "native_library_build_ids": {
            "openvino_runtime": build_id(openvino_lib),
            "intel_gpu_plugin": build_id(gpu_plugin),
            "level_zero_intel_gpu": build_id(level_zero),
        },
        "matching_process_names": matching_processes(),
        "dri_usage_best_effort": dri_usage(),
        "power_context_best_effort": power_context(),
        "interpretation_limits": [
            "Build IDs identify binaries; they do not provide missing debug symbols.",
            "A process-name filter cannot prove that no other GPU workload exists.",
            "Open DRM handles do not prove active GPU load.",
            "OpenVINO identity is captured by the worker result to avoid extra pre-run initialization.",
        ],
    }
    if not snapshot["frozen_manifest_matches"]:
        raise RuntimeError("Stage 2D implementation differs from frozen manifest")
    if not snapshot["baseline_hash_matches_historical_manifest"]:
        raise RuntimeError("Historical baseline hash changed")
    destination.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"Saved Stage 2D preflight evidence: {destination}")


if __name__ == "__main__":
    main()
