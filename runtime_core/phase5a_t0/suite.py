"""Virtual-time harness plus separate, disk-based evidence review."""
from copy import deepcopy
import json

from .evidence import materialize_fixture, read_jsonl, verify_stop
from .logic import MockExecutor, TimeJudge


class Recorder:
    def __init__(self, directory):
        self.directory, self.count, self.total_bytes = directory, 0, 0
        self.sequences, self.sink_counts = {}, {}
        self.files = {name: (directory / name).open("x", encoding="utf-8") for name in
                      ("events.jsonl", "mock_commands.jsonl", "verifier_inputs.jsonl")}

    def write(self, filename, record):
        line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        if len(line.encode()) > 16384:
            raise RuntimeError("EVENT_SIZE_LIMIT")
        self.count += (len(record["events"]) if filename == "verifier_inputs.jsonl"
                       else filename != "mock_commands.jsonl")
        self.total_bytes += len(line.encode())
        if self.count > 512 or self.total_bytes > 1048576:
            raise RuntimeError("RECORDER_LIMIT")
        self.files[filename].write(line)
        self.files[filename].flush()

    def emit(self, case_id, kind, **data):
        seq = self.sequences.get(case_id, 0)
        self.sequences[case_id] = seq + 1
        event = {"case_id": case_id, "sequence": seq, "type": kind,
                 "provenance": "COLLECTED_MOCK_EXECUTION", **data}
        self.write("events.jsonl", event)
        return seq

    def sink(self, case_id, key, timestamp):
        count = self.sink_counts.get(case_id, 0) + 1
        self.sink_counts[case_id] = count
        data = {"token_key": key, "timestamp_ns": timestamp, "command_sequence": count}
        seq = self.emit(case_id, "MOCK_COMMAND", **data)
        self.write("mock_commands.jsonl", {"case_id": case_id, "event_sequence": seq,
                                          **data})

    def close(self):
        for file in self.files.values():
            file.close()


def execute_case(case, vectors, schema, recorder):
    """Only inputs are supplied here; this function never receives expected."""
    cid, operation, data = case["id"], case["operation"], case["input"]
    context = {**vectors["runtime_context"], **case.get("runtime_context_overrides", {})}
    judge = TimeJudge(schema, context, vectors["clock_sources"])
    emit = lambda kind, **args: recorder.emit(cid, kind, **args)
    executor = MockExecutor(judge, emit, lambda key, time: recorder.sink(cid, key, time))
    points = vectors["timepoints"]
    if operation == "validate_timepoint":
        result = ({"decision": "REJECT", "reason": "SCHEMA_INVALID", "age_available": False,
                   "action_age_ns": None, "observation_age_ns": None}
                  if not judge.validator.is_valid(data["timepoint_inline"]) else
                  {"decision": "ALLOW", "age_available": False, "action_age_ns": None,
                   "observation_age_ns": None})
        emit("TIME_CHECK", stage="dequeue", token_key=None,
             points={"now": data["timepoint_inline"]}, result=result)
        return
    action = {k: deepcopy(points[data[k]]) for k in
              ("observation", "generated_at", "valid_until")}
    executor.offer(data["mock_token"], action)
    now = deepcopy(points[data["now"]])
    if operation == "observe_stop_window":
        start, end, period = [int(data[k]) for k in
                              ("window_start_ns", "window_end_ns", "tick_period_ns")]
        emit("WINDOW_START", timestamp_ns=str(start), sink_count=0)
        for tick in range(start, end, period):
            now["timestamp"] = str(tick)
            executor.tick(now)
        emit("WINDOW_END", timestamp_ns=str(end), close_reason="NORMAL_END")
        emit("SINK_FINAL_COUNT", sink_count=recorder.sink_counts.get(cid, 0),
             expired_drop_count=len(executor.expired))
        emit("RECORDER_STATS", loss_count=0,
             recorded_event_count=recorder.sequences[cid] + 1)
        # Keep the original constructed evidence explicitly separate from actual
        # consumer/sink logs. Negative fixtures exercise only the verifier.
        fixture_events, fixture_commands = materialize_fixture(data["evidence"], points)
        recorder.write("verifier_inputs.jsonl", {
            "case_id": cid, "provenance": "SYNTHETIC_VERIFIER_INPUT",
            "events": fixture_events, "commands": fixture_commands})
    else:
        if operation in ("wall_clock_jump", "replay_reset_invalidates_session"):
            emit("VIRTUAL_CLOCK_INPUT", operation=operation,
                 context=context, series={k: v for k, v in data.items()
                                          if k.startswith("fake_") or k == "event"})
        executor.tick(now, points[data["sink_attempt_at"]]
                      if "sink_attempt_at" in data else None)


