"""Draft Stage 2E-A runner for one bounded main-thread module-offset capture."""

from __future__ import annotations

import argparse
import functools
import importlib
import json
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from run_stage2b_shared_boundary import FROZEN_ARGUMENTS, classify_boundary, stable_snapshot
from run_stage2d_gdb_stack import decoded_timeout_output, process_state, sha256, write_raw_output
from stage2e_offset_evidence import gdb_command, offset_quality


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
WORKER_PATH = HERE / "stage2d_worker.py"
RUNNER_PATH = HERE / "run_stage2e_offset_capture.py"
HELPER_PATH = HERE / "stage2e_offset_evidence.py"
PREFLIGHT_SCRIPT = HERE / "capture_stage2e_preflight.py"
MANIFEST_PATH = HERE / "STAGE2E_DRAFT_MANIFEST.json"
GDB_PATH = Path("/usr/bin/gdb")
OPENCL_RUNTIME_PATH = Path("/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so")
EVIDENCE_ROOT = HERE / "evidence" / "stage2e"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2e_preflight"
STAGE2D_CLOSURE = HERE / "STAGE2D_CLOSURE.md"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
RUN_ID_PATTERN = re.compile(r"^stage2e_a1_[A-Za-z0-9][A-Za-z0-9._-]*$")
GDB_TIMEOUT_SECONDS = 2.0
PROTOCOL_ID = "EXP-2026-003-STAGE2E-A-MODULE-OFFSET-CAPTURE-V1"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One human-started Stage 2E-A module-offset attempt."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def implementation_hashes() -> dict[str, str]:
    return {
        "baseline": sha256(BASELINE_SCRIPT),
        "worker": sha256(WORKER_PATH),
        "runner": sha256(RUNNER_PATH),
        "offset_helper": sha256(HELPER_PATH),
        "preflight": sha256(PREFLIGHT_SCRIPT),
        "gdb": sha256(GDB_PATH),
        "opencl_runtime": sha256(OPENCL_RUNTIME_PATH),
    }


def verify_execution_gate(run_id: str) -> dict[str, object]:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run-id must match stage2e_a1_...")
    if not STAGE2D_CLOSURE.exists():
        raise FileNotFoundError("Stage 2D closure is required")
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError("Stage 2E manifest is required")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("Stage 2E manifest protocol mismatch")
    if manifest.get("execution_state") != "READY_FOR_ONE_APPROVED_ATTEMPT":
        raise RuntimeError(
            "Stage 2E real GPU execution is blocked: manifest is not approved/frozen"
        )
    existing = list(EVIDENCE_ROOT.glob("stage2e_a1_*"))
    if existing:
        raise RuntimeError(f"Stage 2E permits one attempt only; evidence already exists: {existing}")
    hashes = implementation_hashes()
    if hashes["baseline"] != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("Historical baseline hash changed")
    if manifest.get("artifacts_sha256") != hashes:
        raise RuntimeError("Stage 2E implementation differs from approved frozen manifest")
    return manifest


def bounded_offset_capture_then_stop(
    process: mp.Process,
    original_stop: Callable[[mp.Process], str],
    output_path: Path,
    control: dict[str, object],
    helper_command: list[str] | None = None,
    timeout_seconds: float = GDB_TIMEOUT_SECONDS,
) -> str:
    started = time.monotonic()
    command = helper_command or gdb_command(GDB_PATH, process.pid)
    control.update({"invoked": True, "target_pid": process.pid, "command": command})
    output = ""
    try:
        try:
            completed = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
            output = completed.stdout
            control["helper_returncode"] = completed.returncode
        except subprocess.TimeoutExpired as exc:
            output = decoded_timeout_output(exc)
            control["helper_timeout"] = True
        except Exception as exc:
            control["helper_error"] = f"{type(exc).__name__}: {exc}"
            output = str(control["helper_error"])
        try:
            write_raw_output(output_path, output)
        except Exception as exc:
            control["output_write_error"] = f"{type(exc).__name__}: {exc}"
        control["output_bytes"] = len(output.encode("utf-8", errors="replace"))
        control["target_state_after_helper"] = process_state(process.pid)
    finally:
        control["snapshot_delay_seconds"] = time.monotonic() - started
        recovery = original_stop(process)
        control["recovery"] = recovery
    return recovery


