"""Run Stage 2B using the historical supervisor and shared infer boundaries."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import json
import multiprocessing as mp
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
WORKER_PATH = HERE / "stage2b_worker.py"
EVIDENCE_ROOT = HERE / "evidence" / "stage2b"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2b_preflight"
STAGE2A_CLOSURE = HERE / "STAGE2A_CLOSURE.md"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
EXPECTED_WORKER_SHA256 = (
    "7093c14a6b6eeed5fb3aa234a6e05c96b89d1e1039c661872e028490377f5672"
)
RUN_ID_PATTERN = re.compile(r"^stage2b_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")
FROZEN_ARGUMENTS = {
    "duration_minutes": 5.0,
    "warmup": 10,
    "stall_seconds": 15.0,
    "startup_seconds": 60.0,
    "telemetry_seconds": 5.0,
    "window_seconds": 60.0,
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One human-started Stage 2B shared-boundary attempt."
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
    same_round = list(EVIDENCE_ROOT.glob(f"stage2b_r{round_number}_*"))
    if same_round:
        raise RuntimeError(
            f"Stage 2B round {round_number} already has evidence: {same_round}"
        )
    for prior_round in range(1, round_number):
        records = list(
            EVIDENCE_ROOT.glob(
                f"stage2b_r{prior_round}_*/stage2b_boundary_result.json"
            )
        )
        if len(records) != 1:
            raise RuntimeError(
                f"Round {round_number} requires exactly one reviewed round {prior_round} record; found={records}"
            )
        record = json.loads(records[0].read_text(encoding="utf-8"))
        if record.get("classification") != "NO_HANG_REPRODUCED_5M_COMPLETE":
            raise RuntimeError(
                f"Stop rule blocks round {round_number}; round {prior_round} classification={record.get('classification')}"
            )


def stable_snapshot(enter_sequence: Any, return_sequence: Any) -> dict[str, object]:
    first = {
        "enter_sequence": int(enter_sequence.value),
        "return_sequence": int(return_sequence.value),
    }
    time.sleep(0.05)
    second = {
        "enter_sequence": int(enter_sequence.value),
        "return_sequence": int(return_sequence.value),
    }
    return {"first": first, "second": second, "stable": first == second}


def heartbeat_infer_sequence(result: dict[str, object], warmup: int) -> int | None:
    heartbeat = result.get("last_completed_inference")
    if not isinstance(heartbeat, dict) or heartbeat.get("iteration") is None:
        return None
    return int(heartbeat["iteration"]) + 1 + warmup


def classify_boundary(
    result: dict[str, object], snapshot: dict[str, object], warmup: int
) -> tuple[str, dict[str, object]]:
    second = snapshot["second"]
    if not isinstance(second, dict):
        raise TypeError("snapshot second sample must be a dictionary")
    enter = int(second["enter_sequence"])
    returned = int(second["return_sequence"])
    heartbeat = heartbeat_infer_sequence(result, warmup)
    derived = {
        "enter_sequence": enter,
        "return_sequence": returned,
        "heartbeat_infer_sequence": heartbeat,
        "enter_minus_return": enter - returned,
    }
    if not snapshot.get("stable"):
        return "BOUNDARY_EVIDENCE_INCONSISTENT", derived

    status = result.get("status")
    execution = result.get("execution")
    hard_gates = execution.get("hard_gates", {}) if isinstance(execution, dict) else {}
    if status == "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED":
        if enter == returned + 1:
            return "HANG_INFER_ENTERED_NOT_RETURNED", derived
        if heartbeat is not None and enter == returned and returned > heartbeat:
            return "HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT", derived
        if heartbeat is not None and enter == returned == heartbeat:
            return "HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER", derived
        return "BOUNDARY_EVIDENCE_INCONSISTENT", derived

    if status == "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING":
        iterations = int(execution.get("iterations", -1)) if isinstance(execution, dict) else -1
        expected = iterations + 1 + warmup
        derived["expected_completed_sequence"] = expected
        if enter == returned == expected:
            return "NO_HANG_REPRODUCED_5M_COMPLETE", derived
        return "BOUNDARY_EVIDENCE_INCONSISTENT", derived

    if (
        hard_gates.get("correctness_failures", 0) != 0
        or hard_gates.get("nonfinite_outputs", 0) != 0
    ):
        return "CORRECTNESS_OR_NONFINITE_FAILURE", derived
    if result.get("worker_ready") is None:
        return "STARTUP_OR_ENVIRONMENT_FAILURE", derived
    return "UNEXPECTED_OR_INCOMPLETE", derived


def main() -> None:
    args = arguments()
    match = RUN_ID_PATTERN.fullmatch(args.run_id)
    if not match:
        raise ValueError(
            "run-id must match stage2b_r1_..., stage2b_r2_..., or stage2b_r3_..."
        )
    round_number = int(match.group("round"))
    verify_sequence(round_number)
    if not STAGE2A_CLOSURE.exists():
        raise FileNotFoundError("Stage 2A closure is required before Stage 2B")

    baseline_hash = sha256(BASELINE_SCRIPT)
    worker_hash = sha256(WORKER_PATH)
    if baseline_hash != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("Historical baseline hash changed")
    if worker_hash != EXPECTED_WORKER_SHA256:
        raise RuntimeError(
            f"Stage 2B worker hash changed: expected={EXPECTED_WORKER_SHA256} actual={worker_hash}"
        )

    preflight_path = PREFLIGHT_ROOT / f"{args.run_id}.json"
    if not preflight_path.exists():
        raise FileNotFoundError(f"Matching Stage 2B preflight required: {preflight_path}")
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("run_id") != args.run_id:
        raise RuntimeError("Preflight run_id does not match")
    if not preflight.get("baseline_hash_matches_frozen_manifest"):
        raise RuntimeError("Preflight did not verify the historical baseline hash")
    preflight_worker_hash = preflight.get("artifacts_sha256", {}).get("stage2b_worker")
    if preflight_worker_hash != worker_hash:
        raise RuntimeError("Preflight Stage 2B worker hash does not match")
    captured_at = datetime.fromisoformat(str(preflight["captured_at_utc"]))
    age = datetime.now(timezone.utc) - captured_at
    if age < timedelta(minutes=-5) or age > timedelta(minutes=30):
        raise RuntimeError(f"Preflight must be 0–30 minutes old; observed age={age}")

    run_dir = EVIDENCE_ROOT / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Stage 2B evidence already exists: {run_dir}")

    sys.path.insert(0, str(PHASE3_DIR))
    baseline = importlib.import_module("run_isolated_gpu_stability_v2_9")
    worker_module = importlib.import_module("stage2b_worker")
    enter_sequence = mp.RawValue("Q", 0)
    return_sequence = mp.RawValue("Q", 0)
    baseline.inference_worker = functools.partial(
        worker_module.inference_worker,
        enter_sequence,
        return_sequence,
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

    snapshot = stable_snapshot(enter_sequence, return_sequence)
    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    classification, derived = classify_boundary(
        result, snapshot, int(FROZEN_ARGUMENTS["warmup"])
    )
    boundary_result = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE2B-INFER-BOUNDARY-SHARED-STATE-V1",
        "run_id": args.run_id,
        "classification": classification,
        "phase3_qualification_round": False,
        "baseline_script_sha256": baseline_hash,
        "stage2b_worker_sha256": worker_hash,
        "frozen_arguments": FROZEN_ARGUMENTS,
        "shared_boundary_snapshot": snapshot,
        "derived_boundary": derived,
        "preflight_evidence": str(preflight_path.relative_to(HERE)),
        "preflight_sha256": sha256(preflight_path),
        "baseline_result": result_path.name,
        "interpretation_limits": [
            "Shared counter writes are low perturbation, not zero perturbation.",
            "An entered inference without a return localizes the synchronous call boundary only.",
            "No Stage 2B classification is GPU admission evidence.",
        ],
    }
    boundary_path = run_dir / "stage2b_boundary_result.json"
    boundary_path.write_text(
        json.dumps(boundary_result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(boundary_result, indent=2))
    print(f"Saved Stage 2B boundary result: {boundary_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
