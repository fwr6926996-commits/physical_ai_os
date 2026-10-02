# EXP-2026-003 Stage 2B Mock Review

## Verdict

`PASS_ALL_BOUNDARY_CLASSIFICATIONS`

No OpenVINO or GPU was initialized.

## Verified cases

- `E=13, R=12, H=12` → `HANG_INFER_ENTERED_NOT_RETURNED`.
- `E=13, R=13, H=12` → `HANG_AFTER_INFER_RETURN_BEFORE_HEARTBEAT`.
- `E=12, R=12, H=12` → `HANG_AFTER_HEARTBEAT_BEFORE_NEXT_INFER`.
- `E=14, R=12, H=12` → `BOUNDARY_EVIDENCE_INCONSISTENT`.
- Completed run with `E=R=H=14` → `NO_HANG_REPRODUCED_5M_COMPLETE`.

Each hang case used a spawned child process, wrote the shared values, was terminated by the mock supervisor, and produced two equal post-recovery snapshots.

## Wiring check

A spawned partial target received the historical supervisor-shaped arguments `(messages, duration_seconds, warmup)` while the two shared counters were pre-bound. It exited with code 0, preserved `duration_seconds=300.0` and `warmup=10`, and updated both counters to 11.

## Diff audit

The stored worker diff shows only:

- two new shared counter parameters;
- one infer sequence;
- enter/return writes around initial inference;
- enter/return writes around each warmup inference;
- enter/return writes around each measurement inference.

Model loading, compile configuration, input construction, `request.infer`, output retrieval/copy, numerical validation, Queue heartbeat, exception behavior and the historical parent supervisor remain unchanged.

## Remaining boundary

Mock success validates the observation and classification mechanism, not real GPU behavior. Shared writes may still perturb timing. Real execution remains bounded by the Stage 2B protocol and requires a fresh preflight.