def main() -> None:
    args = arguments()
    verify_execution_gate(args.run_id)
    hashes = implementation_hashes()

    preflight_path = PREFLIGHT_ROOT / f"{args.run_id}.json"
    if not preflight_path.exists():
        raise FileNotFoundError(f"Matching Stage 2E preflight required: {preflight_path}")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("run_id") != args.run_id:
        raise RuntimeError("Preflight run_id does not match")
    if preflight.get("artifacts_sha256") != hashes:
        raise RuntimeError("Preflight implementation hashes do not match")
    captured_at = datetime.fromisoformat(str(preflight["captured_at_utc"]))
    age = datetime.now(timezone.utc) - captured_at
    if age < timedelta(minutes=-5) or age > timedelta(minutes=30):
        raise RuntimeError(f"Preflight must be 0–30 minutes old; observed age={age}")

    run_dir = EVIDENCE_ROOT / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Stage 2E evidence already exists: {run_dir}")
    raw_path = run_dir / "gdb_offset_capture.txt"
    gdb_control: dict[str, object] = {"invoked": False}

    sys.path.insert(0, str(PHASE3_DIR))
    baseline = importlib.import_module("run_isolated_gpu_stability_v2_9")
    worker_module = importlib.import_module("stage2d_worker")
    enter_sequence = mp.RawValue("Q", 0)
    return_sequence = mp.RawValue("Q", 0)
    baseline.inference_worker = functools.partial(
        worker_module.inference_worker, enter_sequence, return_sequence
    )
    original_stop = baseline.stop_worker
    baseline.stop_worker = functools.partial(
        bounded_offset_capture_then_stop,
        original_stop=original_stop,
        output_path=raw_path,
        control=gdb_control,
    )
    baseline.EVIDENCE_ROOT = EVIDENCE_ROOT
    sys.argv = [
        str(BASELINE_SCRIPT),
        "--run-id",
        args.run_id,
        "--duration-minutes",
        str(FROZEN_ARGUMENTS["duration_minutes"]),
        "--warmup",
        str(FROZEN_ARGUMENTS["warmup"]),
        "--stall-seconds",
        str(FROZEN_ARGUMENTS["stall_seconds"]),
        "--startup-seconds",
        str(FROZEN_ARGUMENTS["startup_seconds"]),
        "--telemetry-seconds",
        str(FROZEN_ARGUMENTS["telemetry_seconds"]),
        "--window-seconds",
        str(FROZEN_ARGUMENTS["window_seconds"]),
    ]
    baseline.main()

    boundary_snapshot = stable_snapshot(enter_sequence, return_sequence)
    baseline_result_path = run_dir / "result.json"
    baseline_result = json.loads(baseline_result_path.read_text(encoding="utf-8"))
    infer_classification, derived_boundary = classify_boundary(
        baseline_result, boundary_snapshot, int(FROZEN_ARGUMENTS["warmup"])
    )
    output = raw_path.read_text(encoding="utf-8", errors="replace") if raw_path.exists() else ""
    quality, offset_evidence = offset_quality(
        baseline_result, gdb_control, output, OPENCL_RUNTIME_PATH
    )
    worker_ready = baseline_result.get("worker_ready")
    ptrace_authorization = (
        worker_ready.get("ptrace_authorization") if isinstance(worker_ready, dict) else None
    )
    ptrace_authorization_valid = (
        isinstance(ptrace_authorization, dict)
        and ptrace_authorization.get("returncode") == 0
        and ptrace_authorization.get("errno") == 0
        and ptrace_authorization.get("authorized_supervisor_pid") == os.getpid()
    )
    if isinstance(worker_ready, dict) and not ptrace_authorization_valid:
        quality = "GDB_AUTHORIZATION_INVALID"
        offset_evidence = {"valid": False, "error": "GDB_AUTHORIZATION_INVALID"}

    result = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": PROTOCOL_ID,
        "run_id": args.run_id,
        "infer_classification": infer_classification,
        "offset_evidence_quality": quality,
        "offset_evidence": offset_evidence,
        "phase3_qualification_round": False,
        "implementation_sha256": hashes,
        "frozen_arguments": FROZEN_ARGUMENTS,
        "gdb_timeout_seconds": GDB_TIMEOUT_SECONDS,
        "ptrace_authorization": ptrace_authorization,
        "ptrace_authorization_valid": ptrace_authorization_valid,
        "gdb_control": gdb_control,
        "shared_boundary_snapshot": boundary_snapshot,
        "derived_boundary": derived_boundary,
        "preflight_evidence": str(preflight_path.relative_to(HERE)),
        "preflight_sha256": sha256(preflight_path),
        "baseline_result": baseline_result_path.name,
        "gdb_raw_output": raw_path.name if raw_path.exists() else None,
        "gdb_raw_output_sha256": sha256(raw_path) if raw_path.exists() else None,
        "interpretation_limits": [
            "A stable module offset identifies a stopped-time location, not a causal component.",
            "A source candidate cannot be assigned without matched symbols or a verified binary mapping.",
            "GDB changes scheduling and delays recovery for a bounded interval.",
            "No Stage 2E result is GPU admission evidence.",
        ],
    }
    result_path = run_dir / "stage2e_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved Stage 2E result: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()

