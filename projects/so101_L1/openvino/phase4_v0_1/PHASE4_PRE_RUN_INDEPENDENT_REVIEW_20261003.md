# Phase 4 Pre-Run Independent Review

Review ID: `P4-DK2500-PRE-RUN-REVIEW-20261003-01`

Date: `2026-10-03`

Reviewed protocol: `P4-DK2500-CPU-FP32-001`

Result: `PROTOCOL_FREEZE_ACCEPTABLE — EXECUTION NOT AUTHORIZED`

## Review question

Is the accepted Phase 4 DK-2500 CPU FP32 qualification protocol sufficiently explicit, bounded
and evidence-driven to freeze without starting model execution?

## Evidence reviewed

- `PHASE4_CPU_FP32_QUALIFICATION_PROTOCOL.md`
- `DK2500_HARDWARE_SOFTWARE_TRUTH_20261003.md`
- `VM1_VERSION_DRIFT_REVIEW_20261003.md`
- `evidence/phase4_0_truth/dk2500_truth_20261003.json`
- `evidence/phase4_0_truth/policy_package_transfer_verification_20261003.json`
- Phase 3 worker and supervisor implementations
- read-only DK-2500 Python dependency, sensor and writable-path probes

## Confirmed protocol properties

1. Scope is restricted to explicit DK-2500 CPU FP32 offline synchronous inference.
2. Policy Package and frozen input/output identity are established through target-side hashes.
3. OpenVINO 2026.2.1 drift is accepted as the target baseline rather than silently normalized.
4. The strict no-touch SSH route separates remote execution from unprepared board handling.
5. Correctness precedes performance and is checked on every stability inference.
6. Thirty minutes, ten warmups, 100 short-run iterations, five-second telemetry and 60-second
   windows are precommitted.
7. A 15-second infer watchdog, 180-second startup boundary and SIGTERM-to-SIGKILL recovery are
   bounded.
8. Each stage is limited to one attempt per explicit human authorization, with no automatic retry.
9. Latency, memory, frequency, utilization and throttle deltas are diagnostic-only because no
   end-to-end control budget or validated resource limit exists.
10. The 100°C software stop retains margin below the exposed 105°C core critical limit.

## Target feasibility checks

- Python: `/usr/bin/python3`, 3.12.3.
- OpenVINO: `2026.2.1-21919-ede283a88e3-releases/2026/2`.
- NumPy: `1.26.4`.
- psutil: `5.9.8`; `acpitz` and `coretemp` readings are available, including `Package id 0`.
- PyTorch: `2.12.1+cu130`; required only to deserialize the frozen `.pt` reference tensors.
- Target artifact/evidence parent is writable.
- CPU core/package throttle counters are readable. Absolute historical counts are nonzero, so
  only immediate pre-run to post-run deltas may be attributed to a qualification run.
- RAPL powercap evidence is unavailable. The adapter rating must not be reported as workload power.

## Implementation gap found

The Phase 3 harness cannot be reused unchanged:

- its supervisor hard-codes `GPU.0`;
- worker and supervisor paths point to Phase 3 directories;
- evidence is written under Phase 3;
- the target package lives in a separate DK-2500 artifact directory;
- the accepted 100°C stop, frequency capture and throttle-counter deltas are not implemented;
- the Phase 4 frozen configuration and target identity are not enforced as one preflight contract.

This is an implementation blocker, not a reason to change the accepted protocol parameters.

## Required work before execution authorization

1. Implement a Phase 4 CPU worker and external supervisor without modifying the frozen protocol.
2. Make package/evidence paths explicit and reject unexpected target identity, versions or hashes.
3. Implement streamed progress, external telemetry, thermal stop and throttle-delta capture.
4. Validate success, timeout, incorrect-output, thermal-stop, partial-evidence and recovery paths
   with mocks that do not access OpenVINO or the Policy Package.
5. Run a no-model preflight on DK-2500 and record script hashes.
6. Perform a final execution-readiness review and obtain separate human start authorization.

## Review decision

The protocol parameters may be frozen as
`FROZEN_APPROVED_EXECUTION_NOT_AUTHORIZED`. No compile, model load, correctness run, benchmark or
stability run is authorized by this review.

Any change to a frozen input, hash, device, precision, runtime version, duration, correctness
threshold, timeout, attempt limit, thermal stop or recovery rule requires a dated deviation review
and normally a new protocol version.
