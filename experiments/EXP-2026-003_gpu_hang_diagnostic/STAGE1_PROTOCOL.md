# EXP-2026-003 GPU Hang Diagnostic — Stage 1 Protocol

Protocol ID: `EXP-2026-003-STAGE1-GPU-CALL-BOUNDARY-V1`

Status: `EXECUTED_ONCE__NO_HANG_REPRODUCED__CLOSED`

Classification: `EXPLORATORY_DIAGNOSTIC`

Owner and first-run operator: human

## Question and decision

- Question: When the known GPU.0 loss of progress recurs, what is the last returned inference call, what is the first entered-but-not-returned call, and what Python/process/kernel evidence exists before recovery?
- Decision supported: Whether the next diagnostic should focus on the Python harness boundary, OpenVINO/native execution boundary, kernel/driver evidence, or a model/configuration A/B.
- Claims not supported: This run cannot by itself prove an OpenVINO Runtime, Intel GPU Plugin, i915 driver or GPU hardware root cause. It cannot readmit GPU.0.

## Frozen artifacts and environment

- Host: Lenovo ThinkBook 16 G7+ IAH, Intel Core Ultra 7 255H.
- GPU target: explicit Intel GPU.0 with identity guard; NVIDIA GPU is rejected.
- Kernel driver currently observed: `i915` for Intel Arrow Lake-P graphics.
- OpenVINO environment: `/home/lucas/intel_ws/openvino_env/bin/python`.
- OpenVINO baseline: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`.
- Model and references: frozen Phase 3 V2.9 Policy Package.
- Precision and performance hint: FP32 and LATENCY.
- No driver, kernel, firmware, power-mode or debug-key change.

## Experimental design

- Baseline: the previously failing isolated-worker GPU.0 synchronous inference path.
- Single changed variable: observability only. Add explicit stage/inference enter and return events, Python faulthandler output, `/proc` snapshot and kernel journal capture.
- Warmup: 10 iterations.
- Maximum measurement duration: 180 seconds.
- Stall timeout: 15 seconds without a worker event.
- Repetitions: exactly one Stage 1 run.
- Recovery: request a Python traceback with SIGUSR1, capture process state, then terminate the exact child with SIGTERM; use SIGKILL only if SIGTERM fails.

## Evidence contract

- `events.jsonl`: supervisor-observed ordered events.
- `python_stack.txt`: best-effort Python stack requested before recovery.
- `proc_snapshot.json`: best-effort process/thread state at timeout.
- `kernel_journal.txt`: kernel journal covering the run window.
- `result.json`: frozen configuration, artifact hashes, last-good/first-missing boundary and interpretation limits.

## PASS conditions for the diagnostic harness

Stage 1 is a diagnostic run, not a GPU qualification run.

- If a stall occurs: the supervisor records an entered inference without a matching return, captures best-effort diagnostic evidence and recovers the worker within the bounded policy.
- If no stall occurs: the run completes once and is recorded as `NO_HANG_REPRODUCED`; it is not repeated automatically and does not readmit GPU.0.
- A worker exception or startup failure is preserved as a distinct result, not called a hang.

## Stop policy

- Maximum formal attempts under this protocol: 1.
- Do not rerun merely because the hang does not reproduce.
- Do not change OpenVINO, driver, kernel, model, precision or performance hint under this protocol.
- Any A/B comparison requires Stage 2 with one explicitly changed variable.
- Do not enable Intel Compute Runtime internal debug keys in Stage 1.

## Pre-run checklist

- [x] Human can explain `infer_enter` versus `infer_return` and its interpretation limit.
- [x] GPU.0 appears in the ordinary host terminal as `Intel(R) Arc(TM) Graphics (iGPU)`; GPU.1 is `NVIDIA GeForce RTX 5060 Laptop GPU (dGPU)` and is outside this run.
- [x] Model and reference artifacts exist; their SHA-256 hashes were verified before the run and will also be captured by the script.
- [ ] No other GPU benchmark or training job is intentionally running.
- [x] Human accepts one bounded 180-second run plus a 15-second recovery window.

## Governing boundary

Phase 3 remains closed as `PARTIAL PASS — CPU FP32 ONLY`. This experiment investigates an unresolved cause; it does not modify the active runtime or start Phase 4.

## Execution record

- Run ID: `stage1_gpu0_call_boundary_20260924_01`
- Result: `NO_HANG_REPRODUCED_SINGLE_RUN_COMPLETE`
- Measurement: 180.013675 seconds, 9,218 measurement iterations.
- Total inference calls: 9,229 entered and 9,229 returned.
- Correctness: zero incorrect measurement heartbeats; maximum absolute error `1.430511474609375e-06`.
- Recovery evidence: not captured because no watchdog timeout occurred.
- Kernel evidence: no GPU/i915 error was observed in the captured run window.
- Repetition policy applied: no automatic rerun.

### Post-run comparability audit

The frozen statement "single changed variable: observability only" was too strong. Compared with the historical isolated stability harness, Stage 1 also changed Queue communication to Pipe communication, emitted two additional events around every inference, omitted periodic parent telemetry, checked warmup correctness, and used a 180-second duration. These changes can perturb timing. The result is valid for this Stage 1 configuration, but it is not a strict single-variable A/B against either historical failure.
