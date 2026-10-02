"""Capture read-only host context before one Stage 2C attempt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
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
PREFLIGHT_ROOT = HERE / "evidence" / "stage2c_preflight"
WORKER_PATH = HERE / "stage2b_worker.py"
HELPER_PATH = HERE / "stage2c_proc_snapshot_helper.py"
RUNNER_PATH = HERE / "run_stage2c_proc_snapshot.py"
PREFLIGHT_PATH = HERE / "capture_stage2c_preflight.py"
MANIFEST_PATH = HERE / "STAGE2C_FROZEN_MANIFEST.json"
RUN_ID_PATTERN = re.compile(r"^stage2c_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Stage 2C context without initializing OpenVINO or the GPU."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError("run-id must match stage2c_r1_..., r2_..., or r3_...")
    destination = PREFLIGHT_ROOT / f"{args.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Preflight evidence already exists: {destination}")
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError("Stage 2C frozen manifest is required")

    hashes = {
        "baseline": sha256(BASELINE_SCRIPT),
        "worker": sha256(WORKER_PATH),
        "helper": sha256(HELPER_PATH),
        "runner": sha256(RUNNER_PATH),
        "preflight": sha256(PREFLIGHT_PATH),
    }
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    snapshot = {
        "schema_version": 1,
        "protocol_id": "EXP-2026-003-STAGE2C-PROC-THREAD-SNAPSHOT-V1",
        "run_id": args.run_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "captured_at_local": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "scope": "Read-only preflight context; OpenVINO and GPU are intentionally not initialized here.",
        "platform": platform.uname()._asdict(),
        "uptime": read_text(Path("/proc/uptime")),
        "memory": read_text(Path("/proc/meminfo")),
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
        "matching_process_names": matching_processes(),
        "dri_usage_best_effort": dri_usage(),
        "power_context_best_effort": power_context(),
        "interpretation_limits": [
            "A process-name filter cannot prove that no other GPU workload exists.",
            "Open DRM handles do not prove active GPU load.",
            "OpenVINO identity is captured by the worker result to avoid extra pre-run initialization.",
        ],
    }
    if not snapshot["frozen_manifest_matches"]:
        raise RuntimeError("Stage 2C implementation differs from frozen manifest")
    if not snapshot["baseline_hash_matches_historical_manifest"]:
        raise RuntimeError("Historical baseline hash changed")
    destination.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"Saved Stage 2C preflight evidence: {destination}")


if __name__ == "__main__":
    main()
