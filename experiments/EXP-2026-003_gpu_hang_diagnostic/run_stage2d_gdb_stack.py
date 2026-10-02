"""Run Stage 2D with one bounded pre-recovery GDB stack snapshot."""

from __future__ import annotations

import argparse
import functools
import hashlib
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


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PHASE3_DIR = REPO_ROOT / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
BASELINE_SCRIPT = PHASE3_DIR / "run_isolated_gpu_stability_v2_9.py"
WORKER_PATH = HERE / "stage2d_worker.py"
RUNNER_PATH = HERE / "run_stage2d_gdb_stack.py"
PREFLIGHT_SCRIPT = HERE / "capture_stage2d_preflight.py"
MANIFEST_PATH = HERE / "STAGE2D_FROZEN_MANIFEST.json"
GDB_PATH = Path("/usr/bin/gdb")
EVIDENCE_ROOT = HERE / "evidence" / "stage2d"
PREFLIGHT_ROOT = HERE / "evidence" / "stage2d_preflight"
STAGE2C_CLOSURE = HERE / "STAGE2C_CLOSURE.md"
EXPECTED_BASELINE_SHA256 = (
    "4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7"
)
RUN_ID_PATTERN = re.compile(r"^stage2d_r(?P<round>[123])_[A-Za-z0-9][A-Za-z0-9._-]*$")
GDB_TIMEOUT_SECONDS = 2.0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One human-started Stage 2D bounded native-stack attempt."
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
    same_round = list(EVIDENCE_ROOT.glob(f"stage2d_r{round_number}_*"))
    if same_round:
        raise RuntimeError(f"Stage 2D round {round_number} already has evidence: {same_round}")
    for prior_round in range(1, round_number):
        records = list(EVIDENCE_ROOT.glob(f"stage2d_r{prior_round}_*/stage2d_result.json"))
        if len(records) != 1:
            raise RuntimeError(
                f"Round {round_number} requires one reviewed round {prior_round}; found={records}"
            )
        record = json.loads(records[0].read_text(encoding="utf-8"))
        if record.get("infer_classification") != "NO_HANG_REPRODUCED_5M_COMPLETE":
            raise RuntimeError(
                f"Stop rule blocks round {round_number}; round {prior_round} infer_classification={record.get('infer_classification')}"
            )


def gdb_command(pid: int, gdb_path: Path = GDB_PATH) -> list[str]:
    return [
        str(gdb_path),
        "--batch",
        "--nx",
        "--quiet",
        "-ex",
        "set pagination off",
        "-ex",
        "set confirm off",
        "-ex",
        "set debuginfod enabled off",
        "-ex",
        f"attach {pid}",
        "-ex",
        "thread apply all bt 40",
        "-ex",
        "detach",
    ]


def decoded_timeout_output(exc: subprocess.TimeoutExpired) -> str:
    raw = exc.stdout or ""
    return raw.decode(errors="replace") if isinstance(raw, bytes) else raw


def process_state(pid: int) -> str:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("State:"):
                return line.split(":", 1)[1].strip()
    except OSError as exc:
        return f"UNAVAILABLE: {type(exc).__name__}: {exc}"
    return "UNKNOWN"


def write_raw_output(path: Path, output: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output, encoding="utf-8")


def bounded_gdb_then_stop(
    process: mp.Process,
    original_stop: Callable[[mp.Process], str],
    output_path: Path,
    control: dict[str, object],
    helper_command: list[str] | None = None,
    timeout_seconds: float = GDB_TIMEOUT_SECONDS,
) -> str:
    started = time.monotonic()
    command = helper_command or gdb_command(process.pid)
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


def main_thread_identified(output: str, pid: int) -> bool:
    pattern = re.compile(
        rf"Thread[^\n]*\(LWP\s+{pid}\)[^\n]*:\s*\n#0\s+",
        re.MULTILINE,
    )
    return pattern.search(output) is not None


