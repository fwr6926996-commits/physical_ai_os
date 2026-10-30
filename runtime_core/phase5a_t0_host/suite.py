"""Single supervisor with bounded nonblocking pipes and owned-child cleanup."""
from copy import deepcopy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import uuid

from .native import (EVENT_LIMIT, FRAME_LIMIT, TOTAL_LIMIT, Journal, binding_reason,
                     guard, identity, line, mono, source_id)
from .verify import fixture_copy, read, verify_case

ROOT = Path(__file__).resolve().parents[2]


class Supervisor:
    def __init__(self, directory, run_id):
        self.directory, self.run_id = directory, run_id
        self.started = guard()
        self.binding = identity()
        self.source = source_id(self.binding)
        self.inventory, self.active, self.bindings = [], [], []
        self.journal = Journal(directory / "supervisor_events.jsonl", "RUN", run_id, "supervisor")
        self.binding_file = (directory / "binding_observations.jsonl").open("xb")
        self.fixtures = (directory / "verifier_fixtures.jsonl").open("xb")

    def limits(self):
        if guard() - self.started >= 30000000000:
            raise TimeoutError("SUPERVISOR_BOOTTIME_GUARD")
        if sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file()) > TOTAL_LIMIT:
            raise RuntimeError("TOTAL_OUTPUT_LIMIT")
        if len(self.active) > 2:
            raise RuntimeError("CHILD_PROCESS_LIMIT")
        if sum(p.read_bytes().count(b"\n") for p in self.directory.rglob("*.jsonl")) > EVENT_LIMIT:
            raise RuntimeError("EVENT_LIMIT")

    def receive(self, child):
        data = child["buffer"]
        while b"\n" not in data:
            self.limits()
            readable, _, _ = select.select([child["process"].stdout], [], [], 0.01)
            if readable:
                chunk = os.read(child["process"].stdout.fileno(), FRAME_LIMIT + 1 - len(data))
                if not chunk:
                    raise EOFError("WORKER_STDOUT_EOF")
                data += chunk
                if len(data) > FRAME_LIMIT:
                    raise ValueError("PIPE_FRAME_LIMIT")
        raw, child["buffer"] = data.split(b"\n", 1)
        response = json.loads(raw)
        if not response["ok"]:
            raise RuntimeError("WORKER: " + response["error"])
        return response["value"]

    def rpc(self, child, op, **data):
        payload = line({"op": op, **data})
        while payload:
            self.limits()
            _, writable, _ = select.select([], [child["process"].stdin], [], 0.01)
            if writable:
                try:
                    n = os.write(child["process"].stdin.fileno(), payload)
                    payload = payload[n:]
                except BlockingIOError:
                    pass
        return self.receive(child)

    def observe(self, child, reported, stage):
        observed = identity(child["process"].pid)
        reason = binding_reason(reported, observed, self.binding)
        record = {"case_id": child["case_id"], "instance_id": child["instance_id"],
                  "role": child["role"], "stage": stage, "reported": reported,
                  "observed": observed, "supervisor": self.binding, "source": self.source,
                  "reason": reason, "worker_command": child["command"]}
        self.bindings.append(record)
        self.binding_file.write(line(record))
        self.binding_file.flush()
        self.journal.emit("BINDING_OBSERVED", case_id=child["case_id"],
                          instance_id=child["instance_id"], stage=stage, reason=reason)
        return reason

    def session(self, cid, generation=0):
        session = f"{self.run_id}/{cid}/g{generation}/{uuid.uuid4()}"
        context = {"run_id": self.run_id, "session_id": session,
                   "control_clock_source": self.source, "permitted_control_domains": ["HOST_STEADY"],
                   "max_observation_age_ns": "5000000000", "mapping_registry": {}}
        self.journal.emit("SESSION_ALLOCATED", case_id=cid, generation=generation, context=context)
        workers, reasons = [], []
        for role in ("producer", "executor"):
            instance = f"{cid}-g{generation}-{role}"
            rel = Path("raw") / instance
            path = self.directory / rel
            path.mkdir(parents=True, exist_ok=False)
            provider = "CLOCK_REALTIME" if cid == "H-02" and role == "executor" else "CLOCK_MONOTONIC"
            fault = ({"H-03": "namespace", "H-04": "unavailable"}.get(cid, "none")
                     if role == "executor" else "none")
            command = [sys.executable, "-B", "-m", "runtime_core.phase5a_t0_host.run", "--worker", role,
                       "--output", str(path), "--case-id", cid, "--instance-id", instance,
                       "--provider", provider, "--fault", fault]
            stderr = (path / "stderr.txt").open("xb")
            process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, bufsize=0)
            child = {"process": process, "stderr": stderr, "buffer": b"", "case_id": cid,
                     "instance_id": instance, "role": role, "command": command}
            self.active.append(child)
            child["process_starttime"] = identity(process.pid)["process_starttime"]
            self.journal.emit("CHILD_STARTED", case_id=cid, instance_id=instance, pid=process.pid,
                              process_starttime=child["process_starttime"], active_workers=len(self.active),
                              at_ns=str(mono()))
            os.set_blocking(process.stdin.fileno(), False)
            os.set_blocking(process.stdout.fileno(), False)
            reported = self.receive(child)
            reasons.append(self.observe(child, reported, "begin"))
            self.inventory.append({"case_id": cid, "instance_id": instance, "role": role,
                                   "relative_directory": str(rel), "context": context,
                                   "pid": process.pid, "process_starttime": child["process_starttime"],
                                   "command": command})
            workers.append(child)
        if not any(reasons):
            for child in workers:
                self.rpc(child, "ready", context=context)
        else:
            self.journal.emit("BINDING_REJECTED", case_id=cid, reasons=[r for r in reasons if r])
        return workers, context

    def close_session(self, workers):
        for child in workers:
            self.observe(child, self.rpc(child, "inspect"), "end")
        for child in workers:
            self.rpc(child, "quit")
            while child["process"].poll() is None:
                self.limits()
                time.sleep(0.002)
            if child["process"].returncode:
                raise RuntimeError("WORKER_EXIT_CODE")
            child["process"].stdin.close()
            child["process"].stdout.close()
            child["stderr"].close()
            self.active.remove(child)
            self.journal.emit("CHILD_EXITED", case_id=child["case_id"],
                              instance_id=child["instance_id"], exit_code=0,
                              pid=child["process"].pid, process_starttime=child["process_starttime"],
                              active_workers=len(self.active), at_ns=str(mono()))

    def abort(self):
        for child in list(self.active):
            p = child["process"]
            if p.poll() is None:
                # A live unreaped Popen child plus starttime pins the owned
                # process instance. Never signal a different/reused PID.
                try:
                    current = identity(p.pid)["process_starttime"]
                    if current == child.get("process_starttime", current):
                        p.kill()
                except (ProcessLookupError, FileNotFoundError):
                    pass
            try:
                p.wait(timeout=1)
            finally:
                child["stderr"].close()
                for stream in (p.stdin, p.stdout):
                    if stream:
                        stream.close()
        self.active.clear()

    def execute(self, case):
        cid = case["id"]
        if cid in ("H-10", "H-11", "H-12"):
            inst = next(i for i in self.inventory if i["case_id"] == "H-06" and i["role"] == "executor")
            base = self.directory / inst["relative_directory"]
            events, commands = fixture_copy(cid, read(base / "events.jsonl"), read(base / "mock_commands.jsonl"))
            meta = {"case_id": cid, "source_case": "H-06", "provenance": "POST_COLLECTION_VERIFIER_FIXTURE"}
            self.fixtures.write(line({**meta, "kind": "BEGIN_FIXTURE"}))
            for event in events:
                self.fixtures.write(line({**meta, "kind": "EVENT", "data": event}))
            for command in commands:
                self.fixtures.write(line({**meta, "kind": "COMMAND", "data": command}))
            self.fixtures.write(line({**meta, "kind": "END_FIXTURE", "event_count": len(events), "command_count": len(commands)}))
            self.fixtures.flush()
            return
        workers, context = self.session(cid)
        if cid in ("H-02", "H-03", "H-04"):
            self.close_session(workers)
            return
        producer, executor = workers
        before = mono()
        ttl = "200000000" if cid in ("H-06", "H-07") else "2000000000"
        token = self.rpc(producer, "produce", token_id=f"{cid}/g0/token-1", ttl_ns=ttl)
        if cid == "H-08":
            self.close_session(workers)
            workers, new_context = self.session(cid, 1)
            self.journal.emit("SESSION_ROTATED", case_id=cid, old=context, new=new_context)
            producer, executor = workers
            self.rpc(executor, "consume", token=token, mode="normal", require_unexpired=True)
            token = self.rpc(producer, "produce", token_id=f"{cid}/g1/token-1", ttl_ns=ttl)
        elif cid == "H-05":
            token = deepcopy(token)
            token["generated_at"]["source"] = "unregistered-native-source-fixture"
            self.journal.emit("PAYLOAD_FAULT", case_id=cid, fault="unregistered_source")
        elif cid == "H-09":
            token = deepcopy(token)
            token["generated_at"]["clock_domain"] = "MCU_UPTIME"
            self.journal.emit("PAYLOAD_FAULT", case_id=cid, fault="domain_metadata_conflict")
        mode = {"H-06": "expire_dequeue", "H-07": "expire_sink"}.get(cid, "normal")
        self.rpc(executor, "consume", token=token, mode=mode,
                 require_unexpired=cid in ("H-05", "H-07", "H-08", "H-09"))
        after = mono()
        if cid == "H-01":
            self.journal.emit("CAUSAL_BRACKET", case_id=cid, before_ns=str(before), after_ns=str(after))
        self.close_session(workers)

    def finish(self):
        self.journal.emit("RUN_END", elapsed_boottime_ns=str(guard() - self.started), active_children=len(self.active))
        self.journal.close()
        self.binding_file.close()
        self.fixtures.close()


def run_suite(directory, run_id, scenarios):
    supervisor = Supervisor(directory, run_id)
    results = []
    try:
        for case in scenarios["cases"]:
            # The execution path receives no expected result.
            supervisor.execute({k: v for k, v in case.items() if k != "expected"})
            actual, details = verify_case(directory, case,
                [i for i in supervisor.inventory if i["case_id"] == case["id"]],
                supervisor.bindings, read(directory / "supervisor_events.jsonl"))
            mismatch = {k: {"expected": v, "actual": actual.get(k)} for k, v in case["expected"].items()
                        if k not in actual or actual[k] != v}
            results.append({"case_id": case["id"], "actual": actual, "detail": details,
                            "matches_expected": not mismatch, "mismatches": mismatch})
            if mismatch:
                raise ValueError("UNEXPECTED_CASE_RESULT: " + case["id"] + " " + json.dumps(mismatch))
    except BaseException:
        supervisor.abort()
        raise
    finally:
        supervisor.finish()
        with (directory / "process_inventory.json").open("x") as f:
            json.dump(supervisor.inventory, f, indent=2)
    return results, supervisor.inventory
