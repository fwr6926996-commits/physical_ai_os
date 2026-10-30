"""Time eligibility and one-use mock execution; context is supplied by the harness."""
from copy import deepcopy

from jsonschema import Draft202012Validator


ROLES = {"observation": "capture", "generated_at": "generated",
         "valid_until": "derived_expiry", "now": "dequeue",
         "sink_attempt_at": "execute_attempt"}


class TimeJudge:
    def __init__(self, schema, context, sources):
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema)
        # Take a private copy: the action cannot change the trusted run context.
        self.context, self.sources = deepcopy(context), deepcopy(sources)

    def check(self, points):
        values = list(points.values())
        unavailable = {"age_available": False, "action_age_ns": None,
                       "observation_age_ns": None}

        def reject(reason, ages=None):
            return {"decision": "REJECT", "reason": reason,
                    **(unavailable if ages is None else ages)}

        # Each stage scans ALL points before proceeding, preserving precedence.
        if (not {"observation", "generated_at", "valid_until", "now"} <= points.keys()
                or any(not self.validator.is_valid(p) for p in values)):
            return reject("SCHEMA_INVALID")
        if any(p["timestamp"] is not None and
               not -(2**63) <= int(p["timestamp"]) < 2**63 for p in values):
            return reject("TIMESTAMP_OUT_OF_RANGE")
        if any(p["validity"] != "VALID" or p["timestamp"] is None or
               (p["clock_domain"] == "HOST_STEADY" and int(p["timestamp"]) < 0)
               for p in values):
            return reject("INVALID_TIMESTAMP")
        if any(p["session_id"] != self.context["session_id"] for p in values):
            return reject("SESSION_MISMATCH")
        if any(p["source"] not in self.sources for p in values):
            return reject("UNKNOWN_CLOCK_SOURCE")
        if any(self.sources[p["source"]]["clock_domain"] != p["clock_domain"]
               for p in values):
            return reject("CLOCK_SOURCE_METADATA_MISMATCH")
        if any(p["synchronization_status"] == "MAPPED_VALID" for p in values):
            return reject("MAPPING_NOT_SUPPORTED")
        if len({p["clock_domain"] for p in values}) != 1:
            return reject("CLOCK_DOMAIN_MISMATCH")
        if values[0]["clock_domain"] not in self.context["permitted_control_domains"]:
            return reject("CLOCK_DOMAIN_NOT_PERMITTED")
        if any(p["source"] != self.context["control_clock_source"] for p in values):
            return reject("CLOCK_SOURCE_MISMATCH")
        if any(p["synchronization_status"] != "SAME_SOURCE" for p in values):
            return reject("SYNCHRONIZATION_UNKNOWN_OR_INVALID")
        if any(role not in ROLES or p["measurement_point"] != ROLES[role]
               for role, p in points.items()):
            return reject("INVALID_MEASUREMENT_POINT")
        t = {k: int(v["timestamp"]) for k, v in points.items()}
        if not (t["observation"] <= t["generated_at"] <= t["now"] and
                t["generated_at"] < t["valid_until"] and
                t.get("sink_attempt_at", t["now"]) >= t["now"]):
            return reject("INVALID_TIME_ORDER")
        checked = t.get("sink_attempt_at", t["now"])
        ages = {"age_available": True,
                "action_age_ns": str(checked - t["generated_at"]),
                "observation_age_ns": str(checked - t["observation"])}
        if checked >= t["valid_until"]:
            return reject("EXPIRED", ages)
        if checked - t["observation"] > int(self.context["max_observation_age_ns"]):
            return reject("OBSERVATION_STALE", ages)
        return {"decision": "ALLOW", **ages}


class MockExecutor:
    """One pending token; discarded/consumed keys cannot be re-enqueued."""

    def __init__(self, judge, emit, sink):
        self.judge, self.emit, self.sink = judge, emit, sink
        self.pending, self.seen, self.expired = None, set(), set()

    def offer(self, token, points):
        key = points["generated_at"]["session_id"] + "/" + token
        if key in self.seen or self.pending is not None:
            raise ValueError("duplicate token or occupied mock buffer")
        self.seen.add(key)
        self.pending = (key, deepcopy(points))

    def tick(self, now, sink_attempt=None, record_tick=True):
        if record_tick:
            self.emit("CONSUMER_TICK", timestamp_ns=now["timestamp"])
        if self.pending is None:
            return None
        key, points = self.pending
        points["now"] = deepcopy(now)
        initial = self.judge.check(points)
        self.emit("TIME_CHECK", stage="dequeue", token_key=key, points=points,
                  result=initial)
        final = initial
        if initial["decision"] == "ALLOW":
            attempt = deepcopy(now) if sink_attempt is None else deepcopy(sink_attempt)
            if sink_attempt is None:
                attempt["measurement_point"] = "execute_attempt"
            points["sink_attempt_at"] = attempt
            final = self.judge.check(points)
            self.emit("TIME_CHECK", stage="sink", token_key=key, points=points,
                      result=final)
        self.pending = None
        checked = points.get("sink_attempt_at", now)
        if final["decision"] == "ALLOW":
            self.sink(key, checked["timestamp"])
        else:
            if final["reason"] == "EXPIRED":
                self.expired.add(key)
            self.emit("ACTION_REJECTED", token_key=key, checked_at=checked,
                      valid_until=points["valid_until"], reason=final["reason"],
                      expired_drop_count=len(self.expired))
        return initial, final
