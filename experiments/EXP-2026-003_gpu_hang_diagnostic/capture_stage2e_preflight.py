"""Draft read-only preflight for one approved Stage 2E-A attempt."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from capture_stage2a_preflight import (
    PACKAGE_DIR,
    dri_usage,
    matching_processes,
    power_context,
    read_text,
    sha256,
)
from run_stage2e_offset_capture import (
    MANIFEST_PATH,
    OPENCL_RUNTIME_PATH,
    PREFLIGHT_ROOT,
    PROTOCOL_ID,
    RUN_ID_PATTERN,
    implementation_hashes,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Stage 2E-A context without initializing OpenVINO or GPU."
    )
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def command_output(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
        check=False,
    )
    return {"returncode": completed.returncode, "output": completed.stdout.strip()}


def build_id(path: Path) -> dict[str, object]:
    return command_output(["readelf", "-n", str(path)])


def main() -> None:
    args = arguments()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError("run-id must match stage2e_a1_...")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("Stage 2E manifest protocol mismatch")
    if manifest.get("execution_state") != "READY_FOR_ONE_APPROVED_ATTEMPT":
        raise RuntimeError(
            "Stage 2E preflight is blocked: implementation is not approved/frozen"
        )
    hashes = implementation_hashes()
    if manifest.get("artifacts_sha256") != hashes:
        raise RuntimeError("Stage 2E implementation differs from approved frozen manifest")

    destination = PREFLIGHT_ROOT / f"{args.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Preflight evidence already exists: {destination}")
    openvino_lib = Path(
        "/home/lucas/intel_ws/openvino_env/lib/python3.12/site-packages/openvino/libs/libopenvino.so.2631"
    )
    gpu_plugin = Path(
        "/home/lucas/intel_ws/openvino_env/lib/python3.12/site-packages/openvino/libs/libopenvino_intel_gpu_plugin.so"
    )
    snapshot = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": args.run_id,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "captured_at_local": datetime.now().astimezone().isoformat(),
        "pid": os.getpid(),
        "scope": "Read-only preflight; OpenVINO and GPU are intentionally not initialized.",
        "platform": platform.uname()._asdict(),
        "uptime": read_text(Path("/proc/uptime")),
        "memory": read_text(Path("/proc/meminfo")),
        "ptrace_scope": read_text(Path("/proc/sys/kernel/yama/ptrace_scope")),
        "gdb_version": command_output(["/usr/bin/gdb", "--version"]),
        "artifacts_sha256": hashes,
        "model_artifacts_sha256": {
            "ir_xml": sha256(PACKAGE_DIR / "act_fp32.xml"),
            "ir_bin": sha256(PACKAGE_DIR / "act_fp32.bin"),
            "reference_input": sha256(PACKAGE_DIR / "reference_model_input.pt"),
            "reference_output": sha256(PACKAGE_DIR / "reference_output_normalized.pt"),
        },
        "native_library_build_ids": {
            "openvino_runtime": build_id(openvino_lib),
            "intel_gpu_plugin": build_id(gpu_plugin),
            "intel_opencl_runtime": build_id(OPENCL_RUNTIME_PATH),
        },
        "matching_process_names": matching_processes(),
        "dri_usage_best_effort": dri_usage(),
        "power_context_best_effort": power_context(),
        "interpretation_limits": [
            "Build IDs identify binaries; they do not provide missing debug symbols.",
            "A process-name filter cannot prove that no other GPU workload exists.",
            "Open DRM handles do not prove active GPU load.",
            "OpenVINO identity is captured by the worker to avoid extra pre-run initialization.",
        ],
    }
    destination.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))
    print(f"Saved Stage 2E preflight evidence: {destination}")


if __name__ == "__main__":
    main()

