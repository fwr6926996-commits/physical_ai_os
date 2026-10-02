"""No-GPU mock for bounded main-thread PC and module-mapping capture."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from stage2d_gdb_stack_mock import compile_mock, process_state, recover_target, start_target
from stage2e_offset_evidence import derive_module_offset, gdb_command


def main() -> None:
    gcc_path = shutil.which("gcc")
    gdb_path = shutil.which("gdb")
    if gcc_path is None or gdb_path is None:
        raise FileNotFoundError("gcc and gdb are required")

    with tempfile.TemporaryDirectory(prefix="stage2e_offset_mock_") as temporary:
        root = Path(temporary)
        library = root / "libstage2e_native_mock.so"
        compilation = compile_mock(gcc_path, library)
        target, identity = start_target(library, authorized=True)
        command = gdb_command(gdb_path, target.pid)
        started = time.monotonic()
        output = ""
        helper_returncode: int | None = None
        helper_timeout = False
        helper_error: str | None = None
        try:
            try:
                completed = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=3.0,
                    check=False,
                )
                output = completed.stdout
                helper_returncode = completed.returncode
            except subprocess.TimeoutExpired as exc:
                helper_timeout = True
                raw = exc.stdout or ""
                output = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            except Exception as exc:
                helper_error = f"{type(exc).__name__}: {exc}"
                output = helper_error

            elapsed = time.monotonic() - started
            target_alive_after_gdb = target.poll() is None
            target_state_after_gdb = process_state(target.pid)
            expected_markers = {
                "main_lwp_identified": f"LWP {target.pid}" in output,
                "native_top_identified": "mock_native_layer_three" in output,
                "shared_library_list_present": "Shared Object Library" in output,
                "proc_mappings_present": "Mapped address spaces" in output,
                "mock_library_mapped": str(library) in output,
                "main_pc_marker_present": "STAGE2E_MAIN_PC=0x" in output,
                "instruction_present": "=>" in output,
                "detached": f"process {target.pid}) detached" in output,
            }
            offset_evidence = derive_module_offset(output, library)
            evidence_complete = (
                helper_returncode == 0
                and not helper_timeout
                and helper_error is None
                and all(expected_markers.values())
                and offset_evidence["valid"] is True
                and target_alive_after_gdb
            )
            recovery = recover_target(target)
        finally:
            if target.poll() is None:
                recover_target(target)

        result = {
            "schema_version": 1,
            "protocol_id": "EXP-2026-003-STAGE2E-A-OFFSET-CAPTURE-MOCK-V1",
            "scope": "Authorized native busy-loop target only; no OpenVINO or GPU access.",
            "compilation": compilation,
            "target_identity": identity,
            "control": {
                "command": command,
                "helper_returncode": helper_returncode,
                "helper_timeout": helper_timeout,
                "helper_error": helper_error,
                "elapsed_seconds": elapsed,
                "output_bytes": len(output.encode("utf-8", errors="replace")),
                "target_alive_after_gdb": target_alive_after_gdb,
                "target_state_after_gdb": target_state_after_gdb,
            },
            "checks": expected_markers,
            "offset_evidence": offset_evidence,
            "recovery": recovery,
            "status": (
                "PASS_STAGE2E_OFFSET_CAPTURE_MOCK"
                if evidence_complete
                and recovery["recovery"] in {"SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"}
                else "FAIL_STAGE2E_OFFSET_CAPTURE_MOCK"
            ),
            "interpretation_limits": [
                "The mock validates one bounded capture of mappings, main-thread PC, a native stack, and module-offset arithmetic.",
                "It does not validate stripped-production-library symbolization, OpenVINO, or GPU diagnosis.",
                "It does not authorize a real GPU run.",
            ],
        }
        print(json.dumps(result, indent=2))
        if not result["status"].startswith("PASS_"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
