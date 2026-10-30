"""One native producer or executor, controlled only by its parent pipe."""
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import sys

from runtime_core.phase5a_t0.logic import TimeJudge
from .native import FRAME_LIMIT, TOTAL_LIMIT, Journal, NativeClock, identity, line, wait_until

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "experiments/EXP-2026-004_sig_a0_alignment/t0_design_review_20261027/timepoint_v0_2_candidate.schema.json"


def restrict_resources(directory):
    resource.setrlimit(resource.RLIMIT_FSIZE, (TOTAL_LIMIT, TOTAL_LIMIT))

    def audit(event, args):
        if event.startswith("socket.") or event in ("subprocess.Popen", "os.system", "os.fork", "os.exec", "os.posix_spawn"):
            raise RuntimeError("RESOURCE_BOUNDARY: " + event)
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            target = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:]
            write = (isinstance(mode, str) and any(s in mode for s in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if write and directory not in target.parents:
                raise RuntimeError("RESOURCE_BOUNDARY: write path")
            permitted = (target == SCHEMA or directory in target.parents or
                         Path(sys.prefix).resolve() in target.parents or
                         ROOT / "runtime_core" in target.parents or
                         target == Path("/proc/sys/kernel/random/boot_id") or
                         Path(f"/proc/{os.getpid()}") in target.parents)
            if not write and not permitted:
                raise RuntimeError("RESOURCE_BOUNDARY: read path")
    sys.addaudithook(audit)


class Worker:
    def __init__(self, directory, case_id, instance_id, role, provider, fault):
        self.role, self.directory = role, directory
        self.journal = Journal(directory / "events.jsonl", case_id, instance_id, role)
        self.binding = identity(provider=provider)
        reported = deepcopy(self.binding)
        if fault == "namespace":
            reported["namespace_ino"] += 1
        elif fault == "unavailable":
            del reported["boot_id_sha256"]
        self.journal.emit("STARTUP", actual_binding=self.binding, reported_binding=reported, fault=fault)
        self.reported = reported
        self.clock, self.judge, self.pending = None, None, None
        self.seen, self.expired, self.command_count = set(), set(), 0
        self.commands = (directory / "mock_commands.jsonl").open("xb") if role == "executor" else None

    def ready(self, context):
        if self.clock is not None:
            raise ValueError("context cannot be replaced")
        self.clock = NativeClock(context, self.binding)
        schema = json.loads(SCHEMA.read_text())
        self.judge = TimeJudge(schema, context, {
            context["control_clock_source"]: {"clock_domain": "HOST_STEADY"}})
        self.journal.emit("READY", context=context)
        return {"ready": True}

    def produce(self, token_id, ttl_ns):
        if self.role != "producer" or self.clock is None:
            raise ValueError("producer not ready")
        observation = self.clock.sample("capture")
        generated = self.clock.sample("generated")
        expiry = {**generated, "measurement_point": "derived_expiry",
                  "timestamp": str(int(generated["timestamp"]) + int(ttl_ns))}
        token = {"token_id": token_id, "payload_kind": "SYNTHETIC_OBSERVATION_NO_SENSOR",
                 "observation": observation, "generated_at": generated, "valid_until": expiry}
        self.journal.emit("TOKEN_CREATED", token=token)
        return token

    def consume(self, token, mode, require_unexpired=False):
        if self.role != "executor" or self.clock is None or self.pending is not None:
            raise ValueError("executor not ready or occupied")
        key = token["generated_at"]["session_id"] + "/" + token["token_id"]
        if key in self.seen:
            raise ValueError("DUPLICATE_TOKEN")
        self.pending = key
        self.seen.add(key)
        self.journal.emit("TOKEN_RECEIVED", token_key=key, token=token,
                          at=self.clock.sample("receive"))
        expiry = int(token["valid_until"]["timestamp"])
        if mode == "expire_dequeue":
            wait_until(expiry)
        now = self.clock.sample("dequeue")
        if require_unexpired and int(now["timestamp"]) >= expiry:
            raise ValueError("SETUP_TIMING_NOT_MET")
        points = {k: token[k] for k in ("observation", "generated_at", "valid_until")}
        points["now"] = now
        initial = self.judge.check(points)
        self.journal.emit("TIME_CHECK", token_key=key, stage="dequeue", points=points, result=initial)
        final = initial
        if initial["decision"] == "ALLOW":
            if mode == "expire_sink":
                wait_until(expiry)
            points["sink_attempt_at"] = self.clock.sample("execute_attempt")
            final = self.judge.check(points)
            self.journal.emit("TIME_CHECK", token_key=key, stage="sink", points=points, result=final)
        self.pending = None
        if final["decision"] == "ALLOW":
            self.command_count += 1
            attempt = points["sink_attempt_at"]
            seq = self.journal.emit("SINK_WRITE_BEGIN", token_key=key, at=attempt,
                                    command_sequence=self.command_count)
            cmd = {"case_id": self.journal.case_id, "instance_id": self.journal.instance_id,
                   "token_key": key, "command_sequence": self.command_count,
                   "event_sequence": seq, "at": attempt, "valid_until": token["valid_until"]}
            self.commands.write(line(cmd))
            self.commands.flush()
            complete = self.clock.sample("sink_write_complete")
            self.journal.emit("MOCK_COMMAND_COMMITTED", command=cmd, at=complete)
            if int(complete["timestamp"]) >= expiry:
                raise ValueError("SINK_COMPLETION_AFTER_DEADLINE")
        else:
            if final["reason"] == "EXPIRED":
                self.expired.add(key)
            self.journal.emit("ACTION_REJECTED", token_key=key,
                              checked_at=points.get("sink_attempt_at", now),
                              valid_until=token["valid_until"], reason=final["reason"],
                              expired_drop_count=len(self.expired))
        if mode in ("expire_dequeue", "expire_sink"):
            self.stop_window(key)
        return {"initial": initial, "final": final}

    def stop_window(self, token_key):
        start = self.clock.sample("window_start")
        start_ns = int(start["timestamp"])
        self.journal.emit("WINDOW_START", at=start, token_key=token_key,
                          sink_count=self.command_count, expired_drop_count=len(self.expired))
        for slot in range(10):
            target = start_ns + slot * 20000000
            wait_until(target)
            actual = self.clock.sample("consumer_tick")
            if int(actual["timestamp"]) >= target + 20000000:
                raise ValueError("EVIDENCE_INCOMPLETE_MISSED_SLOT")
            self.journal.emit("CONSUMER_TICK", at=actual, slot=slot, target_ns=str(target),
                              lateness_ns=str(int(actual["timestamp"]) - target),
                              empty=self.pending is None)
        wait_until(start_ns + 200000000)
        self.journal.emit("WINDOW_END", at=self.clock.sample("window_end"), close_reason="NORMAL_END")
        self.journal.emit("SINK_FINAL_COUNT", sink_count=self.command_count,
                          expired_drop_count=len(self.expired))
        self.journal.emit("RECORDER_STATS", loss_count=0, recorded_event_count=self.journal.sequence + 1)

    def close(self):
        if self.commands:
            self.commands.close()
        self.journal.close()


def run(directory, case_id, instance_id, role, provider="CLOCK_MONOTONIC", fault="none"):
    restrict_resources(directory)
    worker = Worker(directory, case_id, instance_id, role, provider, fault)

    def reply(value):
        sys.stdout.buffer.write(line(value))
        sys.stdout.buffer.flush()

    reply({"ok": True, "value": worker.reported})
    try:
        while True:
            raw = sys.stdin.buffer.readline(FRAME_LIMIT + 1)
            if not raw or len(raw) > FRAME_LIMIT or not raw.endswith(b"\n"):
                raise ValueError("CONTROL_EOF_OR_FRAME_LIMIT")
            request = json.loads(raw)
            op = request.pop("op")
            if op == "ready":
                result = worker.ready(**request)
            elif op == "produce":
                result = worker.produce(**request)
            elif op == "consume":
                result = worker.consume(**request)
            elif op == "inspect":
                result = identity(provider=provider)
                worker.journal.emit("IDENTITY_END", binding=result)
            elif op == "quit":
                worker.journal.emit("EXIT_NORMAL")
                reply({"ok": True, "value": {"closed": True}})
                break
            else:
                raise ValueError("UNKNOWN_CONTROL_OPERATION")
            reply({"ok": True, "value": result})
    except Exception as error:
        worker.journal.emit("WORKER_ERROR", error=str(error))
        reply({"ok": False, "error": str(error)})
        return 1
    finally:
        worker.close()
    return 0
