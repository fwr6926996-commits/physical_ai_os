"""Run Stage 2C with one bounded pre-recovery /proc snapshot."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import json
import multiprocessing as mp
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from run_stage2b_shared_boundary import (
    FROZEN_ARGUMENTS,
    classify_boundary,
    stable_snapshot,
)


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
WORKER_PATH = HERE / "stage2b_worker.py"
HELPER_PATH = HERE / "stage2c_proc_snapshot_helper.py"
PREFLIGHT_SCRIPT = HERE / "capture_stage2c_preflight.py"
MANIFEST_PATH = HERE / "STAGE2C_FROZEN_MANIFEST.json"
EVIDENCE_ROOT = HERE / "evidence" / "stage2c"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2c_preflight"
STAGE2B_CLOSURE = HERE / "STAGE2B_CLOSURE.md"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
EXPECTED_WORKER_SHA256 = (
    "7093c14a6b6eeed5fb3aa234a6e05c96b89d1e1039c661872e028490377f5672"
)
RUN_ID_PATTERN = re.compile(r"^stage2c_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")
SNAPSHOT_TIMEOUT_SECONDS = 2.0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One human-started Stage 2C bounded /proc snapshot attempt."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sequence(round_number: int) -> None:
    same_round = list(EVIDENCE_ROOT.glob(f"stage2c_r{round_number}_*"))
    if same_round:
        raise RuntimeError(
            f"Stage 2C round {round_number} already has evidence: {same_round}"
        )
    for prior_round in range(1, round_number):
        records = list(
            EVIDENCE_ROOT.glob(f"stage2c_r{prior_round}_*/stage2c_result.json")
        )
        if len(records) != 1:
            raise RuntimeError(
                f"Round {round_number} requires one reviewed round {prior_round}; found={records}"
            )
        record = json.loads(records[0].read_text(encoding="utf-8"))
        if (
            record.get("infer_classification")
            != "NO_HANG_REPRODUCED_5M_COMPLETE"
        ):
            raise RuntimeError(
                f"Stop rule blocks round {round_number}; round {prior_round} infer_classification={record.get('infer_classification')}"
            )


def write_fallback_snapshot(
    output_path: Path, pid: int, status: str, detail: str, elapsed: float
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                "pid": pid,
                "status": status,
                "detail": detail,
                "elapsed_seconds": elapsed,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def bounded_snapshot_then_stop(
    process: mp.Process,
    original_stop: Callable[[mp.Process], str],
    output_path: Path,
    control: dict[str, object],
    helper_command: list[str] | None = None,
    timeout_seconds: float = SNAPSHOT_TIMEOUT_SECONDS,
) -> str:
    started = time.monotonic()
    command = helper_command or [
        sys.executable,
        str(HELPER_PATH),
        "--pid",
        str(process.pid),
        "--output",
        str(output_path),
    ]
    control["invoked"] = True
    control["target_pid"] = process.pid
    control["command"] = command
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
            control["helper_returncode"] = completed.returncode
            control["helper_output"] = completed.stdout.strip()
            if completed.returncode != 0 and not output_path.exists():
                write_fallback_snapshot(
                    output_path,
                    process.pid,
                    "HELPER_FAILED",
                    completed.stdout.strip(),
                    time.monotonic() - started,
                )
        except subprocess.TimeoutExpired as exc:
            write_fallback_snapshot(
                output_path,
                process.pid,
                "HELPER_TIMEOUT",
                f"Snapshot helper exceeded {timeout_seconds}s: {exc}",
                time.monotonic() - started,
            )
            control["helper_timeout"] = True
        except Exception as exc:
            control["helper_error"] = f"{type(exc).__name__}: {exc}"
            try:
                write_fallback_snapshot(
                    output_path,
                    process.pid,
                    "HELPER_FAILED",
                    str(control["helper_error"]),
                    time.monotonic() - started,
                )
            except Exception as fallback_exc:
                control["fallback_write_error"] = (
                    f"{type(fallback_exc).__name__}: {fallback_exc}"
                )
    finally:
        control["snapshot_delay_seconds"] = time.monotonic() - started
        recovery = original_stop(process)
        control["recovery"] = recovery
    return recovery


def proc_quality(
    baseline_result: dict[str, object], control: dict[str, object], snapshot: dict[str, object] | None
) -> str:
    if baseline_result.get("status") != "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED":
        return "PROC_SNAPSHOT_NOT_TRIGGERED_NO_HANG"
    if not control.get("invoked") or snapshot is None:
        return "PROC_SNAPSHOT_FAILED"
    status = snapshot.get("status")
    if status == "CAPTURED_COMPLETE":
        return "PROC_SNAPSHOT_COMPLETE_WITHIN_BUDGET"
    if status == "CAPTURED_PARTIAL":
        return "PROC_SNAPSHOT_PARTIAL_WITHIN_BUDGET"
    if status == "HELPER_TIMEOUT":
        return "PROC_SNAPSHOT_TIMEOUT"
    return "PROC_SNAPSHOT_FAILED"


def main() -> None:
    args = arguments()
    match = RUN_ID_PATTERN.fullmatch(args.run_id)
    if not match:
        raise ValueError("run-id must match stage2c_r1_..., r2_..., or r3_...")
    round_number = int(match.group("round"))
    verify_sequence(round_number)
    if not STAGE2B_CLOSURE.exists():
        raise FileNotFoundError("Stage 2B closure is required")

    hashes = {
        "baseline": sha256(BASELINE_SCRIPT),
        "worker": sha256(WORKER_PATH),
        "helper": sha256(HELPER_PATH),
        "runner": sha256(Path(__file__)),
        "preflight": sha256(PREFLIGHT_SCRIPT),
    }
    if hashes["baseline"] != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("Historical baseline hash changed")
    if hashes["worker"] != EXPECTED_WORKER_SHA256:
        raise RuntimeError("Frozen Stage 2B worker hash changed")
    if not MANIFEST_PATH.exists():
        raise RuntimeError("Stage 2C frozen manifest is missing")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != "EXP-2026-003-STAGE2C-PROC-THREAD-SNAPSHOT-V1":
        raise RuntimeError("Stage 2C frozen manifest protocol mismatch")
    if manifest.get("artifacts_sha256") != hashes:
        raise RuntimeError(
            f"Stage 2C implementation differs from frozen manifest: expected={manifest.get('artifacts_sha256')} actual={hashes}"
        )

    preflight_path = PREFLIGHT_ROOT / f"{args.run_id}.json"
    if not preflight_path.exists():
        raise FileNotFoundError(f"Matching Stage 2C preflight required: {preflight_path}")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("run_id") != args.run_id:
        raise RuntimeError("Preflight run_id does not match")
    artifact_hashes = preflight.get("artifacts_sha256", {})
    if artifact_hashes != hashes:
        raise RuntimeError("Preflight implementation hashes do not match")
    captured_at = datetime.fromisoformat(str(preflight["captured_at_utc"]))
    age = datetime.now(timezone.utc) - captured_at
    if age < timedelta(minutes=-5) or age > timedelta(minutes=30):
        raise RuntimeError(f"Preflight must be 0–30 minutes old; observed age={age}")

    run_dir = EVIDENCE_ROOT / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Stage 2C evidence already exists: {run_dir}")
    snapshot_path = run_dir / "proc_snapshot.json"
    snapshot_control: dict[str, object] = {"invoked": False}

    sys.path.insert(0, str(PHASE3_DIR))
    baseline = importlib.import_module("run_isolated_gpu_stability_v2_9")
    worker_module = importlib.import_module("stage2b_worker")
    enter_sequence = mp.RawValue("Q", 0)
    return_sequence = mp.RawValue("Q", 0)
    baseline.inference_worker = functools.partial(
        worker_module.inference_worker, enter_sequence, return_sequence
    )
    original_stop = baseline.stop_worker
    baseline.stop_worker = functools.partial(
        bounded_snapshot_then_stop,
        original_stop=original_stop,
        output_path=snapshot_path,
        control=snapshot_control,
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
    proc_snapshot = (
        json.loads(snapshot_path.read_text(encoding="utf-8"))
        if snapshot_path.exists()
        else None
    )
    quality = proc_quality(baseline_result, snapshot_control, proc_snapshot)
    result = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE2C-PROC-THREAD-SNAPSHOT-V1",
        "run_id": args.run_id,
        "infer_classification": infer_classification,
        "proc_snapshot_quality": quality,
        "phase3_qualification_round": False,
        "implementation_sha256": hashes,
        "frozen_arguments": FROZEN_ARGUMENTS,
        "snapshot_budget_seconds": SNAPSHOT_TIMEOUT_SECONDS,
        "snapshot_control": snapshot_control,
        "shared_boundary_snapshot": boundary_snapshot,
        "derived_boundary": derived_boundary,
        "preflight_evidence": str(preflight_path.relative_to(HERE)),
        "preflight_sha256": sha256(preflight_path),
        "baseline_result": baseline_result_path.name,
        "proc_snapshot": snapshot_path.name if snapshot_path.exists() else None,
        "interpretation_limits": [
            "A /proc snapshot describes one moment and does not prove causality.",
            "UNAVAILABLE fields are missing evidence, not absent state.",
            "No Stage 2C result is GPU admission evidence.",
        ],
    }
    result_path = run_dir / "stage2c_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved Stage 2C result: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
