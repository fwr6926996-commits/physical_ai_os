# EXP-2026-003 Stage 2D Implementation Review

## Verdict

`IMPLEMENTED_AND_MOCK_VERIFIED__READY_FOR_FINAL_HUMAN_EXECUTION_REVIEW__NOT_EXECUTED_ON_GPU`

## Production mechanism

- The historical Phase 3 supervisor remains unchanged on disk.
- The frozen Stage 2B infer enter/return counters remain unchanged.
- The Stage 2D worker adds one startup `PR_SET_PTRACER(supervisor_pid)` call and records its return code, errno and authorized PID in ready evidence.
- The infer hot path, model, input, FP32 configuration, LATENCY hint, correctness, heartbeat and duration remain unchanged.
- On watchdog recovery only, the wrapper launches one GDB process with a 2-second hard budget, saves `thread apply all bt 40`, then always invokes the original SIGTERM/SIGKILL recovery in a `finally` path.
- Stage 2C `/proc` capture is not combined with Stage 2D.

## Final host integration mock

Status: `PASS_STAGE2D_PRODUCTION_WRAPPER_INTEGRATION_MOCK`

- Complete stack: `GDB_STACK_COMPLETE_MAIN_THREAD_IDENTIFIED`; GDB delay `0.125253 s`; target returned to running; SIGTERM succeeded.
- Unauthorized attach: `GDB_ATTACH_FAILED`; delay `0.047797 s`; target remained running; SIGTERM succeeded.
- Synthetic partial stack: `GDB_STACK_PARTIAL_MAIN_THREAD_IDENTIFIED`; delay `0.000845 s`; SIGTERM succeeded.
- Forced GDB timeout: `GDB_HELPER_TIMEOUT`; delay `1.004652 s`; target returned to running; SIGTERM succeeded.
- No-hang classification: `GDB_NOT_TRIGGERED_NO_HANG`.

## Fail-closed evidence checks

- A stack cannot be classified from transient in-memory output when the raw evidence file failed to save.
- A ready worker must record successful authorization with zero errno and an authorized PID exactly equal to the current supervisor PID; otherwise the result is `GDB_AUTHORIZATION_INVALID`.
- Helper launch errors, nonzero return codes, timeout, post-helper target state and recovery result are preserved separately.

## Frozen hashes

- Historical baseline: `4fae4ce71896db4eafe01932b89076c46d11f401f6f64ad2fa3b78ae650cbab7`
- Stage 2D worker: `87b7f46af3913297aa3eeab8a30940980a41e2278f806e60ed82fb12b34c9eef`
- Stage 2D runner: `62eeacf0c1b188045586a7e108da54c2ad29a1fc4e9ad9ccdfebae8d7ee2901f`
- Stage 2D preflight: `de79ef2bd66084a9192a8bb89ece5541e67b5cac8e0e68a4064d6c1cb33d6eb4`
- `/usr/bin/gdb`: `3832cc070ae1716e322105d3b39fb398695e5f031c9d39224cf227a8c2b889f6`
- Production-wrapper mock: `568c7cbcefb571b97db58d781db7a7de7cdd0776668ec55febaf691965a3b82c`

## Remaining limits

- Real OpenVINO and Intel GPU libraries are stripped; the real stack may contain module names and addresses without internal function names.
- GDB briefly stops all target threads and changes recovery timing.
- One backtrace shows observed execution location, not causality or persistence over the full watchdog interval.
- A successful mock does not predict whether the intermittent GPU event will recur.
- No result from this stage is GPU admission evidence.

## Execution gate

Real execution requires a new host-side preflight no more than 30 minutes old and explicit final human acceptance of the 2-second GDB budget and stop rules. Rounds 2 and 3 are allowed only after a preceding five-minute no-hang result; any usable hang stack, authorization error, attach failure, helper timeout, stopped target, recovery anomaly or boundary inconsistency closes further execution pending Review.
