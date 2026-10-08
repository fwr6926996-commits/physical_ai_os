# Phase 4 Short Post-Move Revalidation

Review ID: `P4-DK2500-SHORT-POSTMOVE-20261008-01`

Date: `2026-10-08`

Protocol: `P4-DK2500-CPU-FP32-001` at snapshot `fb18053`

Implementation commit: `6af41fd`

Result: `SHORT_STAGE_READY_FOR_HUMAN_DECISION — EXECUTION NOT AUTHORIZED`

## Why this revalidation exists

The DK-2500 was powered down, physically moved and reconnected after the 2026-10-03 short-stage
readiness review. The earlier correctness result and implementation validation remain historical
evidence, but connectivity, execution state and the observable idle baseline were rechecked before
presenting a new execution decision.

No model was read, compiled or executed during this revalidation.

## Observed state

- Direct Ethernet SSH was restored on `enp1s0` at `192.168.77.2/24`.
- The target identity remained `hepintelpc` on Linux `6.17.0-35-generic`.
- No Phase 4 Worker or Supervisor was observed, and no short authorization or short run directory
  existed.
- The repeated no-model preflight passed. CPU identity, OpenVINO version, six Policy Package
  artifacts, five deployed implementation hashes, dependencies and sensor interfaces matched the
  frozen contract.
- One point sampled package/core temperature at `68/69 C` while the one-second CPU sample was zero.
  It is retained rather than discarded. A subsequent 30-second trend at five-second intervals was
  `43, 35, 34, 34, 34, 35, 35 C` for the package at approximately `0.01` one-minute load.

The bounded trend does not show sustained idle overheating. It also does not qualify loaded thermal
behavior; start/periodic/final telemetry and the frozen `100 C` hard stop remain mandatory during
the short stage.

## Evidence

- `evidence/phase4_0_harness/no_model_preflight_short_postmove_20261008_01.json`
- `evidence/phase4_0_harness/postmove_idle_revalidation_20261008_01.json`
- The original readiness evidence listed in `PHASE4_SHORT_EXECUTION_READINESS_REVIEW_20261003.md`

## Decision boundary

The physical move introduced no observed identity, artifact or implementation drift and no
sustained idle thermal blocker. The short stage may therefore be presented again for human
authorization.

The earlier unexecuted candidate run ID `phase4_r2_short_20261003_01` is superseded before
authorization by `phase4_r2_short_20261008_01` so that the run identity reflects this post-move
decision point. No authorization file has been created. Exactly one attempt, no automatic retry,
and no stability execution would be authorized by a future short-stage decision.

This review does not change the meaning of a successful short result: it would provide offline
frozen-input correctness, segmented latency and bounded target telemetry evidence only. It would
not establish 30-minute stability, real-time control performance or robot safety.
