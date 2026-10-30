"""Read-only verifier. No imports of the sampler, supervisor or TimeJudge."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check(condition, message):
    if not condition:
        raise ValueError("EVIDENCE: " + message)


def source(binding):
    fields = {k: binding[k] for k in ("boot_id_sha256", "namespace_dev", "namespace_ino", "clock_id_symbol")}
    return "linux-monotonic:" + hashlib.sha256(json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def expected_binding_reason(record):
    r, o, p = record["reported"], record["observed"], record["supervisor"]
    if not o.keys() <= r.keys() or any(r[k] is None for k in o):
        return "BINDING_EVIDENCE_UNAVAILABLE"
    if r["sampling_api"] != "time.clock_gettime_ns" or r["clock_id_symbol"] != "CLOCK_MONOTONIC" or r["clock_id_value"] != 1:
        return "BINDING_PROVIDER_MISMATCH"
    if any(r[k] != o[k] or o[k] != p[k] for k in
           ("namespace_dev", "namespace_ino", "time_namespace", "children_time_namespace", "timens_offsets")):
        return "BINDING_NAMESPACE_MISMATCH"
    if (any(r[k] != o[k] for k in ("pid", "ppid", "process_starttime", "boot_id_sha256")) or
            o["ppid"] != p["pid"] or o["boot_id_sha256"] != p["boot_id_sha256"]):
        return "BINDING_PROCESS_OR_BOOT_MISMATCH"
    return None


def derive_check(event, context):
    """Independently derive the native profile's decision and arithmetic."""
    p = event["points"]
    ctx_source, session = context["control_clock_source"], context["session_id"]
    values = list(p.values())
    unavailable = {"age_available": False, "action_age_ns": None, "observation_age_ns": None}
    reason = None
    if any(t["session_id"] != session for t in values):
        reason = "SESSION_MISMATCH"
    elif any(t["source"] != ctx_source for t in values):
        reason = "UNKNOWN_CLOCK_SOURCE"
    elif any(t["clock_domain"] != "HOST_STEADY" for t in values):
        reason = "CLOCK_SOURCE_METADATA_MISMATCH"
    if reason:
        return {"decision": "REJECT", "reason": reason, **unavailable}
    for role, t in p.items():
        expected_role = {"observation": "capture", "generated_at": "generated",
                         "valid_until": "derived_expiry", "now": "dequeue",
                         "sink_attempt_at": "execute_attempt"}[role]
        check(t["measurement_point"] == expected_role and t["unit"] == "ns" and
              t["validity"] == "VALID" and t["synchronization_status"] == "SAME_SOURCE", "timepoint role/metadata")
    ns = {k: int(t["timestamp"]) for k, t in p.items()}
    check(all(0 <= t < 2**63 for t in ns.values()), "int64 range")
    check(ns["observation"] <= ns["generated_at"] <= ns["now"] and
          ns["generated_at"] < ns["valid_until"] and
          ns.get("sink_attempt_at", ns["now"]) >= ns["now"], "time order")
    now = ns.get("sink_attempt_at", ns["now"])
    ages = {"age_available": True, "action_age_ns": str(now - ns["generated_at"]),
            "observation_age_ns": str(now - ns["observation"])}
    if now >= ns["valid_until"]:
        reason = "EXPIRED"
    elif now - ns["observation"] > int(context["max_observation_age_ns"]):
        reason = "OBSERVATION_STALE"
    return {"decision": "REJECT", "reason": reason, **ages} if reason else {"decision": "ALLOW", **ages}


