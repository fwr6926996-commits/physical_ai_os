"""No-GPU GDB attach, stack-quality, detach, and timeout mock."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE_PATH = HERE / "stage2d_native_mock.c"
PR_SET_PTRACER = 0x59616D61
EXPECTED_SYMBOLS = (
    "mock_native_layer_three",
    "mock_native_layer_two",
    "mock_native_layer_one",
    "mock_infer_busy_loop",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate bounded GDB native-stack capture without OpenVINO or GPU."
    )
    parser.add_argument("--target", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--allow-pid", type=int, default=0, help=argparse.SUPPRESS)
    return parser.parse_args()


def target_mode(library: Path, allow_pid: int) -> None:
    identity: dict[str, object] = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "allow_pid": allow_pid,
    }
    if allow_pid:
        libc = ctypes.CDLL(None, use_errno=True)
        returncode = int(libc.prctl(PR_SET_PTRACER, allow_pid, 0, 0, 0))
        error_number = ctypes.get_errno()
        identity.update(
            {
                "prctl_returncode": returncode,
                "prctl_errno": error_number,
                "prctl_error": os.strerror(error_number) if error_number else None,
            }
        )
    native = ctypes.CDLL(str(library))
    native.mock_infer_busy_loop.argtypes = []
    native.mock_infer_busy_loop.restype = None
    print(json.dumps(identity), flush=True)
    native.mock_infer_busy_loop()


def compile_mock(gcc_path: str, library: Path) -> dict[str, object]:
    command = [
        gcc_path,
        "-shared",
        "-fPIC",
        "-g",
        "-O0",
        "-fno-omit-frame-pointer",
        str(SOURCE_PATH),
        "-o",
        str(library),
    ]
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"native mock compilation failed: {completed.stdout}")
    return {"command": command, "returncode": completed.returncode}


def start_target(library: Path, *, authorized: bool) -> tuple[subprocess.Popen[str], dict[str, object]]:
    command = [sys.executable, str(Path(__file__).resolve()), "--target", "--library", str(library)]
    if authorized:
        command.extend(["--allow-pid", str(os.getpid())])
    target = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert target.stdout is not None
    line = target.stdout.readline()
    if not line:
        stderr = target.stderr.read() if target.stderr is not None else ""
        raise RuntimeError(f"target failed before ready: {stderr}")
    return target, json.loads(line)


def gdb_command(gdb_path: str, pid: int, *, pause_inside_gdb: bool = False) -> list[str]:
    command = [
        gdb_path,
        "--batch",
        "--nx",
        "--quiet",
        "-ex",
        "set pagination off",
        "-ex",
        "set confirm off",
        "-ex",
        f"attach {pid}",
    ]
    if pause_inside_gdb:
        command.extend(
            [
                "-ex",
                "python import gdb, time; assert gdb.selected_inferior().pid != 0; time.sleep(10)",
            ]
        )
    else:
        command.extend(["-ex", "thread apply all bt", "-ex", "detach"])
    return command


def process_state(pid: int) -> str:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("State:"):
                return line.split(":", 1)[1].strip()
    except OSError as exc:
        return f"UNAVAILABLE: {type(exc).__name__}: {exc}"
    return "UNKNOWN"


def recover_target(target: subprocess.Popen[str]) -> dict[str, object]:
    state_before = process_state(target.pid)
    if state_before.startswith(("T", "t")):
        os.kill(target.pid, signal.SIGCONT)
    target.terminate()
    try:
        target.wait(timeout=2)
        recovery = "SIGTERM"
    except subprocess.TimeoutExpired:
        target.kill()
        target.wait(timeout=2)
        recovery = "SIGKILL_AFTER_SIGTERM_TIMEOUT"
    return {
        "state_before_recovery": state_before,
        "recovery": recovery,
        "exitcode": target.returncode,
    }


def unauthorized_control(gdb_path: str, library: Path) -> dict[str, object]:
    target, identity = start_target(library, authorized=False)
    try:
        completed = subprocess.run(
            gdb_command(gdb_path, target.pid),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        output = completed.stdout
        rejected = (
            "Operation not permitted" in output
            or "不允许的操作" in output
            or "Could not attach to process" in output
        )
        return {
            "target_identity": identity,
            "gdb_returncode": completed.returncode,
            "attach_rejected": rejected,
            "expected_symbols_seen": [symbol for symbol in EXPECTED_SYMBOLS if symbol in output],
            "gdb_output": output,
            "target_alive_after_gdb": target.poll() is None,
            "recovery": recover_target(target),
        }
    finally:
        if target.poll() is None:
            recover_target(target)


def authorized_stack_capture(gdb_path: str, library: Path) -> dict[str, object]:
    target, identity = start_target(library, authorized=True)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            gdb_command(gdb_path, target.pid),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=5,
            check=False,
        )
        elapsed = time.monotonic() - started
        output = completed.stdout
        seen = [symbol for symbol in EXPECTED_SYMBOLS if symbol in output]
        return {
            "target_identity": identity,
            "gdb_returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "expected_symbols_seen": seen,
            "all_expected_symbols_seen": len(seen) == len(EXPECTED_SYMBOLS),
            "gdb_output": output,
            "target_alive_after_gdb": target.poll() is None,
            "target_state_after_gdb": process_state(target.pid),
            "recovery": recover_target(target),
        }
    finally:
        if target.poll() is None:
            recover_target(target)


def timeout_detach(gdb_path: str, library: Path) -> dict[str, object]:
    target, identity = start_target(library, authorized=True)
    started = time.monotonic()
    timed_out = False
    output = ""
    try:
        try:
            completed = subprocess.run(
                gdb_command(gdb_path, target.pid, pause_inside_gdb=True),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=1.0,
                check=False,
            )
            output = completed.stdout
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            raw = exc.stdout or ""
            output = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
        elapsed = time.monotonic() - started
        time.sleep(0.1)
        return {
            "target_identity": identity,
            "helper_timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "gdb_output": output,
            "target_alive_after_gdb_timeout": target.poll() is None,
            "target_state_after_gdb_timeout": process_state(target.pid),
            "recovery": recover_target(target),
        }
    finally:
        if target.poll() is None:
            recover_target(target)


def main() -> None:
    args = arguments()
    if args.target:
        if args.library is None:
            raise ValueError("--library is required in target mode")
        target_mode(args.library, args.allow_pid)
        return
    gcc_path = shutil.which("gcc")
    gdb_path = shutil.which("gdb")
    if gcc_path is None or gdb_path is None:
        raise FileNotFoundError("gcc and gdb are required")
    with tempfile.TemporaryDirectory(prefix="stage2d_gdb_mock_") as temporary:
        library = Path(temporary) / "libstage2d_native_mock.so"
        compilation = compile_mock(gcc_path, library)
        unauthorized = unauthorized_control(gdb_path, library)
        authorized = authorized_stack_capture(gdb_path, library)
        timeout = timeout_detach(gdb_path, library)
        prctl_ok = authorized["target_identity"].get("prctl_returncode") == 0
        status = (
            "PASS_GDB_STACK_AND_BOUNDED_DETACH_MOCK"
            if unauthorized["attach_rejected"]
            and prctl_ok
            and authorized["all_expected_symbols_seen"]
            and authorized["target_alive_after_gdb"]
            and timeout["helper_timed_out"]
            and timeout["target_alive_after_gdb_timeout"]
            and timeout["recovery"]["recovery"] in {"SIGTERM", "SIGKILL_AFTER_SIGTERM_TIMEOUT"}
            else "FAIL_GDB_STACK_OR_BOUNDED_DETACH_MOCK"
        )
        result = {
            "schema_version": 1,
            "protocol_id": "EXP-2026-003-STAGE2D-GDB-STACK-MOCK-V1",
            "scope": "Compiled native busy-loop mock only; no OpenVINO or GPU access.",
            "compilation": compilation,
            "unauthorized_control": unauthorized,
            "authorized_stack_capture": authorized,
            "timeout_detach": timeout,
            "status": status,
            "interpretation_limits": [
                "Mock symbols are unstripped and do not predict OpenVINO stack symbol quality.",
                "A successful backtrace localizes observed frames but does not prove causality.",
                "This result does not authorize GPU execution.",
            ],
        }
        print(json.dumps(result, indent=2))
        if not status.startswith("PASS_"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
