#!/usr/bin/env python3
"""Mock-only integration checks for the Phase 4 supervisor."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUPERVISOR = HERE / "phase4_cpu_supervisor.py"
MOCK_WORKER = HERE / "phase4_mock_worker.py"


class Phase4HarnessTests(unittest.TestCase):
    def run_case(
        self, scenario: str, expected_status: str, expected_returncode: int, thermal_c: float | None = None
    ) -> dict:
        with tempfile.TemporaryDirectory(prefix="phase4_harness_test_") as temporary:
            root = Path(temporary)
            command = [
                sys.executable,
                str(SUPERVISOR),
                "--run-id",
                f"mock_{scenario}",
                "--stage",
                "correctness",
                "--package-dir",
                str(root / "unused_package"),
                "--evidence-root",
                str(root / "evidence"),
                "--worker-path",
                str(MOCK_WORKER),
                "--test-mode",
                "--mock-scenario",
                scenario,
                "--test-watchdog-seconds",
                "0.25",
                "--test-startup-seconds",
                "0.5",
                "--test-telemetry-seconds",
                "0.02",
            ]
            if thermal_c is not None:
                command.extend(["--test-thermal-fixture-c", str(thermal_c)])
            completed = subprocess.run(command, text=True, capture_output=True, timeout=5)
            self.assertEqual(completed.returncode, expected_returncode, completed.stderr)
            result_path = root / "evidence" / f"mock_{scenario}" / "supervisor_result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], expected_status)
            self.assertEqual(result["classification"], "MOCK_CONTROL_FLOW_ONLY")
            return result

    def test_success(self) -> None:
        result = self.run_case("success", "MOCK_STAGE_PASS_REVIEW_PENDING", 0)
        self.assertIsNone(result["recovery"])
        self.assertGreaterEqual(result["telemetry_summary"]["samples"], 2)
        self.assertEqual(result["telemetry_summary"]["sample_kinds"][0], "start")
        self.assertEqual(result["telemetry_summary"]["sample_kinds"][-1], "final")

    def test_worker_failure(self) -> None:
        result = self.run_case(
            "failure", "MOCK_WORKER_FAILED_WITHOUT_SUPERVISOR_TIMEOUT", 1
        )
        self.assertIsNone(result["recovery"])

    def test_watchdog_recovery(self) -> None:
        result = self.run_case("hang", "MOCK_INFER_WATCHDOG_TIMEOUT_RECOVERED", 1)
        self.assertIn(result["recovery"], ("SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"))
        self.assertEqual(result["diagnostic"]["last_event"]["type"], "infer_enter")

    def test_startup_timeout_recovery(self) -> None:
        result = self.run_case("startup_hang", "MOCK_STARTUP_TIMEOUT_RECOVERED", 1)
        self.assertIn(result["recovery"], ("SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"))
        self.assertEqual(result["diagnostic"]["last_event"]["type"], "worker_started")

    def test_thermal_recovery(self) -> None:
        result = self.run_case("hang", "MOCK_THERMAL_STOP_RECOVERED", 1, thermal_c=101.0)
        self.assertIn(result["recovery"], ("SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"))

    def test_production_rejects_mock_worker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase4_harness_test_") as temporary:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SUPERVISOR),
                    "--run-id",
                    "reject_mock",
                    "--stage",
                    "correctness",
                    "--package-dir",
                    str(Path(temporary) / "unused"),
                    "--evidence-root",
                    str(Path(temporary) / "evidence"),
                    "--worker-path",
                    str(MOCK_WORKER),
                ],
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Production mode accepts only", completed.stderr)

    def test_production_requires_authorization(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase4_harness_test_") as temporary:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SUPERVISOR),
                    "--run-id",
                    "no_authorization",
                    "--stage",
                    "correctness",
                    "--package-dir",
                    str(Path(temporary) / "unused"),
                    "--evidence-root",
                    str(Path(temporary) / "evidence"),
                ],
                text=True,
                capture_output=True,
                timeout=5,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("requires an explicit authorization file", completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
