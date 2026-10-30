"""Regression checks for failure masking, duplicate tokens and evidence gaps."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from runtime_core.phase5a_t0.evidence import materialize_fixture, verify_stop
from runtime_core.phase5a_t0.logic import MockExecutor, TimeJudge
from runtime_core.phase5a_t0.run import DESIGN, launch
from runtime_core.phase5a_t0.suite import Recorder, execute_case, verify_case


VECTORS = json.loads((DESIGN / "t0_test_vectors_v0_2_candidate.json").read_text())
SCHEMA = json.loads((DESIGN / "timepoint_v0_2_candidate.schema.json").read_text())


class LogicRegression(unittest.TestCase):
    def setUp(self):
        self.points = deepcopy(VECTORS["timepoints"])
        self.context = deepcopy(VECTORS["runtime_context"])
        self.judge = TimeJudge(SCHEMA, self.context, VECTORS["clock_sources"])
        self.action = {k: self.points[v] for k, v in
                       {"observation": "observation_0", "generated_at": "generated_0",
                        "valid_until": "expiry_100", "now": "now_80"}.items()}

    def test_untrusted_action_cannot_select_active_source(self):
        action = {k: self.points[v] for k, v in {
            "observation": "host_B_observation_0", "generated_at": "host_B_generated_0",
            "valid_until": "host_B_expiry_100", "now": "host_B_now_80"}.items()}
        self.assertEqual(self.judge.check(action)["reason"], "CLOCK_SOURCE_MISMATCH")

    def test_context_is_copied(self):
        self.context["session_id"] = "attacker-selected"
        self.assertEqual(self.judge.check(self.action)["decision"], "ALLOW")

    def test_source_failure_precedes_expiry(self):
        self.action["now"] = {**self.points["host_B_80"], "timestamp": "200000000"}
        actual = self.judge.check(self.action)
        self.assertEqual(actual["reason"], "CLOCK_SOURCE_MISMATCH")
        self.assertIsNone(actual["action_age_ns"])

    def test_schema_failure_anywhere_precedes_session(self):
        self.action["observation"] = {**self.action["observation"], "session_id": "old"}
        self.action["now"]["timestamp"] = "80\n"
        self.assertEqual(self.judge.check(self.action)["reason"], "SCHEMA_INVALID")

    def test_expiry_half_open_boundary(self):
        self.action["now"]["timestamp"] = "99999999"
        self.assertEqual(self.judge.check(self.action)["decision"], "ALLOW")
        self.action["now"]["timestamp"] = "100000000"
        self.assertEqual(self.judge.check(self.action)["reason"], "EXPIRED")

    def test_observation_budget_boundary(self):
        ctx = {**self.context, "max_observation_age_ns": "80000000"}
        self.assertEqual(TimeJudge(SCHEMA, ctx, VECTORS["clock_sources"]).check(self.action)["decision"], "ALLOW")
        ctx["max_observation_age_ns"] = "79999999"
        self.assertEqual(TimeJudge(SCHEMA, ctx, VECTORS["clock_sources"]).check(self.action)["reason"], "OBSERVATION_STALE")

    def test_sink_recheck_and_no_duplicate_expiry(self):
        events, commands = [], []
        emit = lambda kind, **data: events.append({"type": kind, **deepcopy(data)})
        executor = MockExecutor(self.judge, emit, lambda *args: commands.append(args))
        executor.offer("action-1", {k: v for k, v in self.action.items() if k != "now"})
        initial, final = executor.tick(self.points["now_80"], self.points["attempt_120"])
        self.assertEqual(initial["decision"], "ALLOW")
        self.assertEqual(final["reason"], "EXPIRED")
        for _ in range(11):
            executor.tick(self.points["now_120"])
        self.assertEqual(commands, [])
        self.assertEqual(len(executor.expired), 1)
        self.assertEqual(sum(e["type"] == "ACTION_REJECTED" for e in events), 1)
        with self.assertRaises(ValueError):
            executor.offer("action-1", {k: v for k, v in self.action.items() if k != "now"})

    def test_allowed_token_only_outputs_once(self):
        commands = []
        executor = MockExecutor(self.judge, lambda *args, **kw: None, lambda *args: commands.append(args))
        executor.offer("action-1", {k: v for k, v in self.action.items() if k != "now"})
        executor.tick(self.points["now_80"])
        executor.tick(self.points["now_80"])
        self.assertEqual(len(commands), 1)

    def test_wall_series_does_not_change_execution(self):
        case = deepcopy(VECTORS["cases"][8])
        outputs = []
        from runtime_core.phase5a_t0.evidence import read_jsonl
        for wall in (["9", "1", "99"], ["1", "2", "3"]):
            case["input"]["fake_wall_series_ns"] = wall
            with tempfile.TemporaryDirectory(prefix="phase5a-t0-test-") as temp:
                p = Path(temp)
                rec = Recorder(p)
                execute_case(case, {k: v for k, v in VECTORS.items() if k != "cases"}, SCHEMA, rec)
                rec.close()
                outputs.append(read_jsonl(p / "mock_commands.jsonl"))
        self.assertEqual(outputs[0], outputs[1])


class EvidenceRegression(unittest.TestCase):
    def setUp(self):
        self.fixture = deepcopy(VECTORS["cases"][10]["input"]["evidence"])

    def verify(self):
        e, c = materialize_fixture(self.fixture, VECTORS["timepoints"])
        return verify_stop(e, c, 120000000, 340000000, 20000000, "session-A/action-1")

    def test_complete_fixture(self):
        self.assertEqual(self.verify()["verdict"], "PASS_MOCK_STOP_WINDOW_ONLY")

    def test_no_end_is_incomplete(self):
        del self.fixture["window_end_event_ns"]
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_recorder_loss_is_incomplete(self):
        self.fixture["recorder_loss_count"] = 1
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_sequence_gap_even_when_loss_zero(self):
        self.fixture["critical_event_sequences"][7] = 99
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_counter_contradiction_is_incomplete(self):
        self.fixture["mock_sink_count_at_end"] = 1
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_duplicate_tick_is_incomplete(self):
        self.fixture["consumer_tick_times_ns"][4] = self.fixture["consumer_tick_times_ns"][3]
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_missing_reason_is_incomplete(self):
        self.fixture["rejection_records"][0]["reason"] = "STOPPED"
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_bad_record_count_is_incomplete(self):
        self.fixture["recorded_event_count"] = 99
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_early_exit_is_incomplete(self):
        self.fixture["window_close_reason"] = "INTERRUPTED"
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_sink_output_must_fail(self):
        self.fixture = deepcopy(VECTORS["cases"][30]["input"]["evidence"])
        self.assertEqual(self.verify()["verdict"], "FAIL_MOCK_STOP_WINDOW_ONLY")

    def test_command_event_without_sink_file_is_incomplete(self):
        evidence = VECTORS["cases"][30]["input"]["evidence"]
        e, _ = materialize_fixture(evidence, VECTORS["timepoints"])
        self.assertEqual(verify_stop(e, [], 120000000, 340000000, 20000000,
                                     "session-A/action-1")["verdict"], "EVIDENCE_INCOMPLETE")

    def test_unknown_event_cannot_hide_command(self):
        self.fixture["critical_event_types"][2] = "HIDDEN_COMMAND"
        self.assertEqual(self.verify()["verdict"], "EVIDENCE_INCOMPLETE")

    def test_source_identity_of_rejection_must_match(self):
        e, c = materialize_fixture(self.fixture, deepcopy(VECTORS["timepoints"]))
        next(x for x in e if x["type"] == "ACTION_REJECTED")["checked_at"]["source"] = "host-B"
        self.assertEqual(verify_stop(e, c, 120000000, 340000000, 20000000,
                                     "session-A/action-1")["verdict"], "EVIDENCE_INCOMPLETE")


class GuardRegression(unittest.TestCase):
    def test_watchdog_kills_worker_and_leaves_failure_evidence(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-watchdog-parent-") as parent:
            # launch deliberately requires a fresh direct /tmp child.
            output = Path("/tmp") / (Path(parent).name + "-output")
            process = Mock(returncode=-9)
            process.poll.return_value = None
            args = SimpleNamespace(mode="development", output=str(output), run_id="watchdog-test")
            with patch("runtime_core.phase5a_t0.run.source_identity", return_value={}), \
                 patch("runtime_core.phase5a_t0.run.environment_identity", return_value={}), \
                 patch("runtime_core.phase5a_t0.run.subprocess.Popen", return_value=process), \
                 patch("runtime_core.phase5a_t0.run.time.monotonic", side_effect=[0, 11]):
                self.assertEqual(launch(args), 1)
            process.kill.assert_called_once()
            self.assertEqual(json.loads((output / "launcher_failure.json").read_text())["reason"], "WALL_WATCHDOG")

    def test_recorder_line_bound(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-test-") as temp:
            recorder = Recorder(Path(temp))
            try:
                with self.assertRaisesRegex(RuntimeError, "EVENT_SIZE_LIMIT"):
                    recorder.emit("test", "TOO_BIG", data="x" * 16384)
            finally:
                recorder.close()

    def test_recorder_count_bound(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-test-") as temp:
            recorder = Recorder(Path(temp))
            try:
                for _ in range(512):
                    recorder.emit("test", "TICK")
                with self.assertRaisesRegex(RuntimeError, "RECORDER_LIMIT"):
                    recorder.emit("test", "TICK")
            finally:
                recorder.close()

    def test_evidence_files_are_exclusive(self):
        with tempfile.TemporaryDirectory(prefix="phase5a-t0-test-") as temp:
            recorder = Recorder(Path(temp))
            recorder.close()
            with self.assertRaises(FileExistsError):
                Recorder(Path(temp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
