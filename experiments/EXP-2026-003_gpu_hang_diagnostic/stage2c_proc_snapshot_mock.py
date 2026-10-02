"""No-GPU mock checks for the Stage 2C /proc snapshot mechanism."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from run_stage2c_proc_snapshot import bounded_snapshot_then_stop
from stage2c_proc_snapshot_helper import PROCESS_FIELDS, THREAD_FIELDS, capture


class MockProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid


def make_proc_tree(root: Path, pid: int, *, omit_thread_field: str | None = None) -> None:
    process_root = root / str(pid)
    process_root.mkdir(parents=True)
    for field in PROCESS_FIELDS:
        (process_root / field).write_text(f"mock process {field}\n", encoding="utf-8")
    (process_root / "maps").write_text(
        "1000-2000 r-xp 00000000 00:00 0 /mock/lib.so\n"
        "2000-3000 rw-p 00000000 00:00 0 [heap]\n",
        encoding="utf-8",
    )
    for tid in (pid, pid + 1):
        task_root = process_root / "task" / str(tid)
        task_root.mkdir(parents=True)
        for field in THREAD_FIELDS:
            if tid == pid + 1 and field == omit_thread_field:
                continue
            (task_root / field).write_text(f"mock thread {tid} {field}\n", encoding="utf-8")


def assert_capture_classes(temp_root: Path) -> dict[str, str]:
    complete_root = temp_root / "complete_proc"
    make_proc_tree(complete_root, 41001)
    complete = capture(41001, complete_root)
    assert complete["status"] == "CAPTURED_COMPLETE", complete
    assert complete["thread_count"] == 2, complete

    partial_root = temp_root / "partial_proc"
    make_proc_tree(partial_root, 42001, omit_thread_field="stack")
    partial = capture(42001, partial_root)
    assert partial["status"] == "CAPTURED_PARTIAL", partial
    assert partial["field_counts"]["unavailable"] == 1, partial

    exited = capture(43001, temp_root / "missing_proc")
    assert exited["status"] == "TARGET_EXITED", exited
    return {
        "complete": str(complete["status"]),
        "partial": str(partial["status"]),
        "target_exited": str(exited["status"]),
    }


def assert_timeout_still_recovers(temp_root: Path) -> dict[str, object]:
    output = temp_root / "timeout.json"
    control: dict[str, object] = {}
    recovery_calls: list[int] = []

    def original_stop(process: MockProcess) -> str:
        recovery_calls.append(process.pid)
        return "MOCK_SIGTERM"

    recovery = bounded_snapshot_then_stop(
        MockProcess(44001),  # type: ignore[arg-type]
        original_stop,  # type: ignore[arg-type]
        output,
        control,
        helper_command=[sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_seconds=0.1,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "HELPER_TIMEOUT", result
    assert control.get("helper_timeout") is True, control
    assert recovery == "MOCK_SIGTERM", recovery
    assert recovery_calls == [44001], recovery_calls
    return {
        "snapshot_status": result["status"],
        "recovery": recovery,
        "recovery_call_count": len(recovery_calls),
    }


def assert_failed_helper_still_recovers(temp_root: Path) -> dict[str, object]:
    output = temp_root / "failed.json"
    control: dict[str, object] = {}
    recovery_calls: list[int] = []

    def original_stop(process: MockProcess) -> str:
        recovery_calls.append(process.pid)
        return "MOCK_SIGTERM"

    recovery = bounded_snapshot_then_stop(
        MockProcess(45001),  # type: ignore[arg-type]
        original_stop,  # type: ignore[arg-type]
        output,
        control,
        helper_command=[sys.executable, "-c", "raise RuntimeError('mock failure')"],
        timeout_seconds=0.5,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "HELPER_FAILED", result
    assert recovery == "MOCK_SIGTERM", recovery
    assert recovery_calls == [45001], recovery_calls
    return {
        "snapshot_status": result["status"],
        "recovery": recovery,
        "recovery_call_count": len(recovery_calls),
    }


def assert_real_proc_child_capture() -> dict[str, object]:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        result = capture(child.pid, Path("/proc"))
    finally:
        child.terminate()
        child.wait(timeout=5)
    assert result["status"] in {"CAPTURED_COMPLETE", "CAPTURED_PARTIAL"}, result
    assert int(result["thread_count"]) >= 1, result
    return {
        "status": result["status"],
        "thread_count": result["thread_count"],
        "unavailable_fields": result["field_counts"]["unavailable"],
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="stage2c_mock_") as temp:
        temp_root = Path(temp)
        result = {
            "protocol_id": "EXP-2026-003-STAGE2C-PROC-THREAD-SNAPSHOT-V1",
            "scope": "No GPU, OpenVINO, or historical worker execution.",
            "capture_classes": assert_capture_classes(temp_root),
            "timeout_recovery": assert_timeout_still_recovers(temp_root),
            "failed_helper_recovery": assert_failed_helper_still_recovers(temp_root),
            "real_proc_child": assert_real_proc_child_capture(),
            "status": "PASS",
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