def verify_window(events, commands):
    incomplete = {"verdict": "EVIDENCE_INCOMPLETE", "must_not_infer_zero_output": True}
    try:
        check([e["sequence"] for e in events] == list(range(len(events))), "window stream sequence")
        starts = [e for e in events if e["type"] == "WINDOW_START"]
        ends = [e for e in events if e["type"] == "WINDOW_END"]
        stats = [e for e in events if e["type"] == "RECORDER_STATS"]
        counts = [e for e in events if e["type"] == "SINK_FINAL_COUNT"]
        check(len(starts) == len(ends) == len(stats) == len(counts) == 1, "window terminal records")
        start, end, count, stat = starts[0], ends[0], counts[0], stats[0]
        start_ns, end_ns = int(start["at"]["timestamp"]), int(end["at"]["timestamp"])
        bound_points = [start["at"], end["at"]] + [e["at"] for e in events if e["type"] == "CONSUMER_TICK"]
        for p in bound_points:
            check(all(p[k] == start["at"][k] for k in ("source", "session_id", "clock_domain", "unit"))
                  and p["clock_domain"] == "HOST_STEADY" and p["unit"] == "ns", "window sample source")
        check(end_ns >= start_ns + 200000000 and end["close_reason"] == "NORMAL_END", "window duration/close")
        check(stat["loss_count"] == 0 and stat["recorded_event_count"] == stat["sequence"] + 1, "recorder stats")
        check(end["sequence"] + 1 == count["sequence"] and count["sequence"] + 1 == stat["sequence"], "terminal ordering")
        reject = [e for e in events if e["type"] == "ACTION_REJECTED"]
        check(len(reject) == 1, "rejection record count")
        reject = reject[0]
        check(reject["sequence"] < start["sequence"] and reject["token_key"] == start["token_key"], "rejection linkage")
        check(reject["reason"] == "EXPIRED" and
              int(reject["valid_until"]["timestamp"]) <= int(reject["checked_at"]["timestamp"]) <= start_ns,
              "rejection timestamp/expiry")
        check(reject["expired_drop_count"] == start["expired_drop_count"] == count["expired_drop_count"] == 1, "expired dedup")
        ticks = [e for e in events if e["type"] == "CONSUMER_TICK"]
        check([t["slot"] for t in ticks] == list(range(10)), "tick slots")
        previous = start_ns
        for slot, tick in enumerate(ticks):
            actual, target = int(tick["at"]["timestamp"]), start_ns + slot * 20000000
            check(start["sequence"] < tick["sequence"] < end["sequence"] and tick["empty"] is True, "tick order/empty")
            check(previous <= actual and target <= actual < target + 20000000 and actual < end_ns, "actual tick interval")
            check(tick["target_ns"] == str(target) and int(tick["lateness_ns"]) == actual - target, "tick arithmetic")
            previous = actual
        commits = [e for e in events if e["type"] == "MOCK_COMMAND_COMMITTED"]
        check([e["command"] for e in commits] == commands, "sink records versus events")
        in_window = [c for c in commands if start_ns <= int(c["at"]["timestamp"]) < end_ns]
        check(count["sink_count"] - start["sink_count"] == len(in_window), "sink counter delta")
        if in_window:
            return {"verdict": "FAIL_MOCK_STOP_WINDOW_ONLY", "reason": "UNEXPECTED_MOCK_OUTPUT",
                    "fixture_mock_commands": len(in_window)}
        check(start["sink_count"] == count["sink_count"] == 0 and not commands, "zero output baseline")
        return {"verdict": "PASS_MOCK_STOP_WINDOW_ONLY", "ticks": 10, "expired_drop": 1,
                "mock_commands": 0, "duration_ns": str(end_ns - start_ns)}
    except (KeyError, ValueError, TypeError, IndexError):
        return incomplete


def fixture_copy(case_id, events, commands):
    copied, cmds = deepcopy(events), deepcopy(commands)
    if case_id == "H-10":
        del copied[next(i for i, e in enumerate(copied) if e["type"] == "CONSUMER_TICK")]
    elif case_id == "H-11":
        next(e for e in copied if e["type"] == "SINK_FINAL_COUNT")["sink_count"] += 1
    elif case_id == "H-12":
        index = next(i for i, e in enumerate(copied) if e["type"] == "CONSUMER_TICK" and e["slot"] == 1)
        tick = copied[index]
        cmd = {"case_id": case_id, "instance_id": tick["instance_id"],
               "token_key": "constructed/unexpected-command", "command_sequence": 1,
               "event_sequence": index + 1, "at": deepcopy(tick["at"])}
        cmds.append(cmd)
        copied.insert(index + 1, {**{k: tick[k] for k in ("case_id", "instance_id", "role")},
                                 "type": "MOCK_COMMAND_COMMITTED", "command": cmd, "at": tick["at"]})
        for seq, event in enumerate(copied):
            event["sequence"] = seq
            if event["type"] == "RECORDER_STATS":
                event["recorded_event_count"] = seq + 1
            elif event["type"] == "SINK_FINAL_COUNT":
                event["sink_count"] += 1
    else:
        raise ValueError("unknown fixture")
    for e in copied:
        e["provenance"] = "POST_COLLECTION_VERIFIER_FIXTURE"
    return copied, cmds


def load_fixture(directory, case_id):
    records = [r for r in read(directory / "verifier_fixtures.jsonl") if r["case_id"] == case_id]
    check(records[0]["kind"] == "BEGIN_FIXTURE" and records[-1]["kind"] == "END_FIXTURE", "fixture framing")
    events = [r["data"] for r in records if r["kind"] == "EVENT"]
    commands = [r["data"] for r in records if r["kind"] == "COMMAND"]
    check(records[-1]["event_count"] == len(events) and records[-1]["command_count"] == len(commands), "fixture record count")
    return events, commands


