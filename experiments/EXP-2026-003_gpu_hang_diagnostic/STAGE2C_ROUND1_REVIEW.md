# EXP-2026-003 Stage 2C Round 1 Review

## Verdict

`HANG_INFER_ENTERED_NOT_RETURNED__PROC_SNAPSHOT_PARTIAL_WITHIN_BUDGET`

Round 1 reproduced the same infer-boundary failure and captured a usable partial `/proc` snapshot before recovery. The frozen stop rule closes Stage 2C immediately; Rounds 2 and 3 are prohibited.

## Verified runtime evidence

- Run ID: `stage2c_r1_20260924_02`.
- Device: Intel Arc iGPU `GPU.0`.
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`.
- Initial correctness: PASS; maximum absolute error `1.430511474609375e-06`.
- Last completed measurement iteration: 642 at 12.325821 seconds.
- All 642 recorded measurement outputs were finite and correct, with no iteration gap.
- Completed-call latency: p50 `18.371783 ms`, p95 `25.9961695 ms`, p99 `29.57330875 ms`.
- Watchdog timeout: `15.061408 s` without heartbeat.
- Worker at watchdog observation: running, `94.9%` CPU over the observation interval, RSS `708,509,696` bytes, 37 threads.
- Recovery: SIGTERM; worker exit code `-15`.

## Infer boundary

With one initial inference and ten warmups:

```text
H = last measurement iteration + 11
  = 642 + 11
  = 653

stable shared snapshot:
E = 654
R = 653
H = 653
```

Therefore the worker entered synchronous `request.infer(inputs)` call 654 and did not reach the immediate return marker within the watchdog window. This is the same boundary class observed in Stage 2B.

## `/proc` snapshot quality

- Helper status: `CAPTURED_PARTIAL`.
- Helper elapsed time: `0.004597 s`.
- Total recovery delay introduced by the wrapper: `0.029117 s`, within the 2-second budget.
- Target PID: 345279.
- Threads enumerated: 37.
- Read fields: 153.
- Unavailable fields: 75.
- Task enumeration completed without error.
- Original recovery path executed after the snapshot and returned `SIGTERM`.

The 75 unavailable fields are:

- process-level `syscall`: 1;
- thread-level `syscall`: 37;
- thread-level `stack`: 37.

They were unavailable because of permission restrictions. This is missing evidence, not evidence that no syscall or kernel stack existed.

## Observed thread state

At the single snapshot instant:

```text
main thread:       R (running), wchan=0
other 36 threads:  S (sleeping), wchan=futex_do_wait
```

All thread names were exposed as `python`, so `/proc` did not identify their OpenVINO/plugin ownership.

Together with the watchdog's approximately 94.9% CPU observation, this supports that the process remained CPU-active and that the main thread was runnable/running at the snapshot instant. It did not expose a named kernel sleep point for the main thread at that instant.

## Strongest supported conclusion

During the reproduced infer-not-returned event, one post-timeout snapshot observed the main worker thread as running with `wchan=0`, while the other 36 threads were sleeping in futex waits. The process was still CPU-active immediately before the snapshot.

This narrows the next investigation toward a bounded user-space/native execution observation rather than treating this event as proof that the main thread was sleeping in an identifiable kernel wait.

## Unsupported conclusions

- `wchan=0` does not prove the main thread was making useful progress.
- The evidence cannot distinguish active computation, polling, spinning, livelock, or a rapidly changing wait state.
- The futex-waiting secondary threads are not automatically deadlocked and do not identify an owner or missing wakeup.
- One snapshot cannot establish that the same state persisted throughout the 15-second watchdog interval.
- Unavailable syscall and stack fields cannot be interpreted as absence of a syscall or kernel stack.
- The evidence does not assign causality to OpenVINO Runtime, Intel GPU Plugin, compute runtime, i915, firmware, GPU hardware, or another component.
- The result does not qualify or readmit GPU.0.

## Evidence integrity

- `result.json`: `5cdfddeb794480745c19752b434004bbe573b8dab3452a884cee24736ed06592`
- `stage2c_result.json`: `609706ddfb9b6d71ad781d9d1df532f91d5a8a90ee7cb02666bfe4912962a8ed`
- `proc_snapshot.json`: `9c910b7135668ac4269804d6fbb7f626c294a5d248dc72acd9ce4c152bd0914b`
- `latencies.csv`: `7955dd52615e1d81e7e2e3a160ca371f37ca393eb9b64826b46e186d4ed66271`
- `supervisor_telemetry.csv`: `fe6f81a76d9b7b5f056341dd1a00cc43bd2d34ddaf5d651a8fe0e33fd9968c79`
- preflight: `f6adc550fe9de3e719b005eb835daf6192f7cc94365eeb759195c451a1ed7b56`

## Decision

- Close Stage 2C after Round 1.
- Prohibit Stage 2C Rounds 2 and 3.
- Keep GPU.0 `CLOSED_NOT_ADMITTED`.
- Keep Phase 3 `PARTIAL PASS — CPU FP32 ONLY`.
- If investigation continues, design a separately reviewed next stage that observes one user-space/native execution boundary with bounded overhead and recovery.
