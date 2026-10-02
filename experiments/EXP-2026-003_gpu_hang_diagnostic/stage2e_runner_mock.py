"""No-GPU integration checks for the draft Stage 2E-A production wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from run_stage2e_offset_capture import (
    bounded_offset_capture_then_stop,
    verify_execution_gate,
)
from stage2d_gdb_stack_mock import compile_mock, start_target
from stage2d_runner_mock import stop_subprocess
from stage2e_offset_evidence import offset_quality


HANG_RESULT = {"status": "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED"}
NO_HANG_RESULT = {"status": "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING"}


def main() -> None:
    gcc_path = shutil.which("gcc")
    gdb_path = shutil.which("gdb")
    if gcc_path is None or gdb_path is None:
        raise FileNotFoundError("gcc and gdb are required")

    with tempfile.TemporaryDirectory(prefix="stage2e_runner_mock_") as temporary:
        root = Path(temporary)
        library = root / "libstage2e_native_mock.so"
        compilation = compile_mock(gcc_path, library)
        target, identity = start_target(library, authorized=True)
        output_path = root / "gdb_offset_capture.txt"
        control: dict[str, object] = {"invoked": False}
        recovery = bounded_offset_capture_then_stop(
            target,  # type: ignore[arg-type]
            stop_subprocess,  # type: ignore[arg-type]
            output_path,
            control,
            helper_command=None,
            timeout_seconds=2.0,
        )
        output = output_path.read_text(encoding="utf-8", errors="replace")
        quality, offset_evidence = offset_quality(HANG_RESULT, control, output, library)

        wrong_module_quality, wrong_module_evidence = offset_quality(
            HANG_RESULT, control, output, root / "libwrong.so"
        )
        missing_main_output = output.replace(
            f"STAGE2E_MAIN_LWP={target.pid}", "STAGE2E_MAIN_LWP_REMOVED"
        )
        missing_main_quality, missing_main_evidence = offset_quality(
            HANG_RESULT, control, missing_main_output, library
        )
        write_failure_control = dict(control)
        write_failure_control["output_write_error"] = "mock write failure"
        write_failure_quality, write_failure_evidence = offset_quality(
            HANG_RESULT, write_failure_control, output, library
        )
        no_hang_quality, no_hang_evidence = offset_quality(
            NO_HANG_RESULT, {"invoked": False}, "", library
        )
        try:
            verify_execution_gate("stage2e_a1_mock_gate")
        except RuntimeError as exc:
            hard_gate_blocked = "not approved/frozen" in str(exc)
            hard_gate_error = str(exc)
        else:
            hard_gate_blocked = False
            hard_gate_error = None

        checks = {
            "complete_quality": quality
            == "OFFSET_EVIDENCE_COMPLETE_MAIN_THREAD_AND_MAPPING_IDENTIFIED",
            "offset_valid": offset_evidence.get("valid") is True,
            "main_lwp_matches_target": offset_evidence.get("main_lwp") == target.pid,
            "raw_output_saved": output_path.exists() and len(output) > 0,
            "recovery_bounded": recovery in {"SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"},
            "wrong_module_rejected": wrong_module_quality
            == "OFFSET_EVIDENCE_PARTIAL_MAIN_THREAD_ONLY"
            and wrong_module_evidence.get("valid") is False,
            "missing_main_rejected": missing_main_quality
            == "OFFSET_EVIDENCE_PARTIAL_MAPPING_ONLY"
            and missing_main_evidence.get("valid") is False,
            "write_failure_rejected": write_failure_quality
            == "OFFSET_EVIDENCE_UNUSABLE_RAW_OUTPUT_NOT_SAVED"
            and write_failure_evidence.get("valid") is False,
            "no_hang_not_triggered": no_hang_quality == "GDB_NOT_TRIGGERED_NO_HANG"
            and no_hang_evidence.get("valid") is False,
            "real_execution_hard_blocked": hard_gate_blocked,
        }
        status = (
            "PASS_STAGE2E_PRODUCTION_WRAPPER_INTEGRATION_MOCK"
            if all(checks.values())
            else "FAIL_STAGE2E_PRODUCTION_WRAPPER_INTEGRATION_MOCK"
        )
        result = {
            "schema_version": 1,
            "protocol_id": "EXP-2026-003-STAGE2E-A-PRODUCTION-WRAPPER-MOCK-V1",
            "scope": "Authorized native busy-loop target only; no OpenVINO or GPU access.",
            "compilation": compilation,
            "target_identity": identity,
            "control": control,
            "quality": quality,
            "offset_evidence": offset_evidence,
            "recovery": recovery,
            "negative_controls": {
                "wrong_module": wrong_module_quality,
                "missing_main": missing_main_quality,
                "raw_output_write_failure": write_failure_quality,
                "no_hang": no_hang_quality,
                "draft_execution_gate_error": hard_gate_error,
            },
            "checks": checks,
            "status": status,
            "interpretation_limits": [
                "This validates production-wrapper control and offset classification on a native mock only.",
                "It does not initialize OpenVINO or GPU and does not authorize a real Stage 2E attempt.",
            ],
        }
        print(json.dumps(result, indent=2))
        if not status.startswith("PASS_"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()

