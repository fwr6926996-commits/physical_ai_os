# EXP-2026-003 Stage 2D public evidence bundle

This bundle supports a public Intel compute-runtime issue about an intermittent
non-returning synchronous OpenVINO GPU inference on Intel Arrow Lake-P.

Run: `stage2d_r1_20260930_01`  
Captured: 2026-09-30  
Scope: diagnostic evidence only; not GPU qualification or admission evidence

## Primary evidence

- `result.json`: test configuration, correctness, latency, watchdog and host
  telemetry summary.
- `stage2d_result.json`: stable infer enter/return boundary, bounded GDB control
  result and evidence hashes.
- `gdb_all_threads.txt`: raw all-thread stopped-time GDB backtrace.
- `latencies.csv`: every completed measurement inference before the hang.
- `supervisor_telemetry.csv`: bounded host telemetry.
- `stage2d_r1_20260930_01_preflight.json`: read-only pre-run environment and
  artifact identity.

## Reproducer and diagnostic control

- `stage2d_worker.py`: frozen OpenVINO worker plus scoped ptrace authorization.
- `run_stage2d_gdb_stack.py`: bounded supervisor, watchdog, one GDB snapshot and
  recovery.
- `capture_stage2d_preflight.py`: read-only preflight capture.
- `STAGE2D_FROZEN_MANIFEST.json`: frozen implementation hashes.
- `STAGE2D_ROUND1_REVIEW.md`: evidence interpretation and explicit limits.

The worker imports the Phase 3 model package from the parent project. The model
artifacts are identified by SHA-256 in the results but are not included in this
initial bundle to keep the attachment small. They can be provided if requested.

## Evidence boundary

The capture proves that call 12,397 was entered and had not returned by the
watchdog deadline. At one stopped-time observation, the main thread had its top
nine unresolved frames in stripped `libigdrcl.so`, reached through the Intel
OpenVINO GPU Plugin and OpenVINO Runtime. It does not prove which component
originated the failure or distinguish computation, polling, spinning, livelock,
delayed GPU completion, or response to an earlier fault.
