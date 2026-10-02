"""Run the frozen historical worker path while redirecting new evidence to EXP-2026-003."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
EVIDENCE_ROOT = HERE / "evidence" / "stage2a"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2a_preflight"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
RUN_ID_PATTERN = re.compile(r"^stage2a_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")
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
        description="One human-started Stage 2A historical-path reproduction attempt."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(result: dict[str, object]) -> str:
    status = result.get("status")
    execution = result.get("execution")
    hard_gates = execution.get("hard_gates", {}) if isinstance(execution, dict) else {}
    if status == "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED":
        return "HANG_REPRODUCED_WATCHDOG_RECOVERED"
    if status == "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING":
        return "NO_HANG_REPRODUCED_5M_COMPLETE"
    if (
        hard_gates.get("correctness_failures", 0) != 0
        or hard_gates.get("nonfinite_outputs", 0) != 0
    ):
        return "CORRECTNESS_OR_NONFINITE_FAILURE"
    if result.get("worker_ready") is None:
        return "STARTUP_OR_ENVIRONMENT_FAILURE"
    return "UNEXPECTED_OR_INCOMPLETE"


def verify_sequence(round_number: int) -> None:
    same_round = list(EVIDENCE_ROOT.glob(f"stage2a_r{round_number}_*"))
    if same_round:
        raise RuntimeError(
            f"Stage 2A round {round_number} already has evidence: {same_round}"
        )
    for prior_round in range(1, round_number):
        records = list(
            EVIDENCE_ROOT.glob(
                f"stage2a_r{prior_round}_*/stage2a_classification.json"
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


def main() -> None:
    args = arguments()
    match = RUN_ID_PATTERN.fullmatch(args.run_id)
    if not match:
        raise ValueError(
            "run-id must match stage2a_r1_..., stage2a_r2_..., or stage2a_r3_..."
        )
    round_number = int(match.group("round"))
    verify_sequence(round_number)
    baseline_hash = sha256(BASELINE_SCRIPT)
    if baseline_hash != EXPECTED_BASELINE_SHA256:
        raise RuntimeError(
            f"Historical baseline hash changed: expected={EXPECTED_BASELINE_SHA256} actual={baseline_hash}"
        )
    preflight_path = PREFLIGHT_ROOT / f"{args.run_id}.json"
    if not preflight_path.exists():
        raise FileNotFoundError(
            f"Matching preflight evidence is required before GPU execution: {preflight_path}"
        )
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if preflight.get("run_id") != args.run_id:
        raise RuntimeError("Preflight run_id does not match the requested run")
    if not preflight.get("baseline_hash_matches_frozen_manifest"):
        raise RuntimeError("Preflight did not verify the frozen historical script hash")
    captured_at = datetime.fromisoformat(str(preflight["captured_at_utc"]))
    age = datetime.now(timezone.utc) - captured_at
    if age < timedelta(minutes=-5) or age > timedelta(minutes=30):
        raise RuntimeError(
            f"Preflight must be between 0 and 30 minutes old; observed age={age}"
        )

    run_dir = EVIDENCE_ROOT / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Stage 2A evidence already exists: {run_dir}")

    sys.path.insert(0, str(PHASE3_DIR))
    baseline = importlib.import_module("run_isolated_gpu_stability_v2_9")
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

    result_path = run_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    wrapper_record = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE2A-CURRENT-REPRODUCTION-BASELINE-V1",
        "run_id": args.run_id,
        "classification": classify(result),
        "phase3_qualification_round": False,
        "baseline_script": str(BASELINE_SCRIPT.relative_to(REPO_ROOT)),
        "baseline_script_sha256": baseline_hash,
        "worker_function": "run_isolated_gpu_stability_v2_9.inference_worker",
        "frozen_arguments": FROZEN_ARGUMENTS,
        "preflight_evidence": str(preflight_path.relative_to(HERE)),
        "preflight_sha256": sha256(preflight_path),
        "baseline_result": result_path.name,
        "interpretation_limits": [
            "This is a five-minute exploratory reproduction window, not a Phase 3 qualification run.",
            "A completed window is NO_HANG_REPRODUCED, not PASS and not GPU readmission evidence.",
            "A watchdog timeout reproduces the historical symptom class but does not identify an internal root cause.",
        ],
    }
    wrapper_path = run_dir / "stage2a_classification.json"
    wrapper_path.write_text(json.dumps(wrapper_record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(wrapper_record, indent=2))
    print(f"Saved Stage 2A classification: {wrapper_path}")


if __name__ == "__main__":
    main()
