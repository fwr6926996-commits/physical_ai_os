# EXP-2026-003 Stage 2C Closure

## Status

`CLOSED AFTER ROUND 1 — MAIN THREAD RUNNING AT SINGLE POST-TIMEOUT SNAPSHOT`

## Result

Stage 2C reproduced the intermittent failure in its first bounded attempt. The infer boundary remained stable and consistent: `H=653`, `R=653`, `E=654`.

The bounded pre-recovery `/proc` helper completed in approximately 4.6 milliseconds and added approximately 29.1 milliseconds before the original SIGTERM recovery. It captured all 37 threads but could not read syscall or stack fields because of permissions.

At the snapshot instant, the main thread was `R (running)` with `wchan=0`; the remaining 36 threads were `S (sleeping)` at `futex_do_wait`. The watchdog observation immediately beforehand measured approximately 94.9% process CPU.

## Learning

The snapshot does not show the main thread sleeping at a named kernel wait point. It instead shows a CPU-active process with a runnable/running main thread at one instant during the infer-not-returned event.

This is compatible with several different internal behaviors, including useful native computation, polling, spinning, livelock, or a changing wait state. The single snapshot cannot distinguish them. The 36 futex waits also cannot be labeled deadlock without ownership, stack, timing, and wakeup evidence.

The experiment demonstrates the evidence ladder:

```text
infer entered but did not return
→ process still CPU-active
→ main thread observed running, not in a named kernel sleep
→ internal user-space/native location still unknown
```

Each arrow narrows the observation boundary; none proves the next component-level cause.

## Stop decision

The protocol's success condition was met: a consistent `HANG_INFER_ENTERED_NOT_RETURNED` event and a usable partial `/proc` snapshot were obtained together. Rounds 2 and 3 are therefore prohibited.

## Route

If investigation continues, the next question should be limited to:

> During the same infer-not-returned event, where in the user-space/native call stack is the running main thread observed?

A future stage must choose exactly one bounded mechanism, such as a one-shot native stack sample or an official OpenVINO/Intel diagnostic facility. It must first resolve required permissions, test recovery on a non-GPU mock, define an observation-time budget, and receive separate human approval before GPU execution.

Do not combine stack sampling, syscall tracing, driver changes, continuous profiling, or multiple configuration changes in one stage.

## Unchanged engineering decision

- GPU.0 remains `CLOSED_NOT_ADMITTED`.
- CPU FP32 remains the only admitted backend.
- Phase 3 remains `PARTIAL PASS — CPU FP32 ONLY`.
- Phase 4 remains not started.
