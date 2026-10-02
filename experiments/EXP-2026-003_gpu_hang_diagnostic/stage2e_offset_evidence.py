"""Shared Stage 2E-A GDB command and module-offset evidence classification."""

from __future__ import annotations

import re
from pathlib import Path


MAIN_LWP_PATTERN = re.compile(r"^STAGE2E_MAIN_LWP=(\d+)$", re.MULTILINE)
MAIN_PC_PATTERN = re.compile(r"^STAGE2E_MAIN_PC=(0x[0-9a-fA-F]+)$", re.MULTILINE)


def gdb_command(gdb_path: str | Path, pid: int) -> list[str]:
    select_main = (
        "python target=next((t for t in gdb.selected_inferior().threads() "
        f"if t.ptid[1] == {pid}), None); assert target is not None; "
        f'target.switch(); print("STAGE2E_MAIN_LWP={pid}")'
    )
    return [
        str(gdb_path),
        "--batch",
        "--nx",
        "--quiet",
        "-ex",
        "set pagination off",
        "-ex",
        "set confirm off",
        "-ex",
        "set debuginfod enabled off",
        "-ex",
        f"attach {pid}",
        "-ex",
        "info sharedlibrary",
        "-ex",
        "info proc mappings",
        "-ex",
        "info threads",
        "-ex",
        select_main,
        "-ex",
        "bt 40",
        "-ex",
        'printf "STAGE2E_MAIN_PC=%p\\n", $pc',
        "-ex",
        "x/i $pc",
        "-ex",
        "detach",
    ]


def derive_module_offset(output: str, module_path: Path) -> dict[str, object]:
    """Derive a stable offset only when one exact module mapping contains main PC."""
    lwp_match = MAIN_LWP_PATTERN.search(output)
    pc_match = MAIN_PC_PATTERN.search(output)
    if lwp_match is None:
        return {"valid": False, "error": "MAIN_LWP_NOT_FOUND"}
    if pc_match is None:
        return {
            "valid": False,
            "error": "MAIN_PC_NOT_FOUND",
            "main_lwp": int(lwp_match.group(1)),
        }
    pc = int(pc_match.group(1), 16)

    candidates: list[dict[str, object]] = []
    for line in output.splitlines():
        if str(module_path) not in line:
            continue
        fields = line.split()
        hex_fields = [field for field in fields if re.fullmatch(r"0x[0-9a-fA-F]+", field)]
        permission = next(
            (field for field in fields if re.fullmatch(r"[r-][w-][x-][ps-]", field)),
            None,
        )
        if len(hex_fields) < 4:
            continue
        start, end, _size, file_offset = (int(field, 16) for field in hex_fields[:4])
        candidates.append(
            {
                "start": start,
                "end": end,
                "file_offset": file_offset,
                "permission": permission,
                "contains_pc": start <= pc < end,
                "raw_line": line.strip(),
            }
        )

    containing = [candidate for candidate in candidates if candidate["contains_pc"]]
    if len(containing) != 1:
        return {
            "valid": False,
            "error": "PC_MAPPING_NOT_UNIQUE",
            "main_lwp": int(lwp_match.group(1)),
            "pc": f"0x{pc:x}",
            "candidate_count": len(candidates),
            "containing_count": len(containing),
            "module_path": str(module_path),
        }
    mapping = containing[0]
    if mapping["permission"] is not None and "x" not in str(mapping["permission"]):
        return {
            "valid": False,
            "error": "PC_MAPPING_NOT_EXECUTABLE",
            "main_lwp": int(lwp_match.group(1)),
            "pc": f"0x{pc:x}",
            "mapping": mapping,
            "module_path": str(module_path),
        }
    stable_offset = pc - int(mapping["start"]) + int(mapping["file_offset"])
    return {
        "valid": True,
        "main_lwp": int(lwp_match.group(1)),
        "pc": f"0x{pc:x}",
        "mapping_start": f"0x{int(mapping['start']):x}",
        "mapping_end": f"0x{int(mapping['end']):x}",
        "mapping_file_offset": f"0x{int(mapping['file_offset']):x}",
        "mapping_permission": mapping["permission"],
        "stable_module_offset": f"0x{stable_offset:x}",
        "formula": "pc - mapping_start + mapping_file_offset",
        "module_path": str(module_path),
    }


def offset_quality(
    baseline_result: dict[str, object],
    control: dict[str, object],
    output: str,
    module_path: Path,
) -> tuple[str, dict[str, object]]:
    if baseline_result.get("status") != "FAIL_HANG_REPRODUCED_WATCHDOG_RECOVERED":
        return "GDB_NOT_TRIGGERED_NO_HANG", {"valid": False, "error": "NO_HANG"}
    if not control.get("invoked"):
        return "GDB_ATTACH_FAILED", {"valid": False, "error": "GDB_NOT_INVOKED"}
    if control.get("helper_timeout"):
        return "GDB_HELPER_TIMEOUT", {"valid": False, "error": "GDB_HELPER_TIMEOUT"}
    if control.get("helper_error"):
        return "GDB_ATTACH_FAILED", {"valid": False, "error": "GDB_HELPER_ERROR"}
    if control.get("output_write_error"):
        return (
            "OFFSET_EVIDENCE_UNUSABLE_RAW_OUTPUT_NOT_SAVED",
            {"valid": False, "error": "RAW_OUTPUT_NOT_SAVED"},
        )
    pid = int(control.get("target_pid", -1))
    detached = f"process {pid}) detached" in output
    main_match = MAIN_LWP_PATTERN.search(output)
    module_seen = str(module_path) in output
    evidence = derive_module_offset(output, module_path)
    if (
        control.get("helper_returncode") == 0
        and detached
        and main_match is not None
        and int(main_match.group(1)) == pid
        and evidence.get("valid") is True
    ):
        return "OFFSET_EVIDENCE_COMPLETE_MAIN_THREAD_AND_MAPPING_IDENTIFIED", evidence
    if main_match is not None:
        return "OFFSET_EVIDENCE_PARTIAL_MAIN_THREAD_ONLY", evidence
    if module_seen:
        return "OFFSET_EVIDENCE_PARTIAL_MAPPING_ONLY", evidence
    if control.get("helper_returncode") not in (None, 0):
        return "GDB_ATTACH_FAILED", evidence
    return "OFFSET_EVIDENCE_UNUSABLE_MODULE_NOT_IDENTIFIED", evidence
