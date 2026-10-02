# EXP-2026-003 Stage 2D Feasibility Review

## Status

`SCOPED_PTRACE_ROUTE_FEASIBLE__GDB_NOT_INSTALLED__NO_GPU_EXECUTION_AUTHORIZED`

Stage 2D has not executed OpenVINO or GPU inference. This review covers only the feasibility of obtaining one bounded native stack snapshot after a future watchdog timeout.

## Question inherited from Stage 2C

Stage 2C observed the main worker thread as `R (running)` with `wchan=0` during an `HANG_INFER_ENTERED_NOT_RETURNED` event, while the other 36 threads were sleeping in futex waits.

The next unresolved question is:

> During the same infer-not-returned event, where in the user-space/native call stack is the running main thread observed?

## Local constraints

- Linux Yama `ptrace_scope=1` is enabled.
- `perf_event_paranoid=4` prevents unprivileged perf sampling.
- `gdb`, `gstack`, `pstack`, `eu-stack`, `lldb`, and `py-spy` are not installed.
- `strace` is installed and was used only as a no-GPU ptrace permission probe.
- OpenVINO Runtime and Intel GPU plugin shared libraries are stripped. A future stack may still expose library boundaries and exported symbols, but source lines and internal function names are not guaranteed.
- Available package candidate: GDB `15.1-1ubuntu1~24.04.1`.

## Host-side controlled probe

Protocol: `EXP-2026-003-STAGE2D-PTRACE-FEASIBILITY-PROBE-V1`

The ordinary target was a sleeping Python child. No OpenVINO or GPU access occurred.

### Unauthorized control

- Target PID: 346857.
- No `PR_SET_PTRACER` authorization.
- `strace` attach failed with `PTRACE_SEIZE: Operation not permitted`.
- Target remained alive.

### Scoped authorization

- Target PID: 346862.
- Target authorized only supervisor PID 346853 with `PR_SET_PTRACER`.
- `prctl` returned 0 with no errno.
- A `strace` process launched as a supervisor descendant attached and detached successfully.
- The target remained alive after detach.

## Supported conclusion

On the real host, a worker can retain global `ptrace_scope=1` while granting its supervisor and the supervisor's descendants permission to attach for that worker's lifetime. This makes a bounded post-timeout GDB helper technically plausible without changing the system-wide ptrace policy.

## Unsupported conclusions

- The probe does not show that GDB is installed or functional.
- It does not show that GDB can unwind the OpenVINO worker's 37 threads.
- It does not establish stack quality, symbol availability, attach latency, or detach latency.
- It does not establish that a GDB stack will identify a root cause.
- It does not authorize a GPU run or a system package installation.

## Recommended route

1. Obtain human approval to install the distribution GDB package.
2. On an ordinary no-GPU native mock process, validate:
   - unauthorized attach rejection;
   - scoped authorization;
   - all-thread backtrace capture;
   - hard helper timeout;
   - detach/target-liveness behavior;
   - original recovery execution after success, partial output, timeout, or failure.
3. Review actual stack quality before drafting the Stage 2D GPU protocol.
4. If stack quality is useful, freeze one bounded post-timeout observation mechanism and request separate GPU execution approval.

Do not change `ptrace_scope`, enable unrestricted ptracing, use continuous profiling, or combine GDB with driver/configuration changes.
