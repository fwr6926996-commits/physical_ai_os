"""Supervise the original stability runner using streamed-file heartbeats."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import psutil


HERE = Path(__file__).resolve().parent
WORKER = HERE / "run_stability_v2_9.py"
EVIDENCE_ROOT = HERE / "evidence" / "phase3_stability"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Guard the original GPU.0 stability path from native hangs.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--duration-minutes", type=float, default=30.0)
    parser.add_argument("--stall-seconds", type=float, default=15.0)
    parser.add_argument("--startup-seconds", type=float, default=60.0)
    parser.add_argument("--external-telemetry-seconds", type=float, default=5.0)
    return parser.parse_args()


def last_csv_row(path: Path) -> str | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        lines = deque(stream, maxlen=1)
    return lines[0].rstrip("\n") if lines else None


def process_snapshot(pid: int) -> dict[str, object]:
    try:
        process = psutil.Process(pid)
        return {
            "pid": pid,
            "status": process.status(),
            "cpu_percent": process.cpu_percent(interval=0.2),
            "memory_rss_bytes": process.memory_info().rss,
            "num_threads": process.num_threads(),
        }
    except psutil.Error as exc:
        return {"pid": pid, "snapshot_error": f"{type(exc).__name__}: {exc}"}


def external_telemetry(elapsed_s: float, pid: int) -> dict[str, object]:
    memory = psutil.virtual_memory()
    temperatures = []
    package_c = None
    for entries in psutil.sensors_temperatures(fahrenheit=False).values():
        for item in entries:
            if item.current is None:
                continue
            temperatures.append(float(item.current))
            if item.label == "Package id 0":
                package_c = float(item.current)
    try:
        worker_rss = psutil.Process(pid).memory_info().rss
    except psutil.Error:
        worker_rss = None
    return {
        "elapsed_s": elapsed_s,
        "worker_rss_bytes": worker_rss,
        "system_available_memory_bytes": memory.available,
        "package_temperature_c": package_c,
        "max_sensor_temperature_c": max(temperatures) if temperatures else None,
    }


def main() -> None:
    args = arguments()
    if (
        args.duration_minutes <= 0
        or args.stall_seconds <= 0
        or args.startup_seconds <= 0
        or args.external_telemetry_seconds <= 0
    ):
        raise ValueError("duration and timeout values must be > 0")
    run_dir = EVIDENCE_ROOT / args.run_id
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing run directory: {run_dir}")
    command = [
        sys.executable,
        str(WORKER),
        "--run-id", args.run_id,
        "--device", "GPU.0",
        "--duration-minutes", str(args.duration_minutes),
        "--warmup", "10",
        "--telemetry-seconds", "5",
        "--window-seconds", "60",
        "--telemetry-mode", "none",
    ]
    started_at = datetime.now(timezone.utc)
    supervisor_started = time.monotonic()
    child = subprocess.Popen(command)
    latency_path = run_dir / "latencies.csv"
    telemetry_path = run_dir / "telemetry.csv"
    external_telemetry_path = run_dir / "supervisor_telemetry.csv"
    last_size = -1
    last_activity = time.monotonic()
    termination = None
    diagnostic = None
    telemetry_rows = []
    next_telemetry = 0.0

    while child.poll() is None:
        now = time.monotonic()
        run_elapsed = now - supervisor_started
        if run_elapsed >= next_telemetry:
            telemetry_rows.append(external_telemetry(run_elapsed, child.pid))
            next_telemetry += args.external_telemetry_seconds
        if latency_path.exists():
            size = latency_path.stat().st_size
            if size != last_size:
                last_size = size
                last_activity = now
            timeout = args.stall_seconds
        else:
            timeout = args.startup_seconds
        if now - last_activity > timeout:
            diagnostic = process_snapshot(child.pid)
            diagnostic.update({
                "seconds_without_latency_file_growth": now - last_activity,
                "last_latency_csv_row": last_csv_row(latency_path),
                "latency_csv_bytes": latency_path.stat().st_size if latency_path.exists() else None,
                "worker_telemetry_csv_bytes": telemetry_path.stat().st_size if telemetry_path.exists() else None,
            })
            child.terminate()
            try:
                child.wait(timeout=5.0)
                termination = "SIGTERM"
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5.0)
                termination = "SIGKILL_AFTER_SIGTERM_TIMEOUT"
            break
        time.sleep(0.5)

    run_dir.mkdir(parents=True, exist_ok=True)
    if telemetry_rows:
        with external_telemetry_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=tuple(telemetry_rows[0]))
            writer.writeheader()
            writer.writerows(telemetry_rows)
    worker_result_path = run_dir / "result.json"
    worker_result = None
    if worker_result_path.exists():
        worker_result = json.loads(worker_result_path.read_text(encoding="utf-8"))
    if diagnostic is not None:
        status = "HANG_REPRODUCED_SUPERVISOR_RECOVERED"
    elif child.returncode == 0 and worker_result is not None:
        status = "WORKER_COMPLETED_REVIEW_PENDING"
    else:
        status = "WORKER_FAILED_WITHOUT_WATCHDOG_TIMEOUT"
    result = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "started_at_utc": started_at.isoformat(),
        "run_id": args.run_id,
        "status": status,
        "configuration": {
            "device": "GPU.0",
            "precision": "f32",
            "duration_minutes": args.duration_minutes,
            "stall_seconds": args.stall_seconds,
            "startup_seconds": args.startup_seconds,
            "external_telemetry_seconds": args.external_telemetry_seconds,
            "worker_telemetry_mode": "none",
            "worker_path": str(WORKER),
        },
        "child_pid": child.pid,
        "child_returncode": child.returncode,
        "termination": termination,
        "hang_diagnostic": diagnostic,
        "worker_result_status": worker_result.get("status") if worker_result else None,
        "worker_result_path": "result.json" if worker_result else None,
        "latencies_csv_last_row": last_csv_row(latency_path),
        "worker_telemetry_csv_last_row": last_csv_row(telemetry_path),
        "supervisor_telemetry_csv": "supervisor_telemetry.csv" if telemetry_rows else None,
        "supervisor_telemetry_last_row": last_csv_row(external_telemetry_path),
    }
    supervisor_path = run_dir / "supervisor_result.json"
    supervisor_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved supervisor evidence: {supervisor_path}")


if __name__ == "__main__":
    main()
