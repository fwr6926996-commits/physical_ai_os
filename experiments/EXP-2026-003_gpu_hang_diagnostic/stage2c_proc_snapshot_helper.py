"""Capture one best-effort /proc process and thread snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROCESS_FIELDS = ("status", "stat", "wchan", "syscall", "sched")
THREAD_FIELDS = ("comm", "status", "stat", "wchan", "syscall", "stack")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture one bounded-by-parent /proc snapshot.")
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"), help=argparse.SUPPRESS)
    return parser.parse_args()


def read_field(path: Path) -> dict[str, object]:
    try:
        return {"status": "READ", "content": path.read_text(errors="replace")}
    except OSError as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


def maps_summary(path: Path) -> dict[str, object]:
    try:
        content = path.read_text(errors="replace")
    except OSError as exc:
        return {"status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}
    permissions: Counter[str] = Counter()
    file_backed = 0
    anonymous = 0
    lines = content.splitlines()
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) >= 2:
            permissions[fields[1]] += 1
        if len(fields) == 6 and fields[5].startswith("/"):
            file_backed += 1
        else:
            anonymous += 1
    return {
        "status": "READ",
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "mapping_count": len(lines),
        "file_backed_count": file_backed,
        "anonymous_or_special_count": anonymous,
        "permissions": dict(sorted(permissions.items())),
    }


def capture(pid: int, proc_root: Path) -> dict[str, object]:
    started = time.monotonic()
    captured_at = datetime.now(timezone.utc).isoformat()
    target = proc_root / str(pid)
    if not target.exists():
        return {
            "schema_version": 1,
            "captured_at_utc": captured_at,
            "pid": pid,
            "status": "TARGET_EXITED",
            "elapsed_seconds": time.monotonic() - started,
        }

    process = {field: read_field(target / field) for field in PROCESS_FIELDS}
    process["maps_summary"] = maps_summary(target / "maps")
    threads: list[dict[str, object]] = []
    task_root = target / "task"
    try:
        task_dirs = sorted(
            (path for path in task_root.iterdir() if path.name.isdigit()),
            key=lambda path: int(path.name),
        )
        task_error = None
    except OSError as exc:
        task_dirs = []
        task_error = f"{type(exc).__name__}: {exc}"
    for task_dir in task_dirs:
        thread: dict[str, object] = {"tid": int(task_dir.name)}
        for field in THREAD_FIELDS:
            thread[field] = read_field(task_dir / field)
        threads.append(thread)

    read_count = 0
    unavailable_count = 0
    for value in process.values():
        if isinstance(value, dict) and value.get("status") == "READ":
            read_count += 1
        elif isinstance(value, dict):
            unavailable_count += 1
    for thread in threads:
        for field in THREAD_FIELDS:
            value = thread[field]
            if isinstance(value, dict) and value.get("status") == "READ":
                read_count += 1
            else:
                unavailable_count += 1
    if task_error is not None:
        unavailable_count += 1

    return {
        "schema_version": 1,
        "captured_at_utc": captured_at,
        "pid": pid,
        "status": (
            "CAPTURED_COMPLETE" if unavailable_count == 0 else "CAPTURED_PARTIAL"
        ),
        "process": process,
        "thread_count": len(threads),
        "threads": threads,
        "task_enumeration_error": task_error,
        "field_counts": {"read": read_count, "unavailable": unavailable_count},
        "elapsed_seconds": time.monotonic() - started,
        "interpretation_limits": [
            "This is one OS-visible snapshot, not a causal diagnosis.",
            "UNAVAILABLE fields must not be interpreted as absent state.",
            "The maps content is not stored; only a hash and aggregate summary are retained.",
        ],
    }


def main() -> None:
    args = arguments()
    result = capture(args.pid, args.proc_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "pid": result["pid"],
        "status": result["status"],
        "thread_count": result.get("thread_count"),
        "elapsed_seconds": result["elapsed_seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
