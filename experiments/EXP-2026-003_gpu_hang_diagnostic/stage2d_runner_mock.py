"""No-GPU integration checks for the Stage 2D production GDB wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from run_stage2d_gdb_stack import bounded_gdb_then_stop, gdb_quality
from stage2d_gdb_stack_mock import compile_mock, gdb_command as mock_gdb_command, start_target


HANG_RESULT = {"status": "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED"}
NO_HANG_RESULT = {"status": "HARD_GATES_PASS_DIAGNOSTIC_REVIEW_PENDING"}


def stop_subprocess(process: subprocess.Popen[str]) -> str:
    if process.poll() is not None:
        return "ALREADY_EXITED"
    process.terminate()
    try:
        process.wait(timeout=2)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
        return "SIGKILL_AFTER_SIGTERM_TIMEOUT"


def run_case(
    name: str,
    target: subprocess.Popen[str],
    output_path: Path,
    *,
    helper_command: list[str] | None = None,
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    control: dict[str, object] = {"invoked": False}
    recovery = bounded_gdb_then_stop(
        target,  # type: ignore[arg-type]
        stop_subprocess,  # type: ignore[arg-type]
        output_path,
        control,
        helper_command=helper_command,
        timeout_seconds=timeout_seconds,
    )
    output = output_path.read_text(encoding="utf-8", errors="replace")
    return {
        "name": name,
        "quality": gdb_quality(HANG_RESULT, control, output),
        "control": control,
        "output_contains_native_top": "mock_native_layer_three" in output,
        "recovery": recovery,
        "target_exitcode": target.returncode,
    }


def main() -> None:
    gcc_path = shutil.which("gcc")
    gdb_path = shutil.which("gdb")
    if gcc_path is None or gdb_path is None:
        raise FileNotFoundError("gcc and gdb are required")
    with tempfile.TemporaryDirectory(prefix="stage2d_runner_mock_") as temporary:
        root = Path(temporary)
        library = root / "libstage2d_native_mock.so"
        compilation = compile_mock(gcc_path, library)

        success_target, _ = start_target(library, authorized=True)
        success = run_case("success", success_target, root / "success.txt")

        unauthorized_target, _ = start_target(library, authorized=False)
        attach_failure = run_case(
            "attach_failure", unauthorized_target, root / "attach_failure.txt"
        )

        partial_target, _ = start_target(library, authorized=True)
        partial_pid = partial_target.pid
        partial_output = (
            f'Thread 1 (Thread 0x1 (LWP {partial_pid}) "python3"):\n'
            "#0  0x1 in mock_partial_frame ()\n"
        )
        partial = run_case(
            "partial",
            partial_target,
            root / "partial.txt",
            helper_command=["/usr/bin/printf", "%s", partial_output],
        )

        timeout_target, _ = start_target(library, authorized=True)
        timeout = run_case(
            "timeout",
            timeout_target,
            root / "timeout.txt",
            helper_command=mock_gdb_command(gdb_path, timeout_target.pid, pause_inside_gdb=True),
            timeout_seconds=1.0,
        )

        expected = {
            "success": "GDB_STACK_COMPLETE_MAIN_THREAD_IDENTIFIED",
            "attach_failure": "GDB_ATTACH_FAILED",
            "partial": "GDB_STACK_PARTIAL_MAIN_THREAD_IDENTIFIED",
            "timeout": "GDB_HELPER_TIMEOUT",
        }
        cases = {case["name"]: case for case in (success, attach_failure, partial, timeout)}
        classifications_match = all(
            cases[name]["quality"] == quality for name, quality in expected.items()
        )
        recoveries_bounded = all(
            case["recovery"] in {"SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"}
            for case in cases.values()
        )
        no_hang_quality = gdb_quality(NO_HANG_RESULT, {"invoked": False}, "")
        status = (
            "PASS_STAGE2D_PRODUCTION_WRAPPER_INTEGRATION_MOCK"
            if classifications_match
            and recoveries_bounded
            and success["output_contains_native_top"]
            and timeout["control"].get("helper_timeout") is True
            and no_hang_quality == "GDB_NOT_TRIGGERED_NO_HANG"
            else "FAIL_STAGE2D_PRODUCTION_WRAPPER_INTEGRATION_MOCK"
        )
        result = {
            "schema_version": 1,
            "protocol_id": "EXP-2026-003-STAGE2D-PRODUCTION-WRAPPER-MOCK-V1",
            "scope": "Native busy-loop targets only; no OpenVINO or GPU access.",
            "compilation": compilation,
            "cases": cases,
            "no_hang_quality": no_hang_quality,
            "status": status,
            "interpretation_limits": [
                "The mock validates wrapper control flow and classifications, not OpenVINO stack quality.",
                "The production GPU run remains blocked until hashes are frozen and separately approved.",
            ],
        }
        print(json.dumps(result, indent=2))
        if not status.startswith("PASS_"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
