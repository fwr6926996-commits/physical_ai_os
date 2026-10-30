"""Development/freeze/formal entry point for the bounded T0-H suite."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from runtime_core.phase5a_t0.run import environment_identity
from .native import EVENT_LIMIT, TOTAL_LIMIT, guard, identity, source_id

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_host_design_20261027"
RECORD = ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_host_implementation_20261027"
PROTOCOL = ROOT / "docs/protocols/PHASE5A_T0_HOST_CLOCK_V0_1_CANDIDATE.md"
SCENARIOS = DESIGN / "scenarios_v0_1_candidate.json"
AUTH = RECORD / "AUTHORIZATION.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(directory, name, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    size = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
    if size + len(payload.encode()) > TOTAL_LIMIT:
        raise RuntimeError("TOTAL_OUTPUT_LIMIT")
    with (directory / name).open("x") as f:
        f.write(payload)


def code_identity():
    paths = [PROTOCOL, SCENARIOS, AUTH, ROOT / "runtime_core/phase5a_t0/logic.py",
             ROOT / "runtime_core/phase5a_t0/run.py", ROOT / "runtime_core/phase5a_t0/__init__.py",
             ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_design_review_20261027/timepoint_v0_2_candidate.schema.json"]
    paths += sorted((ROOT / "runtime_core/phase5a_t0_host").glob("*.py"))
    paths += sorted((ROOT / "tests/phase5a_t0_host").glob("*.py"))
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def clock_identity():
    current = identity()
    return {k: current[k] for k in ("boot_id_sha256", "namespace_dev", "namespace_ino",
                                   "time_namespace", "children_time_namespace", "timens_offsets",
                                   "clock_id_symbol", "clock_id_value", "sampling_api")}


def claim_authorization(record_directory, authorization_id, run_id, freeze_path):
    claim = record_directory / (authorization_id + ".attempt.json")
    with claim.open("x") as f:
        json.dump({"attempt": 1, "run_id": run_id, "freeze_sha256": sha(freeze_path),
                   "claimed_at": datetime.now(timezone.utc).isoformat()}, f)


def prepare(path, run_id, development):
    dev = Path(development).resolve()
    result, manifest = [json.loads((dev / name).read_text()) for name in ("result.json", "run_manifest.json")]
    checks = json.loads((RECORD / "development_checks.json").read_text())
    for name, digest in json.loads((dev / "hashes.json").read_text()).items():
        if sha(dev / name) != digest:
            raise ValueError("development evidence drift")
    if (result["status"] != "T0_H_NATIVE_CLOCK_AND_LOCAL_PIPE_MOCK_PASS" or
            checks["status"] != "PASS" or checks["source_sha256"] != code_identity() or
            manifest["source_sha256"] != code_identity()):
        raise ValueError("development pass missing or stale")
    payload = {"protocol_id": "P5A-T0-H-0.1", "authorization_id": json.loads(AUTH.read_text())["authorization_id"],
               "frozen_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id,
               "source_sha256": code_identity(), "environment": environment_identity(),
               "clock_identity": clock_identity(), "source": source_id(identity()),
               "command": [sys.executable, "-B", "-m", "runtime_core.phase5a_t0_host.run", "--mode", "formal",
                           "--run-id", run_id, "--freeze", str(path)],
               "output_directory": str(ROOT / "artifacts/phase5a/t0_host" / run_id),
               "worker_command_template": "<interpreter> -B -m runtime_core.phase5a_t0_host.run --worker <producer|executor> --output <fresh instance directory> --case-id <case> --instance-id <case-generation-role> --provider <fixed case provider> --fault <fixed case fault>",
               "context_rule": "supervisor allocates run/case/generation/UUID session before READY; source from kernel binding; incoming action cannot override",
               "limits": json.loads(SCENARIOS.read_text())["limits"],
               "development_evidence": {str(p): sha(p) for p in
                                        (dev / "result.json", dev / "hashes.json", RECORD / "development_checks.json")}}
    with path.open("x") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def launch(args):
    from .suite import run_suite
    from .verify import read, review
    formal = args.mode == "formal"
    frozen = None
    if formal:
        path = Path(args.freeze).resolve()
        frozen = json.loads(path.read_text())
        command = [sys.executable, "-B", "-m", "runtime_core.phase5a_t0_host.run", "--mode", "formal",
                   "--run-id", args.run_id, "--freeze", str(path)]
        if (frozen["command"] != command or frozen["run_id"] != args.run_id or
                frozen["source_sha256"] != code_identity() or frozen["environment"] != environment_identity() or
                frozen["clock_identity"] != clock_identity()):
            raise ValueError("formal freeze identity/command mismatch")
        for name, digest in frozen["development_evidence"].items():
            if sha(name) != digest:
                raise ValueError("development evidence changed after freeze")
        directory = ROOT / "artifacts/phase5a/t0_host" / args.run_id
        if frozen["output_directory"] != str(directory):
            raise ValueError("output path mismatch")
        # Authorization-level claim survives changing run_id or copying freeze.
        claim_authorization(RECORD, frozen["authorization_id"], args.run_id, path)
    else:
        directory = Path(args.output).resolve()
        if directory.parent != Path("/tmp") or not directory.name.startswith("phase5a-t0-host-"):
            raise ValueError("development path must be a fresh /tmp/phase5a-t0-host-* directory")
    directory.parent.mkdir(parents=True, exist_ok=True)
    directory.mkdir(exist_ok=False)
    manifest = {"protocol_id": "P5A-T0-H-0.1", "run_id": args.run_id, "mode": args.mode,
                "source_sha256": code_identity(), "environment": environment_identity(),
                "clock_identity": clock_identity(), "supervisor_startup_binding": identity(),
                "authorization_id": json.loads(AUTH.read_text())["authorization_id"],
                "frozen_snapshot": frozen, "started_at": datetime.now(timezone.utc).isoformat()}
    write(directory, "run_manifest.json", manifest)
    started = guard()
    try:
        scenarios = json.loads(SCENARIOS.read_text())
        results, inventory = run_suite(directory, args.run_id, scenarios)
        # Re-read all closed worker/parent evidence; execution responses and
        # in-memory counters do not determine the final result.
        independent = review(directory, scenarios, inventory)
        if independent != results:
            raise ValueError("independent disk review mismatch")
        for role in ("producer", "executor"):
            with (directory / f"{role}_events.jsonl").open("xb") as f:
                for instance in inventory:
                    if instance["role"] == role:
                        f.write((directory / instance["relative_directory"] / "events.jsonl").read_bytes())
        with (directory / "mock_commands.jsonl").open("xb") as f:
            for instance in inventory:
                if instance["role"] == "executor":
                    f.write((directory / instance["relative_directory"] / "mock_commands.jsonl").read_bytes())
        event_count = sum(len(read(directory / i["relative_directory"] / "events.jsonl")) for i in inventory)
        event_count += len(read(directory / "supervisor_events.jsonl")) + len(read(directory / "binding_observations.jsonl"))
        event_count += len(read(directory / "verifier_fixtures.jsonl"))
        if event_count > EVENT_LIMIT:
            raise ValueError("EVENT_LIMIT")
        if manifest["source_sha256"] != code_identity() or manifest["environment"] != environment_identity() or manifest["clock_identity"] != clock_identity():
            raise ValueError("SOURCE_OR_ENVIRONMENT_DRIFT")
        passed = len(results) == 12 and all(r["matches_expected"] for r in results)
        write(directory, "evidence_summary.json", {"cases": results, "event_count": event_count,
                                                 "actual_commands": len(read(directory / "mock_commands.jsonl")),
                                                 "raw_worker_streams": len(inventory),
                                                 "maximum_simultaneous_workers": 2,
                                                 "constructed_fixture_cases": ["H-10", "H-11", "H-12"]})
        write(directory, "result.json", {"status": "T0_H_NATIVE_CLOCK_AND_LOCAL_PIPE_MOCK_PASS" if passed else "FAIL",
                                        "case_count": len(results), "matched_count": sum(r["matches_expected"] for r in results),
                                        "human_result_acceptance": "PENDING", "full_gate_t0": "NOT_ESTABLISHED"})
        write(directory, "guard_result.json", {"guard_clock": "CLOCK_BOOTTIME", "triggered": False,
                                              "suite_elapsed_ns": str(guard() - started),
                                              "scope": "resource guard, not a real-time metric"})
        with (directory / "REVIEW.md").open("x") as f:
            f.write(f"# T0-H {args.mode}\n\n12/12 matched; native source binding, local pipes and Mock only.\n\n"
                    "Actual worker logs and POST_COLLECTION_VERIFIER_FIXTURE copies remain separate. "
                    "Human result acceptance PENDING; full Gate T0 NOT_ESTABLISHED.\n")
        paths = sorted(p for p in directory.rglob("*") if p.is_file())
        write(directory, "hashes.json", {str(p.relative_to(directory)): sha(p) for p in paths})
        print(json.dumps({"status": "PASS" if passed else "FAIL", "cases": len(results), "output": str(directory)}))
        return 0 if passed else 1
    except BaseException as error:
        write(directory, "failure.json", {"status": "FAIL_STOPPED", "error": str(error), "automatic_rerun": False,
                                          "elapsed_boottime_ns": str(guard() - started)})
        print(json.dumps({"status": "FAIL_STOPPED", "error": str(error), "output": str(directory)}))
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("development", "formal"), default="development")
    parser.add_argument("--output")
    parser.add_argument("--run-id", default="development")
    parser.add_argument("--freeze")
    parser.add_argument("--prepare-freeze")
    parser.add_argument("--development")
    parser.add_argument("--worker", choices=("producer", "executor"))
    parser.add_argument("--case-id")
    parser.add_argument("--instance-id")
    parser.add_argument("--provider", choices=("CLOCK_MONOTONIC", "CLOCK_REALTIME"), default="CLOCK_MONOTONIC")
    parser.add_argument("--fault", choices=("none", "namespace", "unavailable"), default="none")
    args = parser.parse_args()
    if args.worker:
        from .worker import run
        return run(Path(args.output).resolve(), args.case_id, args.instance_id, args.worker, args.provider, args.fault)
    if args.prepare_freeze:
        prepare(Path(args.prepare_freeze).resolve(), args.run_id, args.development)
        return 0
    return launch(args)


if __name__ == "__main__":
    sys.exit(main())
