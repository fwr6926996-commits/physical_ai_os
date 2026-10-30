"""Independent evidence reader. Does not import the time judge or expected values."""
import json


def read_jsonl(path):
    with open(path, encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def verify_stop(events, commands, start, end, period, token_key):
    incomplete = {"verdict": "EVIDENCE_INCOMPLETE",
                  "must_not_infer_zero_output": True}
    try:
        if not (0 < period and start < end):
            return incomplete
        if [e["sequence"] for e in events] != list(range(len(events))):
            return incomplete
        by_type = {}
        for e in events:
            by_type.setdefault(e["type"], []).append(e)
        if not set(by_type) <= {"WINDOW_START", "WINDOW_END", "SINK_FINAL_COUNT", "RECORDER_STATS",
                                "CONSUMER_TICK", "TIME_CHECK", "ACTION_REJECTED", "MOCK_COMMAND"}:
            return incomplete
        one = lambda kind: by_type[kind][0] if len(by_type[kind]) == 1 else None
        first, last, counts, stats = [one(k) for k in (
            "WINDOW_START", "WINDOW_END", "SINK_FINAL_COUNT", "RECORDER_STATS")]
        if any(e is None for e in (first, last, counts, stats)):
            return incomplete
        if not (events[0] == first and events[-3:] == [last, counts, stats]):
            return incomplete
        if (int(first["timestamp_ns"]) != start or int(last["timestamp_ns"]) != end
                or last["close_reason"] != "NORMAL_END"
                or stats["loss_count"] != 0 or stats["recorded_event_count"] != len(events)):
            return incomplete
        ticks = [int(e["timestamp_ns"]) for e in by_type.get("CONSUMER_TICK", [])]
        if ticks != list(range(start, end, period)):
            return incomplete
        rejects = by_type.get("ACTION_REJECTED", [])
        if len(rejects) != 1:
            return incomplete
        r = rejects[0]
        if (r["token_key"] != token_key or r["reason"] != "EXPIRED" or
                int(r["checked_at"]["timestamp"]) != start or
                int(r["valid_until"]["timestamp"]) > start or
                r["checked_at"]["session_id"] != r["valid_until"]["session_id"] or
                r["checked_at"]["source"] != r["valid_until"]["source"] or
                r["checked_at"]["clock_domain"] != "HOST_STEADY" or
                r["valid_until"]["clock_domain"] != "HOST_STEADY" or
                r["expired_drop_count"] != 1 or counts["expired_drop_count"] != 1):
            return incomplete
        # Match sink records to command events and the counter delta; never infer
        # silence just from an empty file or from one 'stopped' message.
        cmd_events = by_type.get("MOCK_COMMAND", [])
        if len(cmd_events) != len(commands):
            return incomplete
        for e, cmd in zip(cmd_events, commands):
            if (cmd["event_sequence"] != e["sequence"] or
                    any(cmd[k] != e[k] for k in ("token_key", "timestamp_ns", "command_sequence"))
                    or not start <= int(cmd["timestamp_ns"]) < end):
                return incomplete
        n0, n1 = first["sink_count"], counts["sink_count"]
        if type(n0) is not int or type(n1) is not int or n0 < 0 or n1 - n0 != len(commands):
            return incomplete
        if [c["command_sequence"] for c in commands] != list(range(n0 + 1, n1 + 1)):
            return incomplete
        if commands:
            return {"verdict": "FAIL_MOCK_STOP_WINDOW_ONLY",
                    "reason": "UNEXPECTED_MOCK_OUTPUT", "mock_commands": len(commands)}
        return {"verdict": "PASS_MOCK_STOP_WINDOW_ONLY", "tick_count": len(ticks),
                "mock_commands": 0, "expired_drop": 1, "evidence_complete": True}
    except (KeyError, ValueError, TypeError, IndexError):
        return incomplete


def materialize_fixture(evidence, timepoints):
    """Import SYNTHETIC verifier input; never call this collected execution data."""
    seqs, types = evidence["critical_event_sequences"], evidence["critical_event_types"]
    ticks = iter(evidence["consumer_tick_times_ns"])
    rejections = {r["event_sequence"]: r for r in evidence["rejection_records"]}
    commands = evidence["mock_command_records"]
    by_seq = {r["event_sequence"]: r for r in commands}
    events = []
    for seq, kind in zip(seqs, types):
        e = {"sequence": seq, "type": kind, "provenance": "SYNTHETIC_VERIFIER_INPUT"}
        if kind == "WINDOW_START":
            e.update(timestamp_ns=evidence["window_start_event_ns"],
                     sink_count=evidence["mock_sink_count_at_start"])
        elif kind == "WINDOW_END":
            if "window_end_event_ns" not in evidence:
                continue
            e.update(timestamp_ns=evidence["window_end_event_ns"],
                     close_reason=evidence["window_close_reason"])
        elif kind == "CONSUMER_TICK":
            # A sequence-gap fixture can have a tick summary that exceeds its
            # recorded events. Keep both facts; completeness must fail.
            e["timestamp_ns"] = next(ticks)
        elif kind == "ACTION_REJECTED":
            r = rejections[seq]
            e.update(token_key=r["token_key"], reason=r["reason"],
                     checked_at=timepoints[r["checked_at_ref"]],
                     valid_until=timepoints[r["valid_until_ref"]],
                     expired_drop_count=evidence["expired_drop_count"])
        elif kind == "MOCK_COMMAND":
            e.update({k: v for k, v in by_seq[seq].items() if k != "event_sequence"})
        elif kind == "SINK_FINAL_COUNT":
            if "mock_sink_count_at_end" not in evidence:
                continue
            e.update(sink_count=evidence["mock_sink_count_at_end"],
                     expired_drop_count=evidence["expired_drop_count"])
        elif kind == "RECORDER_STATS":
            e.update(loss_count=evidence["recorder_loss_count"],
                     recorded_event_count=evidence["recorded_event_count"])
        events.append(e)
    return events, commands
