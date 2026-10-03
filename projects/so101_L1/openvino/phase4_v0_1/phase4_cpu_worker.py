#!/usr/bin/env python3
"""Frozen DK-2500 CPU FP32 qualification worker.

The worker performs one explicitly selected stage. It never retries, changes device, or recovers
itself. The external supervisor owns loss-of-progress detection and bounded termination.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import openvino as ov
import torch


HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "phase4_frozen_config.json"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one frozen Phase 4 CPU FP32 stage.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True, choices=("correctness", "short", "stability"))
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser.parse_args()


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class EventWriter:
    def __init__(self, path: Path) -> None:
        self._stream = path.open("a", encoding="utf-8", buffering=1)

    def emit(self, event_type: str, **fields: Any) -> None:
        event = {
            "type": event_type,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "worker_monotonic_s": time.monotonic(),
            **fields,
        }
        self._stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        self._stream.flush()

    def close(self) -> None:
        self._stream.close()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_artifacts(package_dir: Path, config: dict[str, Any]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, expected in config["artifacts"].items():
        path = package_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing frozen artifact: {path}")
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Artifact hash mismatch for {name}: {actual} != {expected}")
        observed[name] = actual
    return observed


def stats(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    sample = np.asarray(values, dtype=np.float64)
    return {
        "min": float(sample.min()),
        "mean": float(sample.mean()),
        "p50": float(np.percentile(sample, 50)),
        "p95": float(np.percentile(sample, 95)),
        "p99": float(np.percentile(sample, 99)),
        "max": float(sample.max()),
    }


def main() -> int:
    args = arguments()
    config = load_config()
    run_dir = args.run_dir.resolve()
    package_dir = args.package_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Supervisor-created run directory is missing: {run_dir}")
    events = EventWriter(run_dir / "events.jsonl")
    started_at = datetime.now(timezone.utc)
    latencies: list[float] = []
    maximum_abs_error = 0.0
    measured_iterations = 0
    failure: dict[str, Any] | None = None
    artifacts: dict[str, str] = {}
    runtime_identity: dict[str, Any] = {}
    compile_ms: float | None = None
    latency_stream = None
    try:
        events.emit("worker_started", run_id=args.run_id, stage=args.stage)
        artifacts = verify_artifacts(package_dir, config)
        events.emit("artifacts_verified", hashes=artifacts)

        if ov.__version__ != config["openvino_version"]:
            raise RuntimeError(
                f"OpenVINO version mismatch: {ov.__version__} != {config['openvino_version']}"
            )
        core = ov.Core()
        available = list(core.available_devices)
        if config["device"] not in available:
            raise RuntimeError(f"Frozen CPU device unavailable; detected={available}")
        full_name = core.get_property(config["device"], ov.properties.device.full_name)
        if full_name != config["cpu_full_name"]:
            raise RuntimeError(f"CPU identity mismatch: {full_name} != {config['cpu_full_name']}")
        runtime_identity = {
            "platform": platform.platform(),
            "python": sys.version,
            "openvino": ov.__version__,
            "available_devices": available,
            "runtime_device": config["device"],
            "device_full_name": full_name,
        }
        events.emit("runtime_identity_verified", **runtime_identity)

        model_path = package_dir / "act_fp32.xml"
        model = core.read_model(model_path)
        shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
        expected_shapes = {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}
        if shapes != expected_shapes:
            raise RuntimeError(f"Frozen input contract changed: {shapes}")

        compile_config = {
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
            ov.properties.hint.inference_precision: ov.Type.f32,
        }
        events.emit("compile_enter")
        compile_started = time.perf_counter_ns()
        compiled = core.compile_model(model, config["device"], compile_config)
        compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0
        events.emit("compile_return", compile_ms=compile_ms)

        model_input = torch.load(package_dir / "reference_model_input.pt", weights_only=False)
        expected = torch.load(
            package_dir / "reference_output_normalized.pt", weights_only=False
        )["action_chunk"].numpy()
        inputs = {
            "state": model_input["observation.state"].numpy(),
            "wrist_image": model_input["observation.images.wrist"].numpy(),
        }
        request = compiled.create_infer_request()
        stage_config = config["stages"][args.stage]
        latency_path = run_dir / "latencies.csv"
        latency_stream = latency_path.open("w", newline="", encoding="utf-8", buffering=1)
        writer = csv.DictWriter(
            latency_stream,
            fieldnames=(
                "phase",
                "iteration",
                "elapsed_s",
                "latency_ms",
                "finite",
                "correct",
                "max_abs_error",
            ),
        )
        writer.writeheader()

        sequence = 0

        def infer_once(phase: str, iteration: int, elapsed_s: float) -> None:
            nonlocal sequence, maximum_abs_error, measured_iterations
            sequence += 1
            events.emit("infer_enter", sequence=sequence, phase=phase, iteration=iteration)
            started_ns = time.perf_counter_ns()
            request.infer(inputs)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
            actual = request.get_output_tensor(0).data.copy()
            if actual.shape != expected.shape:
                raise RuntimeError(
                    f"Output shape mismatch: {actual.shape} != {expected.shape}"
                )
            if actual.dtype != expected.dtype or actual.dtype != np.dtype("float32"):
                raise RuntimeError(
                    f"Output dtype mismatch: actual={actual.dtype} expected={expected.dtype}"
                )
            finite = bool(np.isfinite(actual).all())
            if finite:
                error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
                max_abs_error = float(error.max())
                correct = bool(
                    np.allclose(
                        actual,
                        expected,
                        rtol=config["correctness"]["rtol"],
                        atol=config["correctness"]["atol"],
                    )
                )
            else:
                max_abs_error = float("inf")
                correct = False
            maximum_abs_error = max(maximum_abs_error, max_abs_error)
            writer.writerow(
                {
                    "phase": phase,
                    "iteration": iteration,
                    "elapsed_s": elapsed_s,
                    "latency_ms": latency_ms,
                    "finite": finite,
                    "correct": correct,
                    "max_abs_error": max_abs_error,
                }
            )
            latency_stream.flush()
            events.emit(
                "infer_return",
                sequence=sequence,
                phase=phase,
                iteration=iteration,
                latency_ms=latency_ms,
                finite=finite,
                correct=correct,
                max_abs_error=max_abs_error,
            )
            if not finite or not correct:
                raise RuntimeError(
                    f"Correctness gate failed in {phase} iteration {iteration}: "
                    f"finite={finite} max_abs_error={max_abs_error}"
                )
            if phase == "measurement":
                latencies.append(latency_ms)
                measured_iterations += 1

        infer_once("correctness", 0, 0.0)
        for iteration in range(stage_config["warmup_iterations"]):
            infer_once("warmup", iteration, 0.0)

        events.emit("measurement_started", stage=args.stage)
        measurement_started = time.monotonic()
        if args.stage in ("correctness", "short"):
            for iteration in range(stage_config["measured_iterations"]):
                infer_once(
                    "measurement", iteration, time.monotonic() - measurement_started
                )
        else:
            duration_s = float(stage_config["duration_seconds"])
            iteration = 0
            while time.monotonic() - measurement_started < duration_s:
                infer_once(
                    "measurement", iteration, time.monotonic() - measurement_started
                )
                iteration += 1
        elapsed_s = time.monotonic() - measurement_started
        events.emit(
            "worker_completed",
            measured_iterations=measured_iterations,
            measurement_elapsed_s=elapsed_s,
        )
        result = {
            "schema_version": 1,
            "protocol_id": config["protocol_id"],
            "protocol_snapshot": config["protocol_snapshot"],
            "run_id": args.run_id,
            "stage": args.stage,
            "status": "WORKER_PASS_SUPERVISOR_REVIEW_PENDING",
            "started_at_utc": started_at.isoformat(),
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "runtime_identity": runtime_identity,
            "artifacts": artifacts,
            "configuration": stage_config,
            "compile_ms": compile_ms,
            "execution": {
                "measured_iterations": measured_iterations,
                "measurement_elapsed_s": elapsed_s,
                "maximum_abs_error": maximum_abs_error,
            },
            "latency_ms": stats(latencies),
            "evidence_files": {"events": "events.jsonl", "latencies": "latencies.csv"},
        }
        atomic_json(run_dir / "worker_result.json", result)
        return 0
    except Exception as exc:
        failure = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        events.emit("worker_failed", error_type=failure["type"], message=failure["message"])
        atomic_json(
            run_dir / "worker_result.json",
            {
                "schema_version": 1,
                "protocol_id": config["protocol_id"],
                "protocol_snapshot": config["protocol_snapshot"],
                "run_id": args.run_id,
                "stage": args.stage,
                "status": "WORKER_FAIL",
                "started_at_utc": started_at.isoformat(),
                "ended_at_utc": datetime.now(timezone.utc).isoformat(),
                "runtime_identity": runtime_identity,
                "artifacts": artifacts,
                "compile_ms": compile_ms,
                "failure": failure,
            },
        )
        return 1
    finally:
        if latency_stream is not None:
            latency_stream.close()
        events.close()


if __name__ == "__main__":
    raise SystemExit(main())
