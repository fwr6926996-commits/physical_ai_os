"""Bounded parent launcher; frozen formal output directories are single-use."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib import import_module, metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_design_review_20261027"
IMPLEMENTATION = ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_implementation_20261027"
PROTOCOL = ROOT / "docs/protocols/PHASE5A_T0_OFFLINE_MOCK_V0_2_CANDIDATE.md"
VECTOR = DESIGN / "t0_test_vectors_v0_2_candidate.json"
SCHEMA = DESIGN / "timepoint_v0_2_candidate.schema.json"
AUTH = IMPLEMENTATION / "AUTHORIZATION.json"
LIMIT_BYTES = 1048576


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(directory, name, data):
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    size = sum(p.stat().st_size for p in directory.iterdir() if p.is_file())
    if size + len(payload.encode()) > LIMIT_BYTES:
        raise RuntimeError("TOTAL_OUTPUT_LIMIT")
    with (directory / name).open("x", encoding="utf-8") as file:
        file.write(payload)


def source_identity():
    paths = [PROTOCOL, VECTOR, SCHEMA, AUTH]
    paths += sorted((ROOT / "runtime_core/phase5a_t0").glob("*.py"))
    paths += sorted((ROOT / "tests/phase5a_t0").glob("*.py"))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def environment_identity():
    dependencies = {}
    for name in ("jsonschema", "attrs", "referencing", "rpds", "jsonschema_specifications"):
        module = import_module(name)
        package = Path(module.__file__).parent
        files = sorted(p for p in package.rglob("*") if p.is_file() and
                       "__pycache__" not in p.parts)
        hashes = {str(p.relative_to(package)): sha(p) for p in files}
        distribution = {"rpds": "rpds-py", "jsonschema_specifications": "jsonschema-specifications"}.get(name, name)
        dependencies[name] = {"version": metadata.version(distribution),
                              "path": str(package), "file_count": len(files),
                              "tree_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}
    binary = str(Path(sys.executable).resolve())
    return {"interpreter": sys.executable, "resolved_interpreter": binary,
            "interpreter_sha256": sha(binary), "python_version": sys.version,
            "platform": platform.platform(), "hostname": platform.node(),
            "dependencies": dependencies}


def worker(directory):
    from .suite import run
    # This is a synthetic-only process. Fail closed on writes outside its fresh
    # evidence directory, device reads, network access or subprocess creation.
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT_BYTES, LIMIT_BYTES))

    def audit(event, arguments):
        if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.posix_spawn"):
            raise RuntimeError("RESOURCE_BOUNDARY: " + event)
        if event == "open":
            path, mode, flags = arguments
            if isinstance(path, (str, bytes, os.PathLike)):
                target = Path(os.fsdecode(path)).resolve()
                if target == Path("/dev") or Path("/dev") in target.parents:
                    raise RuntimeError("RESOURCE_BOUNDARY: device access")
                writing = (isinstance(mode, str) and any(k in mode for k in "wax+")) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                if writing and directory not in target.parents:
                    raise RuntimeError("RESOURCE_BOUNDARY: output path")
                if not writing and not (
                        directory in target.parents or Path(sys.prefix).resolve() in target.parents
                        or target in (VECTOR, SCHEMA)
                        or ROOT / "runtime_core/phase5a_t0" in target.parents):
                    raise RuntimeError("RESOURCE_BOUNDARY: input path")
    sys.addaudithook(audit)
    vectors, schema = json.loads(VECTOR.read_text()), json.loads(SCHEMA.read_text())
    results = run(vectors, schema, directory)
    passed = len(results) == 34 and all(r["matches_expected"] for r in results)
    save(directory, "evidence_summary.json", {
        "cases": results, "collected_mock_commands": sum(1 for _ in (directory / "mock_commands.jsonl").open()),
        "fixture_note": "Constructed verifier inputs are separate from collected mock execution logs.",
        "actual_stop_windows": sum(r["collected_mock_window"] is not None for r in results)})
    save(directory, "result.json", {"status": "T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS" if passed else "FAIL",
                                   "case_count": len(results), "matched_count": sum(r["matches_expected"] for r in results),
                                   "final_acceptance": "HUMAN_REVIEW_PENDING",
                                   "full_gate_t0": "NOT_ESTABLISHED"})
    return 0 if passed else 1


def prepare_freeze(path, run_id, development):
    dev = Path(development).resolve()
    if json.loads((dev / "result.json").read_text())["status"] != "T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS":
        raise ValueError("development suite has not passed")
    identity = source_identity()
    if json.loads((dev / "run_manifest.json").read_text())["source_sha256"] != identity:
        raise ValueError("source changed since passing development run")
    unit = json.loads((IMPLEMENTATION / "development_checks.json").read_text())
    if unit["status"] != "PASS" or unit["source_sha256"] != identity:
        raise ValueError("regression checks missing or stale")
    output = ROOT / "artifacts/phase5a/t0" / run_id
    freeze = {"protocol_id": "P5A-T0-L-0.2", "run_id": run_id,
              "authorization_id": json.loads(AUTH.read_text())["authorization_id"],
              "frozen_at": datetime.now(timezone.utc).isoformat(),
              "source_sha256": identity, "environment": environment_identity(),
              "trusted_runtime_context": json.loads(VECTOR.read_text())["runtime_context"],
              "clock_sources": json.loads(VECTOR.read_text())["clock_sources"],
              "context_note": "Fixture context run_id is a virtual-data label; outer run_id identifies this execution.",
              "command": [sys.executable, "-B", "-m", "runtime_core.phase5a_t0.run", "--mode", "formal",
                          "--run-id", run_id, "--freeze", str(path)],
              "output_directory": str(output), "case_count": 34, "maximum_formal_attempts": 1,
              "bounds": {"wall_watchdog_seconds": 10, "event_count": 512,
                         "single_event_bytes": 16384, "total_output_bytes": LIMIT_BYTES},
              "development_evidence": {str(p): sha(p) for p in
                                       (dev / "run_manifest.json", dev / "result.json",
                                        IMPLEMENTATION / "development_checks.json")}}
    with path.open("x", encoding="utf-8") as file:
        json.dump(freeze, file, ensure_ascii=False, indent=2)
        file.write("\n")


def launch(args):
    formal = args.mode == "formal"
    if formal:
        freeze_path = Path(args.freeze).resolve()
        freeze = json.loads(freeze_path.read_text())
        if (freeze["run_id"] != args.run_id or freeze["source_sha256"] != source_identity() or
                freeze["environment"] != environment_identity() or freeze["maximum_formal_attempts"] != 1):
            raise ValueError("frozen source/environment/run identity mismatch")
        for path, digest in freeze["development_evidence"].items():
            if sha(path) != digest:
                raise ValueError("development evidence changed after freeze")
        command = [sys.executable, "-B", "-m", "runtime_core.phase5a_t0.run", "--mode", "formal",
                   "--run-id", args.run_id, "--freeze", str(freeze_path)]
        if command != freeze["command"]:
            raise ValueError("formal command differs from frozen command")
        directory = Path(freeze["output_directory"])
        if directory != ROOT / "artifacts/phase5a/t0" / args.run_id:
            raise ValueError("formal output outside authorized path")
        # Claim the freeze itself, not just the output run_id: re-labelling the
        # output cannot grant a second formal attempt.
        with Path(str(freeze_path) + ".attempt.json").open("x") as claim:
            json.dump({"freeze_sha256": sha(freeze_path), "attempt": 1,
                       "claimed_at": datetime.now(timezone.utc).isoformat()}, claim)
    else:
        directory = Path(args.output).resolve()
        if directory.parent != Path("/tmp") or not directory.name.startswith("phase5a-t0-"):
            raise ValueError("development output must be /tmp/phase5a-t0-*")
        freeze = {"source_sha256": source_identity(), "environment": environment_identity()}
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=False)
    manifest = {**freeze, "mode": args.mode, "run_id": args.run_id,
                "started_at": datetime.now(timezone.utc).isoformat(), "formal_attempt": 1 if formal else 0}
    save(directory, "run_manifest.json", manifest)
    started = time.monotonic()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [sys.executable, "-B", "-m", "runtime_core.phase5a_t0.run", "--worker", str(directory)]
    with (directory / "worker_stdout.txt").open("x") as stdout, (directory / "worker_stderr.txt").open("x") as stderr:
        process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        stop = None
        try:
            while process.poll() is None:
                if time.monotonic() - started >= 10:
                    stop = "WALL_WATCHDOG"
                    break
                if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > LIMIT_BYTES:
                    stop = "TOTAL_OUTPUT_LIMIT"
                    break
                time.sleep(0.02)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    if stop or process.returncode:
        save(directory, "launcher_failure.json", {"reason": stop or "WORKER_FAILED",
                                                   "exit_code": process.returncode, "automatic_rerun": False})
        print(json.dumps({"status": "FAIL_STOPPED", "output": str(directory)}))
        return 1
    if manifest["source_sha256"] != source_identity() or manifest["environment"] != environment_identity():
        save(directory, "launcher_failure.json", {"reason": "SOURCE_OR_ENVIRONMENT_DRIFT", "automatic_rerun": False})
        return 1
    result = json.loads((directory / "result.json").read_text())
    review_text = ("# T0-L offline Mock suite\n\n"
                   f"Mode: {args.mode}; status: {result['status']}; cases: {result['matched_count']}/34.\n\n"
                   "Collected mock windows and constructed verifier inputs are identified separately. "
                   "No ROS, model or hardware execution; no full Gate T0 or physical-stop claim. "
                   "Final human review is pending.\n")
    with (directory / "REVIEW.md").open("x") as file:
        file.write(review_text)
    save(directory, "launcher_result.json", {"exit_code": process.returncode, "watchdog_triggered": False,
                                            "elapsed_wall_seconds": time.monotonic() - started,
                                            "interpretation": "watchdog only; not a real-time performance result"})
    save(directory, "hashes.json", {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()})
    print(json.dumps({**result, "output": str(directory)}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("development", "formal"), default="development")
    parser.add_argument("--run-id", default="development")
    parser.add_argument("--output")
    parser.add_argument("--freeze")
    parser.add_argument("--prepare-freeze")
    parser.add_argument("--development")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        return worker(Path(args.worker))
    if args.prepare_freeze:
        prepare_freeze(Path(args.prepare_freeze).resolve(), args.run_id, args.development)
        return 0
    return launch(args)


if __name__ == "__main__":
    sys.exit(main())
