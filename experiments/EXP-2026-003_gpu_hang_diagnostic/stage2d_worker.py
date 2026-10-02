"""Stage 2B worker plus one scoped startup ptrace authorization."""

from __future__ import annotations

import ctypes
import multiprocessing as mp
import os
import platform
import time
from typing import Any

import numpy as np

from run_isolated_gpu_stability_v2_9 import ATOL, IR_PATH, PACKAGE_DIR, RTOL


PR_SET_PTRACER = 0x59616D61


def authorize_supervisor_ptrace() -> dict[str, object]:
    """Authorize only the supervisor and its descendants for this process lifetime."""
    supervisor_pid = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    ctypes.set_errno(0)
    returncode = int(libc.prctl(PR_SET_PTRACER, supervisor_pid, 0, 0, 0))
    error_number = ctypes.get_errno()
    evidence = {
        "mechanism": "PR_SET_PTRACER",
        "authorized_supervisor_pid": supervisor_pid,
        "returncode": returncode,
        "errno": error_number,
        "error": os.strerror(error_number) if error_number else None,
        "scope": "Supervisor and its descendants; target process lifetime only.",
    }
    if returncode != 0:
        raise RuntimeError(f"Scoped ptrace authorization failed: {evidence}")
    return evidence


def inference_worker(
    enter_sequence: Any,
    return_sequence: Any,
    messages: mp.Queue,
    duration_seconds: float,
    warmup: int,
) -> None:
    """Frozen Stage 2B path plus one authorization before OpenVINO initialization."""
    try:
        ptrace_authorization = authorize_supervisor_ptrace()

        import openvino as ov
        import torch

        core = ov.Core()
        available = core.available_devices
        runtime_device = "GPU.0"
        if runtime_device not in available and "GPU" in available:
            runtime_device = "GPU"
        if runtime_device not in available:
            raise RuntimeError(f"GPU.0 unavailable; detected={available}")
        full_name = core.get_property(runtime_device, ov.properties.device.full_name)
        if "intel" not in full_name.lower() or "nvidia" in full_name.lower():
            raise RuntimeError(f"GPU identity guard rejected {runtime_device}: {full_name}")

        model = core.read_model(IR_PATH)
        shapes = {port.any_name: str(port.partial_shape) for port in model.inputs}
        expected_shapes = {"state": "[1,6]", "wrist_image": "[1,3,480,640]"}
        if shapes != expected_shapes:
            raise RuntimeError(f"Frozen input contract changed: {shapes}")
        config = {
            ov.properties.hint.performance_mode: ov.properties.hint.PerformanceMode.LATENCY,
            ov.properties.hint.inference_precision: ov.Type.f32,
        }
        compile_started = time.perf_counter_ns()
        compiled = core.compile_model(model, runtime_device, config)
        compile_ms = (time.perf_counter_ns() - compile_started) / 1_000_000.0
        request = compiled.create_infer_request()

        input_path = PACKAGE_DIR / "reference_model_input.pt"
        output_path = PACKAGE_DIR / "reference_output_normalized.pt"
        model_input = torch.load(input_path, weights_only=False)
        expected = torch.load(output_path, weights_only=False)["action_chunk"].numpy()
        inputs = {
            "state": model_input["observation.state"].numpy(),
            "wrist_image": model_input["observation.images.wrist"].numpy(),
        }

        sequence = 1
        enter_sequence.value = sequence
        request.infer(inputs)
        return_sequence.value = sequence
        initial = request.get_output_tensor(0).data.copy()
        initial_error = np.abs(initial.astype(np.float32) - expected.astype(np.float32))
        initial_finite = bool(np.isfinite(initial).all())
        initial_correct = initial_finite and bool(
            np.allclose(initial, expected, rtol=RTOL, atol=ATOL)
        )
        if not initial_correct:
            raise RuntimeError(
                "Initial GPU correctness failed: "
                f"max_abs_error={float(initial_error.max())}"
            )
        for _ in range(warmup):
            sequence += 1
            enter_sequence.value = sequence
            request.infer(inputs)
            return_sequence.value = sequence

        versions = {
            name: {
                "build_number": value.build_number,
                "description": value.description,
            }
            for name, value in core.get_versions(runtime_device).items()
        }
        messages.put({
            "type": "ready",
            "pid": os.getpid(),
            "available_devices": available,
            "runtime_device": runtime_device,
            "device_full_name": full_name,
            "openvino_version": ov.__version__,
            "platform": platform.platform(),
            "plugin_versions": versions,
            "compile_ms": compile_ms,
            "ptrace_authorization": ptrace_authorization,
            "initial_correctness": {
                "rtol": RTOL,
                "atol": ATOL,
                "max_abs_error": float(initial_error.max()),
                "mean_abs_error": float(initial_error.mean()),
                "status": "PASS",
            },
        })

        started = time.monotonic()
        iteration = 0
        while time.monotonic() - started < duration_seconds:
            sequence += 1
            enter_sequence.value = sequence
            inference_started = time.perf_counter_ns()
            request.infer(inputs)
            return_sequence.value = sequence
            latency_ms = (time.perf_counter_ns() - inference_started) / 1_000_000.0
            iteration += 1
            elapsed_s = time.monotonic() - started
            actual = request.get_output_tensor(0).data.copy()
            finite = bool(np.isfinite(actual).all())
            if finite:
                error = np.abs(actual.astype(np.float32) - expected.astype(np.float32))
                max_abs_error = float(error.max())
                correct = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
            else:
                max_abs_error = float("inf")
                correct = False
            messages.put({
                "type": "heartbeat",
                "iteration": iteration,
                "elapsed_s": elapsed_s,
                "latency_ms": latency_ms,
                "finite": finite,
                "correct": correct,
                "max_abs_error": max_abs_error,
            })
            if not finite or not correct:
                messages.put({
                    "type": "validation_failure",
                    "iteration": iteration,
                    "finite": finite,
                    "correct": correct,
                    "max_abs_error": max_abs_error,
                })
                return
        messages.put({
            "type": "completed",
            "iteration": iteration,
            "elapsed_s": time.monotonic() - started,
        })
    except BaseException as exc:
        messages.put({
            "type": "worker_exception",
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        })
