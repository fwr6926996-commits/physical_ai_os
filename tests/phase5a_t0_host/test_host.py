"""Native binding, evidence corruption and bounded-launch regression checks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime_core.phase5a_t0_host.native import (NativeClock, binding_reason, identity, line,
                                                source_id, wait_until)
from runtime_core.phase5a_t0_host.run import claim_authorization
from runtime_core.phase5a_t0_host.suite import Supervisor
from runtime_core.phase5a_t0_host.verify import derive_check, fixture_copy, source, verify_window


def point(value, role="dequeue"):
    return {"timestamp": str(value), "measurement_point": role, "source": "unit-source",
            "session_id": "unit-session", "clock_domain": "HOST_STEADY", "unit": "ns",
            "validity": "VALID", "synchronization_status": "SAME_SOURCE",
            "contract_version": "phase5a.t0.timepoint/0.2-candidate"}


def window():
    events = []

    def add(kind, **data):
        events.append({"type": kind, "sequence": len(events), "case_id": "H-06",
                       "instance_id": "unit", "role": "executor", **data})
    add("STARTUP")
    add("ACTION_REJECTED", token_key="unit-token", checked_at=point(120000000),
        valid_until=point(100000000, "derived_expiry"), reason="EXPIRED", expired_drop_count=1)
    add("WINDOW_START", at=point(121000000, "window_start"), token_key="unit-token", sink_count=0, expired_drop_count=1)
    for slot in range(10):
        target = 121000000 + slot * 20000000
        add("CONSUMER_TICK", at=point(target + 100000, "consumer_tick"), slot=slot,
            target_ns=str(target), lateness_ns="100000", empty=True)
    add("WINDOW_END", at=point(321000001, "window_end"), close_reason="NORMAL_END")
    add("SINK_FINAL_COUNT", sink_count=0, expired_drop_count=1)
    add("RECORDER_STATS", loss_count=0, recorded_event_count=len(events) + 1)
    add("EXIT_NORMAL")
    return events, []


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.parent = identity()
        self.child = {**self.parent, "pid": 12345, "ppid": self.parent["pid"], "process_starttime": "123"}

    def test_valid_independent_binding(self):
        self.assertIsNone(binding_reason(self.child, self.child, self.parent))

    def test_provider_mismatch_precedes_namespace(self):
        reported = {**self.child, "clock_id_symbol": "CLOCK_REALTIME", "clock_id_value": 0, "namespace_ino": 9}
        self.assertEqual(binding_reason(reported, self.child, self.parent), "BINDING_PROVIDER_MISMATCH")

    def test_namespace_mismatch_even_on_same_host(self):
        reported = {**self.child, "namespace_ino": self.child["namespace_ino"] + 1}
        self.assertEqual(binding_reason(reported, self.child, self.parent), "BINDING_NAMESPACE_MISMATCH")

    def test_missing_evidence(self):
        reported = deepcopy(self.child)
        del reported["boot_id_sha256"]
        self.assertEqual(binding_reason(reported, self.child, self.parent), "BINDING_EVIDENCE_UNAVAILABLE")

    def test_pid_reuse_or_boot_mismatch(self):
        for key in ("process_starttime", "boot_id_sha256"):
            with self.subTest(key=key):
                self.assertEqual(binding_reason({**self.child, key: "other"}, self.child, self.parent), "BINDING_PROCESS_OR_BOOT_MISMATCH")

    def test_source_is_independent_of_session_and_pid(self):
        self.assertEqual(source_id(self.parent), source_id(self.child))
        self.assertEqual(source_id(self.parent), source(self.parent))
        self.assertNotEqual(source_id(self.parent), source_id({**self.parent, "namespace_ino": 1}))

    def test_clock_context_is_copied(self):
        ctx = {"session_id": "old", "control_clock_source": source_id(self.parent)}
        clock = NativeClock(ctx, self.parent)
        ctx["session_id"] = "tampered"
        self.assertEqual(clock.sample("dequeue")["session_id"], "old")

    def test_clock_refuses_wrong_source(self):
        with self.assertRaises(ValueError):
            NativeClock({"session_id": "s", "control_clock_source": "forged"}, self.parent)

    def test_wait_uses_predicate_and_boottime_guard(self):
        with patch("runtime_core.phase5a_t0_host.native.mono", return_value=0), \
             patch("runtime_core.phase5a_t0_host.native.guard", side_effect=[0, 2000000001]):
            with self.assertRaises(TimeoutError):
                wait_until(100)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.events, self.commands = window()

    def verdict(self):
        return verify_window(self.events, self.commands)["verdict"]

    def test_complete_actual_slot_timestamps(self):
        self.assertEqual(self.verdict(), "PASS_MOCK_STOP_WINDOW_ONLY")

    def test_missing_event_sequence(self):
        del self.events[5]
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_missing_terminal(self):
        self.events[-4]["type"] = "OTHER"
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_duplicate_slot(self):
        self.events[5]["slot"] = 0
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_late_tick_not_replaced_by_catchup(self):
        self.events[3]["at"]["timestamp"] = str(121000000 + 20000000)
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_foreign_clock_tick(self):
        self.events[3]["at"]["source"] = "another-host"
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_wrong_lateness_arithmetic(self):
        self.events[3]["lateness_ns"] = "0"
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_zero_file_with_nonzero_counter(self):
        next(e for e in self.events if e["type"] == "SINK_FINAL_COUNT")["sink_count"] = 1
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_loss_counter(self):
        next(e for e in self.events if e["type"] == "RECORDER_STATS")["loss_count"] = 1
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_expiry_counter_dedup(self):
        next(e for e in self.events if e["type"] == "SINK_FINAL_COUNT")["expired_drop_count"] = 10
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_rejection_time_and_expiry_required(self):
        del self.events[1]["checked_at"]
        self.assertEqual(self.verdict(), "EVIDENCE_INCOMPLETE")

    def test_fixtures_do_not_modify_raw_input(self):
        original = deepcopy(self.events)
        for cid, result in (("H-10", "EVIDENCE_INCOMPLETE"), ("H-11", "EVIDENCE_INCOMPLETE"),
                            ("H-12", "FAIL_MOCK_STOP_WINDOW_ONLY")):
            events, cmds = fixture_copy(cid, self.events, self.commands)
            self.assertEqual(verify_window(events, cmds)["verdict"], result)
        self.assertEqual(self.events, original)

    def test_rejection_ages_not_published_for_wrong_session(self):
        points = {k: point(t, role) for k, t, role in
                  (("observation", 0, "capture"), ("generated_at", 1, "generated"),
                   ("valid_until", 100, "derived_expiry"), ("now", 80, "dequeue"))}
        result = derive_check({"points": points}, {"session_id": "new", "control_clock_source": "unit-source"})
        self.assertEqual(result["reason"], "SESSION_MISMATCH")
        self.assertIsNone(result["action_age_ns"])


class GuardTests(unittest.TestCase):
    def test_frame_guard(self):
        with self.assertRaisesRegex(RuntimeError, "FRAME_LIMIT"):
            line({"large": "x" * 16384})

    def test_supervisor_boottime_deadline(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-host-unit-") as temp:
            supervisor = Supervisor(Path(temp), "unit")
            with patch("runtime_core.phase5a_t0_host.suite.guard", return_value=supervisor.started + 30000000000):
                with self.assertRaisesRegex(TimeoutError, "BOOTTIME"):
                    supervisor.limits()
            supervisor.finish()

    def test_pipe_frame_guard(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-host-unit-") as temp:
            supervisor = Supervisor(Path(temp), "unit")
            child = {"buffer": b"", "process": Mock()}
            with patch("runtime_core.phase5a_t0_host.suite.select.select", return_value=([1], [], [])), \
                 patch("runtime_core.phase5a_t0_host.suite.os.read", return_value=b"x" * 16385):
                with self.assertRaisesRegex(ValueError, "PIPE_FRAME_LIMIT"):
                    supervisor.receive(child)
            supervisor.finish()

    def test_authorization_claim_cannot_be_reused_with_new_run_id(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-host-unit-") as temp:
            p = Path(temp)
            frozen = p / "freeze.json"
            frozen.write_text("{}")
            claim_authorization(p, "unit-auth", "run-A", frozen)
            with self.assertRaises(FileExistsError):
                claim_authorization(p, "unit-auth", "run-B", frozen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
