#!/usr/bin/env python3
"""Mock-only worker for Phase 4 supervisor control-flow validation."""

from __future__ import annotations

import argparse
import json
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--scenario", choices=("success", "hang", "startup_hang", "failure"), required=True
    )
    return parser.parse_args()


def emit(path: Path, event_type: str, **fields: Any) -> None:
    event = {
        "type": event_type,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "worker_monotonic_s": time.monotonic(),
        **fields,
    }
    with path.open("a", encoding="utf-8", buffering=1) as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        stream.flush()


def main() -> int:
    args = arguments()
    events = args.run_dir / "events.jsonl"
    emit(events, "worker_started", run_id=args.run_id, stage=args.stage, mock=True)
    if args.scenario == "startup_hang":
        signal.pause()
        return 2
    emit(events, "artifacts_verified", mock=True)
    emit(events, "runtime_identity_verified", mock=True)
    emit(events, "compile_enter", mock=True)
    emit(events, "compile_return", compile_ms=0.1, mock=True)
    emit(events, "infer_enter", sequence=1, phase="measurement", iteration=0, mock=True)
    if args.scenario == "hang":
        signal.pause()
        return 2
    if args.scenario == "failure":
        emit(
            events,
            "infer_return",
            sequence=1,
            phase="measurement",
            iteration=0,
            finite=True,
            correct=False,
            max_abs_error=1.0,
            mock=True,
        )
        emit(events, "worker_failed", error_type="MockCorrectnessFailure", mock=True)
        (args.run_dir / "worker_result.json").write_text(
            json.dumps({"status": "MOCK_WORKER_FAIL"}, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1
    emit(
        events,
        "infer_return",
        sequence=1,
        phase="measurement",
        iteration=0,
        finite=True,
        correct=True,
        max_abs_error=0.0,
        mock=True,
    )
    emit(events, "worker_completed", measured_iterations=1, mock=True)
    (args.run_dir / "worker_result.json").write_text(
        json.dumps({"status": "WORKER_PASS_SUPERVISOR_REVIEW_PENDING"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