def verify_case(case, vectors, events, commands, fixture):
    """Reconstruct facts from records, independently of executor counters."""
    operation, data = case["operation"], case["input"]
    if [e["sequence"] for e in events] != list(range(len(events))):
        raise ValueError("collected event sequence is incomplete")
    checks = [e for e in events if e["type"] == "TIME_CHECK"]
    rejects = [e for e in events if e["type"] == "ACTION_REJECTED"]
    sink_events = [e for e in events if e["type"] == "MOCK_COMMAND"]
    if len(sink_events) != len(commands):
        raise ValueError("sink file and event stream disagree")
    for e, c in zip(sink_events, commands):
        if (c["event_sequence"] != e["sequence"] or
                any(c[k] != e[k] for k in ("token_key", "timestamp_ns", "command_sequence"))):
            raise ValueError("sink record identity mismatch")
    if {e["token_key"] for e in rejects} & {c["token_key"] for c in commands}:
        raise ValueError("a rejected token produced a command")
    if len({c["token_key"] for c in commands}) != len(commands):
        raise ValueError("a one-use token produced multiple commands")
    for c in commands:
        permit = [e for e in checks if e["stage"] == "sink" and
                  e["token_key"] == c["token_key"] and e["sequence"] < c["event_sequence"]]
        if len(permit) != 1 or permit[0]["result"]["decision"] != "ALLOW":
            raise ValueError("command without one sink permit")
        p = permit[0]["points"]
        ctx = {**vectors["runtime_context"], **case.get("runtime_context_overrides", {})}
        if any(t["session_id"] != ctx["session_id"] or
               t["source"] != ctx["control_clock_source"] for t in p.values()):
            raise ValueError("command outside active context")
        if not int(p["sink_attempt_at"]["timestamp"]) == int(c["timestamp_ns"]) < int(p["valid_until"]["timestamp"]):
            raise ValueError("command at or beyond expiry")
    expired = {e["token_key"] for e in rejects if e["reason"] == "EXPIRED"}
    if len(expired) != sum(e["reason"] == "EXPIRED" for e in rejects):
        raise ValueError("duplicate expiry rejection")
    for e in rejects:
        if not {"token_key", "checked_at", "valid_until", "reason", "expired_drop_count"} <= e.keys():
            raise ValueError("incomplete rejection record")
        if e["expired_drop_count"] != len(expired):
            raise ValueError("expired counter disagrees with rejection records")
    if operation == "observe_stop_window":
        start, end, period = [int(data[k]) for k in
                              ("window_start_ns", "window_end_ns", "tick_period_ns")]
        token = vectors["timepoints"][data["generated_at"]]["session_id"] + "/" + data["mock_token"]
        live = verify_stop(events, commands, start, end, period, token)
        if live.get("verdict") != "PASS_MOCK_STOP_WINDOW_ONLY":
            raise ValueError("actual mock stop evidence failed")
        return verify_stop(fixture["events"], fixture["commands"], start, end, period, token), live
    if not checks:
        raise ValueError("no decision evidence")
    initial, final = checks[0]["result"], checks[-1]["result"]
    actual = {**final, "mock_commands": len(commands), "expired_drop": len(expired)}
    if operation == "consume_then_sink_recheck":
        actual.update(initial_check=initial["decision"], sink_check=final["decision"],
                      initial_action_age_ns=initial["action_age_ns"],
                      sink_action_age_ns=final["action_age_ns"],
                      sink_observation_age_ns=final["observation_age_ns"])
    if operation == "wall_clock_jump":
        observed = [e for e in events if e["type"] == "VIRTUAL_CLOCK_INPUT"]
        series = observed[0]["series"]
        # This says only that the supplied steady reading drove the check.
        actual["result_independent_of_wall_series"] = (
            checks[0]["points"]["now"]["timestamp"] == series["fake_steady_series_ns"][-1]
            and all(p["clock_domain"] == "HOST_STEADY" for p in checks[-1]["points"].values()))
    if operation == "replay_reset_invalidates_session":
        actual["old_tokens_invalidated"] = (final.get("reason") == "SESSION_MISMATCH" and not commands)
    return actual, None


def review(directory, vectors):
    events, commands = read_jsonl(directory / "events.jsonl"), read_jsonl(directory / "mock_commands.jsonl")
    fixtures = {f["case_id"]: f for f in read_jsonl(directory / "verifier_inputs.jsonl")}
    results = []
    for case in vectors["cases"]:
        cid = case["id"]
        ev, cmd = [e for e in events if e["case_id"] == cid], [c for c in commands if c["case_id"] == cid]
        actual, live = verify_case(case, vectors, ev, cmd, fixtures.get(cid))
        mismatches = {k: {"expected": v, "actual": actual.get(k)} for k, v in case["expected"].items()
                      if k not in actual or actual[k] != v}
        results.append({"case_id": cid, "actual": actual, "expected": case["expected"],
                        "matches_expected": not mismatches, "mismatches": mismatches,
                        "collected_mock_window": live})
    return results


def run(vectors, schema, directory):
    recorder = Recorder(directory)
    execution_setup = {k: v for k, v in vectors.items() if k != "cases"}
    try:
        for case in vectors["cases"]:
            # Deliberately strip expected before entering the execution path.
            execute_case({k: v for k, v in case.items() if k != "expected"}, execution_setup, schema, recorder)
            # Stop at the first unexpected result; expected negative outcomes are
            # successful coverage, not unexpected failures.
            recorder.files["verifier_inputs.jsonl"].flush()
            ev = [e for e in read_jsonl(directory / "events.jsonl") if e["case_id"] == case["id"]]
            cmd = [c for c in read_jsonl(directory / "mock_commands.jsonl") if c["case_id"] == case["id"]]
            fixtures = {f["case_id"]: f for f in read_jsonl(directory / "verifier_inputs.jsonl")}
            actual, _ = verify_case(case, vectors, ev, cmd, fixtures.get(case["id"]))
            if any(k not in actual or actual[k] != v for k, v in case["expected"].items()):
                raise ValueError("unexpected case result: " + case["id"])
    finally:
        recorder.close()
    return review(directory, vectors)
