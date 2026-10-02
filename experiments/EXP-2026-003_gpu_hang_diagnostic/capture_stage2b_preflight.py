"""Capture a read-only host snapshot before one Stage 2B attempt."""

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
    matching_processes,
    power_context,
    read_text,
    dri_usage,
    sha256,
)


HERE = Path(__file__).resolve().parent
PREFLIGHT_ROOT = HERE / "evidence" / "stage2b_preflight"
WORKER_PATH = HERE / "stage2b_worker.py"
RUN_ID_PATTERN = re.compile(r"^stage2b_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Stage 2B context without initializing OpenVINO or the GPU."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError(
            "run-id must match stage2b_r1_..., stage2b_r2_..., or stage2b_r3_..."
        )
    destination = PREFLIGHT_ROOT / f"{args.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Preflight evidence already exists: {destination}")

    baseline_hash = sha256(BASELINE_SCRIPT)
    snapshot = {
        "schema_version": 1,
        "protocol_id": "EXP-2026-003-STAGE2B-INFER-BOUNDARY-SHARED-STATE-V1",
        "run_id": args.run_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "captured_at_local": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "scope": "Read-only preflight context; OpenVINO and GPU are intentionally not initialized here.",
        "platform": platform.uname()._asdict(),
        "uptime": read_text(Path("/proc/uptime")),
        "memory": read_text(Path("/proc/meminfo")),
        "artifacts_sha256": {
            "baseline_script": baseline_hash,
            "stage2b_worker": sha256(WORKER_PATH),
            "ir_xml": sha256(PACKAGE_DIR / "act_fp32.xml"),
            "ir_bin": sha256(PACKAGE_DIR / "act_fp32.bin"),
            "reference_input": sha256(PACKAGE_DIR / "reference_model_input.pt"),
            "reference_output": sha256(PACKAGE_DIR / "reference_output_normalized.pt"),
        },
        "baseline_hash_matches_frozen_manifest": baseline_hash
        == EXPECTED_BASELINE_SHA256,
        "matching_process_names": matching_processes(),
        "dri_usage_best_effort": dri_usage(),
        "power_context_best_effort": power_context(),
        "interpretation_limits": [
            "A process-name filter cannot prove that no other GPU workload exists.",
            "Open DRM handles do not prove active GPU load.",
            "OpenVINO identity is captured by the worker result to avoid extra pre-run initialization.",
        ],
    }
    destination.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"Saved Stage 2B preflight evidence: {destination}")


if __name__ == "__main__":
    main()
