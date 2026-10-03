# Phase 4 Short Execution Readiness Review

Review ID: `P4-DK2500-SHORT-READINESS-20261003-01`

Date: `2026-10-03`

Frozen protocol snapshot: `fb18053`

Implementation commit: `6af41fd`

Result: `SHORT_STAGE_READY_FOR_HUMAN_DECISION — EXECUTION NOT AUTHORIZED`

## Reviewed scope

This review covers only the proposed short-stage implementation for the recorded DK-2500 CPU
FP32 identity:

- one initial correctness inference;
- 10 full-pipeline warmups;
- 100 measured full-pipeline iterations;
- portable frozen preprocessing, explicit CPU FP32 OpenVINO inference and portable frozen
  postprocessing;
- normalized-output correctness on every inference;
- raw per-iteration segmented timings and external telemetry;
- the existing watchdog, thermal stop, one-attempt rule and bounded recovery.

It does not authorize execution, the 30-minute stability stage, robot motion, real-time admission or
physical-safety claims.

## Pre/post boundary and equivalence

The DK-2500 baseline does not include the LeRobot package. Installing a new framework into the
qualification environment merely to time two simple transforms would introduce avoidable software
drift. The short harness therefore implements the frozen ACT processor behavior directly in NumPy:

1. clone the frozen raw state and wrist image;
2. add the batch dimension;
3. apply the frozen LeRobot `MEAN_STD` state/image normalization;
4. run synchronous OpenVINO inference;
5. copy the normalized output and apply the frozen action mean/std unnormalization.

`prepost_equivalence_20261003_01.json` compares the portable path against both the original saved
LeRobot processors and the frozen reference tensors. All six comparisons are exact with zero
maximum and mean absolute difference. The source processor files, portable implementation and
config are hash-bound in that evidence.

The normalized action output remains the frozen qualification correctness boundary. The
postprocessed action comparison is recorded as diagnostic evidence; it is not silently introduced
as a new pass/fail threshold after the protocol freeze.

## Measurement contract

For every short-stage call, the Worker records:

- `preprocess_ms`: raw tensor clone, batch and normalization;
- `inference_ms`: only the synchronous `request.infer()` call;
- `postprocess_ms`: output copy and action unnormalization;
- `total_ms`: the measured preprocess → inference → postprocess path;
- normalized finite/correctness result and maximum absolute error;
- diagnostic postprocessed correctness and maximum absolute error.

P50/P95/P99 are computed independently for all four timing boundaries from the 100 measured rows.
These are offline frozen-input host-pipeline measurements, not robot control-loop latency.

## Telemetry and throttle follow-up

The frozen periodic telemetry interval remains 5 seconds. The Supervisor now also requires a final
snapshot after Worker exit, so even a short run preserves at least start and final host state, plus
any 5-second periodic samples reached during execution. The final snapshot independently enforces
the frozen `100°C` hard limit.

Throttle counters are captured before and after the stage, with the number of incrementing paths
reported. The Round 1 counter increments remain unexplained and diagnostic-only under the frozen
protocol. This short run can characterize whether increments recur alongside timing and thermal
samples; it cannot by itself identify their hardware/firmware cause.

## Verification evidence

- `short_harness_mock_validation_20261003.json`: 10/10 local unit and control-flow tests passed.
- `prepost_equivalence_20261003_01.json`: 6/6 exact LeRobot/portable/reference comparisons passed.
- `no_model_preflight_short_20261003_01.json`: target OpenVINO/CPU identity, six artifacts,
  dependencies, sensors, paths and all five deployed implementation hashes passed.
- The target preflight explicitly records `execution_authorized=false` and did not call
  `read_model`, `compile_model` or `infer()`.

## Stop and evidence rules

- Proposed run ID: `phase4_r2_short_20261003_01`.
- Exactly one attempt after a separate run-specific human authorization; no automatic retry.
- Any identity/hash mismatch, incorrect or non-finite normalized output, process failure, watchdog
  timeout or observed `>=100°C` temperature fails and stops the stage.
- Partial evidence is preserved before Supervisor `SIGTERM`, followed by `SIGKILL` only after the
  frozen 5-second grace period.
- The consumed Round 1 authorization cannot be reused.

## Decision

The short-stage implementation is ready to be presented to the human owner for a one-attempt
authorization decision. This review does not create an authorization file and does not start the
stage. Stability remains blocked regardless of the human short-stage decision.
