"""No-GPU probe for scoped ptrace authorization under Yama ptrace_scope=1."""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


PR_SET_PTRACER = 0x59616D61


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test scoped ptrace authorization on an ordinary sleeping child."
    )
    parser.add_argument("--target", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--allow-pid", type=int, default=0, help=argparse.SUPPRESS)
    return parser.parse_args()


def target_mode(allow_pid: int) -> None:
    result: dict[str, object] = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "allow_pid": allow_pid,
    }
    if allow_pid:
        libc = ctypes.CDLL(None, use_errno=True)
        returncode = int(libc.prctl(PR_SET_PTRACER, allow_pid, 0, 0, 0))
        error_number = ctypes.get_errno()
        result.update(
            {
                "prctl_returncode": returncode,
                "prctl_errno": error_number,
                "prctl_error": os.strerror(error_number) if error_number else None,
            }
        )
    print(json.dumps(result), flush=True)
    time.sleep(30)


def one_case(*, authorized: bool, strace_path: str) -> dict[str, object]:
    parent_pid = os.getpid()
    command = [sys.executable, str(Path(__file__).resolve()), "--target"]
    if authorized:
        command.extend(["--allow-pid", str(parent_pid)])
    target = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
    assert target.stdout is not None
    identity = json.loads(target.stdout.readline())
    target_pid = int(identity["pid"])
    tracer = subprocess.Popen(
        [strace_path, "-e", "trace=none", "-p", str(target_pid)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.35)
    attached_for_window = tracer.poll() is None
    if attached_for_window:
        tracer.terminate()
    try:
        stdout, stderr = tracer.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        tracer.kill()
        stdout, stderr = tracer.communicate()
    target_alive_after_detach = target.poll() is None
    if target_alive_after_detach:
        target.terminate()
    try:
        target.wait(timeout=2)
    except subprocess.TimeoutExpired:
        target.kill()
        target.wait(timeout=2)
    return {
        "authorized": authorized,
        "target_identity": identity,
        "tracer_attached_for_observation_window": attached_for_window,
        "tracer_returncode": tracer.returncode,
        "tracer_stdout": stdout.strip(),
        "tracer_stderr": stderr.strip(),
        "target_alive_after_tracer_detach": target_alive_after_detach,
    }


def main() -> None:
    args = arguments()
    if args.target:
        target_mode(args.allow_pid)
        return
    strace_path = shutil.which("strace")
    if strace_path is None:
        raise FileNotFoundError("strace is required for this no-GPU permission probe")
    ptrace_scope_path = Path("/proc/sys/kernel/yama/ptrace_scope")
    ptrace_scope = (
        ptrace_scope_path.read_text(encoding="utf-8").strip()
        if ptrace_scope_path.exists()
        else "UNAVAILABLE"
    )
    unauthorized = one_case(authorized=False, strace_path=strace_path)
    authorized = one_case(authorized=True, strace_path=strace_path)
    authorized_identity = authorized["target_identity"]
    prctl_ok = (
        isinstance(authorized_identity, dict)
        and authorized_identity.get("prctl_returncode") == 0
    )
    status = (
        "PASS_SCOPED_PTRACE_ROUTE_FEASIBLE"
        if prctl_ok
        and authorized["tracer_attached_for_observation_window"]
        and authorized["target_alive_after_tracer_detach"]
        else "FAIL_SCOPED_PTRACE_ROUTE_NOT_ESTABLISHED"
    )
    result = {
        "schema_version": 1,
        "protocol_id": "EXP-2026-003-STAGE2D-PTRACE-FEASIBILITY-PROBE-V1",
        "scope": "Ordinary sleeping Python child only; no OpenVINO or GPU access.",
        "ptrace_scope": ptrace_scope,
        "unauthorized_control": unauthorized,
        "scoped_authorization": authorized,
        "status": status,
        "interpretation_limits": [
            "This validates only the host ptrace permission route and detach behavior.",
            "It does not validate GDB availability, stack quality, symbols, or GPU-hang diagnosis.",
            "PR_SET_PTRACER authorization lasts only for the target process lifetime.",
        ],
    }
    print(json.dumps(result, indent=2))
    if status != "PASS_SCOPED_PTRACE_ROUTE_FEASIBLE":
        raise SystemExit(errno.EPERM)


if __name__ == "__main__":
    main()
