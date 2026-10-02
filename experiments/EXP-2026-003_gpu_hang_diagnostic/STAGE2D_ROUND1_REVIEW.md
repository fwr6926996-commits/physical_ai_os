# EXP-2026-003 Stage 2D Round 1 Review

## Verdict

`HANG_INFER_ENTERED_NOT_RETURNED__GDB_STACK_COMPLETE_MAIN_THREAD_IDENTIFIED`

Round 1 reproduced the same infer-boundary failure and captured a complete bounded native stack with the main Linux thread identified. The stop rule closes Stage 2D immediately; Rounds 2 and 3 are prohibited.

## Verified runtime evidence

- Run ID: `stage2d_r1_20260930_01`.
- Device: Intel Arc iGPU `GPU.0`.
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`.
- Initial correctness: PASS; maximum absolute error `1.430511474609375e-06`.
- Last completed measurement iteration: 12,385 at `233.663175 s`.
- All 12,385 recorded measurement outputs were finite and correct, with no iteration gap.
- Completed-call latency: p50 `18.153212 ms`, p95 `24.782856 ms`, p99 `29.5417714 ms`.
- Watchdog timeout: `15.074147 s` without heartbeat.
- Worker at watchdog observation: running, `99.9%` CPU, RSS `681,037,824` bytes, 37 threads.
- Recovery: SIGTERM; worker exit code `-15`.

## Infer boundary

With one initial inference and ten warmups:

```text
H = 12,385 + 11 = 12,396
E = 12,397
R = 12,396
H = 12,396
```

Both shared snapshots were stable and identical. The worker entered synchronous `request.infer(inputs)` call 12,397 and did not reach the immediate return marker within the watchdog window.

## Authorization and GDB mechanism

- Worker authorized supervisor PID 430782.
- `PR_SET_PTRACER` return code: 0; errno: 0.
- Runner verified that the authorized PID exactly matched its own PID.
- GDB target PID: 430808.
- GDB return code: 0.
- Raw output saved: 54,537 bytes.
- GDB delay before recovery: `1.047426 s`, within the 2-second budget.
- Target state after detach: `R (running)`.
- Original recovery completed with SIGTERM.
- All 37 threads were present in the raw stack.

## Main-thread native stack

Linux main thread: LWP 430808.

The observed call chain, from Python toward the currently executing native frames, was:

```text
Python evaluation
→ _pyopenvino Python binding
→ ov::InferRequest::infer()
→ ov::IAsyncInferRequest::infer()
→ OpenVINO Runtime execution
→ Intel GPU Plugin (libopenvino_intel_gpu_plugin.so)
→ Intel OpenCL Compute Runtime (libigdrcl.so)
→ nine unresolved libigdrcl.so frames at the top of the stack
```

Frame ranges:

- frames 0–8: `/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so`;
- frames 9–19: `libopenvino_intel_gpu_plugin.so`;
- frames 20–25: `libopenvino.so.2631`, including `ov::IAsyncInferRequest::infer()` and `ov::InferRequest::infer()`;
- frames 26–27: `_pyopenvino`;
- remaining frames: Python and libc startup.

The other 36 threads had a futex wait at frame 0. Some deeper secondary-thread frames also entered `libigdrcl.so`, but their waiting state does not by itself establish deadlock or ownership.

## Actual OpenCL runtime identity

The stack revealed a Design–Reality Gap: the observed backend path used Intel OpenCL Compute Runtime, not the Level Zero library prioritized in the preflight inventory.

- Path: `/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so`.
- Package: `intel-opencl-icd`.
- Package version: `25.18.33578.77-1146~24.04` (`amd64`).
- Build ID: `58ccca242c62c0629c06940ee3d7b8a40b298e35`.
- SHA-256: `d43af828e1acfcce4a2c042167ecacb270e9356fa55a3a557f18cd55b79540da`.
- Binary state: stripped.

## Strongest supported conclusion

During this reproduced infer-not-returned event, the main thread was observed executing inside a multi-frame Intel OpenCL Compute Runtime (`libigdrcl.so`) call chain reached through the Intel OpenVINO GPU Plugin and OpenVINO Runtime. The process was consuming approximately one CPU core at the watchdog observation.

This narrows the unexplained execution boundary from generic synchronous `infer` to the GPU Plugin → Intel OpenCL Compute Runtime path, with the stopped-time top frames inside `libigdrcl.so`.

## Unsupported conclusions

- The stack does not prove `libigdrcl.so` contains the originating bug.
- It does not distinguish useful computation, polling, spinning, livelock, delayed GPU completion, or response to an earlier fault.
- It does not prove the main thread stayed in the same frames throughout the 15-second watchdog interval.
- The 36 futex-waiting threads are not automatically deadlocked.
- Stripped `??` frames cannot be assigned function names from this evidence alone.
- Absolute runtime addresses cannot be treated as stable module offsets because this run did not save the GDB shared-library mapping/base addresses.
- The result does not qualify or readmit GPU.0.

## Evidence integrity

- `result.json`: `fec9b0d3341399542c660d0a1c5c8333683e463eddd2753fe14f25d21b8ff525`
- `stage2d_result.json`: `13626d2f9d0e9f255a1da3d7b3a3612d84497fb6b167d0d8dd7df77d28dd5444`
- `gdb_all_threads.txt`: `03f492adb1791f09ff31c95da745de3fce6cdd62840f123ba158965811531843`
- `latencies.csv`: `b5930efef818bda5062be4a38675738448f7f2865af0a02d0ac6f7af3fc17dd1`
- `supervisor_telemetry.csv`: `f5c3d555fe3a473d5cba7bbd4c73e682dd18c8521254a0a470f25322e91207d9`
- preflight: `98460061fcd96f94c0b80a9c1fed401144922d9782769ae6ff5b2b4d539f8ec4`

## Decision

- Close Stage 2D after Round 1.
- Prohibit Stage 2D Rounds 2 and 3.
- Keep GPU.0 `CLOSED_NOT_ADMITTED`.
- Keep Phase 3 `PARTIAL PASS — CPU FP32 ONLY`.
- Route the newly identified OpenCL Runtime boundary to research before designing another GPU experiment.