def gdb_quality(
    baseline_result: dict[str, object],
    control: dict[str, object],
    output: str,
) -> str:
    if baseline_result.get("status") != "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED":
        return "GDB_NOT_TRIGGERED_NO_HANG"
    if not control.get("invoked"):
        return "GDB_ATTACH_FAILED"
    if control.get("helper_timeout"):
        return "GDB_HELPER_TIMEOUT"
    if control.get("helper_error") or control.get("output_write_error"):
        return "GDB_ATTACH_FAILED"
    pid = int(control.get("target_pid", -1))
    main_seen = main_thread_identified(output, pid)
    detached = f"process {pid}) detached" in output
    if main_seen and control.get("helper_returncode") == 0 and detached:
        return "GDB_STACK_COMPLETE_MAIN_THREAD_IDENTIFIED"
    if main_seen:
        return "GDB_STACK_PARTIAL_MAIN_THREAD_IDENTIFIED"
    if control.get("helper_returncode") not in (None, 0):
        return "GDB_ATTACH_FAILED"
    return "GDB_STACK_UNUSABLE_MAIN_THREAD_NOT_IDENTIFIED"


def main() -> None:
    args = arguments()
    match = RUN_ID_PATTERN.fullmatch(args.run_id)
    if not match:
        raise ValueError("run-id must match stage2d_r1_..., r2_..., or r3_...")
    round_number = int(match.group("round"))
    verify_sequence(round_number)
    if not STAGE2C_CLOSURE.exists():
        raise FileNotFoundError("Stage 2C closure is required")
    if not MANIFEST_PATH.exists():
        raise RuntimeError("Stage 2D frozen manifest is missing")

    hashes = {
        "baseline": sha256(BASELINE_SCRIPT),
        "worker": sha256(WORKER_PATH),
        "runner": sha256(RUNNER_PATH),
        "preflight": sha256(PREFLIGHT_SCRIPT),
        "gdb": sha256(GDB_PATH),
    }
    if hashes["baseline"] != EXPECTED_BASELINE_SHA256:
        raise RuntimeError("Historical baseline hash changed")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != "EXP-2026-003-STAGE2D-BOUNDED-NATIVE-STACK-V1":
        raise RuntimeError("Stage 2D frozen manifest protocol mismatch")
    if manifest.get("artifacts_sha256") != hashes:
        raise RuntimeError(
            f"Stage 2D implementation differs from frozen manifest: expected={manifest.get('artifacts_sha256')} actual={hashes}"
        )

    preflight_path = PREFLIGHT_ROOT / f"{args.run_id}.json"
    if not preflight_path.exists():
        raise FileNotFoundError(f"Matching Stage 2D preflight required: {preflight_path}")
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
        raise FileExistsError(f"Stage 2D evidence already exists: {run_dir}")
    stack_path = run_dir / "gdb_all_threads.txt"
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
        bounded_gdb_then_stop,
        original_stop=original_stop,
        output_path=stack_path,
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
    output = stack_path.read_text(encoding="utf-8", errors="replace") if stack_path.exists() else ""
    quality = gdb_quality(baseline_result, gdb_control, output)
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
    result = {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": "EXP-2026-003-STAGE2D-BOUNDED-NATIVE-STACK-V1",
        "run_id": args.run_id,
        "infer_classification": infer_classification,
        "gdb_stack_quality": quality,
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
        "gdb_stack": stack_path.name if stack_path.exists() else None,
        "gdb_stack_sha256": sha256(stack_path) if stack_path.exists() else None,
        "interpretation_limits": [
            "A native stack is one stopped-time observation, not a causal diagnosis.",
            "Stripped libraries may expose only module boundaries and addresses.",
            "GDB changes scheduling and delays recovery for a bounded interval.",
            "No Stage 2D result is GPU admission evidence.",
        ],
    }
    result_path = run_dir / "stage2d_result.json"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved Stage 2D result: {result_path}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