def verify_case(directory, case, instances, bindings, supervisor_events):
    cid = case["id"]
    if cid in ("H-10", "H-11", "H-12"):
        events, commands = load_fixture(directory, cid)
        return verify_window(events, commands), {}
    relevant = [b for b in bindings if b["case_id"] == cid]
    checks = [b for b in relevant if b["stage"] == "begin"]
    check(len(checks) == len(instances) and len(instances) >= 2, "worker binding inventory")
    reasons = [expected_binding_reason(b) for b in checks]
    for b in relevant:
        check(b["reason"] == expected_binding_reason(b), "independent binding decision")
        check(b["source"] == source(b["supervisor"]), "canonical source")
    binding_reasons = [r for r in reasons if r]
    actual = {"binding_verdict": "REJECT" if binding_reasons else "ALLOW"}
    if binding_reasons:
        actual.update(binding_reason=binding_reasons[0], age_available=False,
                      action_age_ns=None, observation_age_ns=None)
    all_commands, all_checks, rejections = [], [], []
    windows = []
    all_streams = []
    for inst in instances:
        events = read(directory / inst["relative_directory"] / "events.jsonl")
        check([e["sequence"] for e in events] == list(range(len(events))), "worker event sequence")
        check(events[0]["type"] == "STARTUP" and events[-1]["type"] == "EXIT_NORMAL", "complete worker lifecycle")
        check(all(e["case_id"] == cid and e["instance_id"] == inst["instance_id"] and e["role"] == inst["role"] for e in events), "stream identity")
        before = next(b for b in checks if b["instance_id"] == inst["instance_id"])
        after = [b for b in relevant if b["instance_id"] == inst["instance_id"] and b["stage"] == "end"]
        check(len(after) == 1, "end binding missing")
        for k in ("pid", "ppid", "process_starttime", "boot_id_sha256", "namespace_dev", "namespace_ino"):
            check(before["observed"][k] == after[0]["observed"][k] == events[0]["actual_binding"][k], "process/source changed")
        all_streams.extend(events)
        command_path = directory / inst["relative_directory"] / "mock_commands.jsonl"
        commands = read(command_path) if inst["role"] == "executor" else []
        all_commands.extend(commands)
        ready = [e for e in events if e["type"] == "READY"]
        if binding_reasons:
            check(not ready and not commands and not any(e["type"] == "TOKEN_CREATED" for e in events), "output before binding")
            continue
        check(len(ready) == 1 and ready[0]["context"] == inst["context"], "trusted ready context")
        for e in events:
            if e["type"] == "TIME_CHECK":
                check(e["result"] == derive_check(e, inst["context"]), "time result/arithmetic")
                # Local consumption/attempt points must themselves bind to the
                # current source, even when incoming action metadata is faulty.
                for k in ("now", "sink_attempt_at"):
                    if k in e["points"]:
                        p = e["points"][k]
                        check(p["source"] == source(before["observed"]) and
                              p["session_id"] == inst["context"]["session_id"], "native sample origin")
                all_checks.append(e)
            elif e["type"] == "ACTION_REJECTED":
                rejections.append(e)
        committed = [e for e in events if e["type"] == "MOCK_COMMAND_COMMITTED"]
        check([e["command"] for e in committed] == commands, "command file/event equality")
        check([c["command_sequence"] for c in commands] == list(range(1, len(commands) + 1)), "sink sequence")
        for event, cmd in zip(committed, commands):
            permits = [e for e in events if e["type"] == "TIME_CHECK" and e["stage"] == "sink" and
                       e["token_key"] == cmd["token_key"] and e["sequence"] < event["sequence"]]
            check(len(permits) == 1 and permits[0]["result"]["decision"] == "ALLOW", "sink permit")
            check(permits[0]["points"]["sink_attempt_at"] == cmd["at"], "sink point identity")
            check(all(event["at"][k] == cmd["at"][k] for k in ("source", "session_id", "clock_domain", "unit")), "sink completion source")
            check(int(cmd["at"]["timestamp"]) <= int(event["at"]["timestamp"]) < int(cmd["valid_until"]["timestamp"]), "sink completion envelope")
        if any(e["type"] == "WINDOW_START" for e in events):
            w = verify_window(events, commands)
            check(w["verdict"] == "PASS_MOCK_STOP_WINDOW_ONLY", "actual stop window")
            windows.append(w)
    reject_keys = {e["token_key"] for e in rejections}
    generated = {e["token"]["generated_at"]["session_id"] + "/" + e["token"]["token_id"]: e["token"]
                 for e in all_streams if e["type"] == "TOKEN_CREATED"}
    received = [e for e in all_streams if e["type"] == "TOKEN_RECEIVED"]
    for e in received:
        original = deepcopy(generated[e["token_key"]])
        if cid == "H-05":
            original["generated_at"]["source"] = "unregistered-native-source-fixture"
        elif cid == "H-09":
            original["generated_at"]["clock_domain"] = "MCU_UPTIME"
        check(original == e["token"], "producer-to-executor token association")
    check(not reject_keys & {c["token_key"] for c in all_commands}, "rejected token output")
    expired = {e["token_key"] for e in rejections if e["reason"] == "EXPIRED"}
    check(len(expired) == sum(e["reason"] == "EXPIRED" for e in rejections), "expired dedup")
    for r in rejections:
        check(r["expired_drop_count"] == len(expired), "expired counter")
        matching = [e for e in all_checks if e["token_key"] == r["token_key"]]
        check(matching and matching[-1]["result"].get("reason") == r["reason"], "rejection reason")
        check(r["checked_at"] == matching[-1]["points"].get("sink_attempt_at", matching[-1]["points"]["now"])
              and r["valid_until"] == matching[-1]["points"]["valid_until"], "rejection timestamps")
    actual["mock_commands"] = len(all_commands)
    if all_checks:
        actual.update(all_checks[-1]["result"], expired_drop=len(expired))
    if cid == "H-01":
        bracket = next(e for e in supervisor_events if e["type"] == "CAUSAL_BRACKET" and e["case_id"] == cid)
        generated = next(e for e in all_streams if e["type"] == "TOKEN_CREATED")["token"]["generated_at"]
        consume = all_checks[0]["points"]["now"]
        check(int(bracket["before_ns"]) <= int(generated["timestamp"]) <= int(consume["timestamp"]) <= int(bracket["after_ns"]), "causal ordering")
        actual.update(causal_bracket_valid=True, sink_write_completed_before_expiry=True)
    if cid == "H-07":
        actual.update(initial_check=all_checks[0]["result"]["decision"], sink_check=all_checks[-1]["result"]["decision"])
    if windows:
        actual["stop_window_verdict"] = windows[0]["verdict"]
    if cid == "H-08":
        old = next(e for e in all_checks if e["result"].get("reason") == "SESSION_MISMATCH")
        check(int(old["points"]["now"]["timestamp"]) < int(old["points"]["valid_until"]["timestamp"]), "unexpired old token precondition")
        check(len({i["context"]["session_id"] for i in instances}) == 2, "session rotation")
        check(len({i["context"]["control_clock_source"] for i in instances}) == 1, "source continuity")
        actual.update(old_token_reason=old["result"]["reason"], old_token_mock_commands=0,
                      new_token_mock_commands=len(all_commands), source_identity_unchanged=True, session_changed=True)
    if cid in ("H-05", "H-09"):
        check(int(all_checks[0]["points"]["now"]["timestamp"]) < int(all_checks[0]["points"]["valid_until"]["timestamp"]), "unexpired metadata negative")
    return actual, {"windows": windows, "commands": len(all_commands), "rejected_tokens": sorted(reject_keys)}


