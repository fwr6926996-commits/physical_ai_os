# EXP-2026-003 Stage 1 Review

## Status

`COMPLETE — NO HANG REPRODUCED IN THE SINGLE FROZEN RUN`

This is an exploratory diagnostic result. GPU.0 remains excluded from the active backend, and Phase 3 remains `PARTIAL PASS — CPU FP32 ONLY`.

## Verified evidence

- Explicit device: `GPU.0`, identified as `Intel(R) Arc(TM) Graphics (iGPU)`.
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`.
- Kernel: `Linux 7.0.0-31-generic`.
- Frozen model and reference hashes matched the pre-run artifacts.
- Model compilation returned in 973.79803 ms.
- 9,229 `infer_enter` events and 9,229 matching `infer_return` events were recorded.
- The 9,218 measurement iterations all reported `correct: true`.
- Maximum observed absolute error: `1.430511474609375e-06`.
- Measurement duration: 180.013675 seconds.
- Inference latency in all 9,229 calls: minimum 17.713431 ms, median 18.193235 ms, p95 27.643517 ms, p99 35.196292 ms, maximum 89.497361 ms, mean 19.456706 ms.
- Worker exited normally with exit code 0.
- No relevant GPU/i915 error appeared in the captured kernel journal window. The single journal line was an unrelated Microsoft Edge AppArmor audit.

## Expected absent evidence

- `first_missing_event` is `null` because every entered inference returned.
- `proc_snapshot.json` says `NOT_CAPTURED_NO_WATCHDOG_TIMEOUT` because the watchdog did not fire.
- `python_stack.txt` is empty because SIGUSR1 stack capture is only requested at watchdog timeout.
- `recovery` is `null` because the worker did not require termination.

These are expected consequences of a clean run, not missing required evidence.

## What this run supports

- The exact Stage 1 configuration completed one bounded 180-second GPU.0 FP32 run.
- All outputs observed during this run met the frozen numerical comparison.
- The enter/return harness preserves enough information to identify a future entered-but-not-returned inference if a stall recurs.
- The historical failure is intermittent under the evidence currently available; it did not reproduce in this attempt.

## What this run does not support

- It does not invalidate the two previous stability failures at about 52 and 94 seconds.
- It does not establish 30-minute stability.
- It does not readmit GPU.0 for deployment.
- It does not locate a root cause because no stalled state was captured.
- Absence of a kernel error in this window does not prove that the driver or hardware is fault-free.

## Design–reality gap

The Stage 1 protocol described observability as the only changed variable, but the implementation also changed Queue communication to Pipe communication, added two messages per inference, omitted periodic parent telemetry, checked warmup outputs, and used a shorter bounded duration. These changes may perturb scheduling or timing. Therefore this run is not a strict single-variable comparison with the historical failing harness.

The external GPU workload state was not captured as structured pre-run evidence. It remains an uncontrolled contextual factor even though the operator was instructed to close intentional GPU benchmark, training, and inference jobs.

## Route

Route the unresolved root-cause question to a future `Experiment`, not to an implementation change or architecture rule.

Before any further GPU run, define a Stage 2 protocol that:

1. states one decision to be supported;
2. preserves the historical inference path as one exact control;
3. changes only one factor per comparison arm;
4. records relevant pre-run workload and environment state;
5. sets a bounded repetition and stop policy in advance;
6. treats non-reproduction as censored evidence, not as a pass.

Stage 2 is not authorized or executed by this review.

## Learning checkpoint

The strongest valid conclusion is: **this configuration completed once; the known intermittent GPU.0 loss of progress was not observed, and its cause remains unknown.**