def review(directory, scenarios, inventory):
    bindings, supervisor = read(directory / "binding_observations.jsonl"), read(directory / "supervisor_events.jsonl")
    check([e["sequence"] for e in supervisor] == list(range(len(supervisor))), "supervisor sequence")
    alive, maximum = {}, 0
    for event in supervisor:
        if event["type"] == "CHILD_STARTED":
            key = (event["pid"], event["process_starttime"])
            check(key not in alive, "duplicate child instance")
            alive[key] = event["instance_id"]
            maximum = max(maximum, len(alive))
            check(event["active_workers"] == len(alive) <= 2, "live child bound")
        elif event["type"] == "CHILD_EXITED":
            key = (event["pid"], event["process_starttime"])
            check(alive.pop(key) == event["instance_id"] and event["exit_code"] == 0, "owned child exit")
            check(event["active_workers"] == len(alive), "child count after exit")
    check(not alive and maximum == 2 and supervisor[-1]["type"] == "RUN_END" and
          supervisor[-1]["active_children"] == 0, "all children exited")
    old_exits = [e["sequence"] for e in supervisor if e["type"] == "CHILD_EXITED" and e["instance_id"].startswith("H-08-g0-")]
    new_starts = [e["sequence"] for e in supervisor if e["type"] == "CHILD_STARTED" and e["instance_id"].startswith("H-08-g1-")]
    check(len(old_exits) == len(new_starts) == 2 and max(old_exits) < min(new_starts), "supervised restart ordering")
    results = []
    for case in scenarios["cases"]:
        instances = [i for i in inventory if i["case_id"] == case["id"]]
        actual, detail = verify_case(directory, case, instances, bindings, supervisor)
        mismatches = {k: {"expected": v, "actual": actual.get(k)} for k, v in case["expected"].items()
                      if k not in actual or v != actual[k]}
        results.append({"case_id": case["id"], "actual": actual, "detail": detail,
                        "matches_expected": not mismatches, "mismatches": mismatches})
    return results
