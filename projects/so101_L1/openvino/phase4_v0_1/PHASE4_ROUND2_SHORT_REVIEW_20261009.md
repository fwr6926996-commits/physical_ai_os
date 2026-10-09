# Phase 4 Round 2 Short Review

Review ID: `P4-DK2500-R2-SHORT-REVIEW-20261009-01`

Run ID: `phase4_r2_short_20261008_01`

Protocol snapshot: `fb18053`

Authorization commit: `307c1d5`

Decision: `PASS — SHORT STAGE ONLY`

Performance admission: `NONE`

Stability authorization: `BLOCKED PENDING THERMAL DIAGNOSIS PLAN REVIEW`

## Decision boundary

The one authorized DK-2500 CPU FP32 short attempt completed its initial correctness call, ten
warmups and 100 measured full-pipeline iterations. Every normalized and postprocessed output was
finite and correct, all event pairs completed, and no watchdog, recovery or software thermal stop
occurred.

This passes the frozen short-stage hard gates only. It does not establish steady-state performance,
30-minute stability, another backend, changing-input behavior, deployment, real-time control or
physical safety.

## Independently verified evidence

- Local evidence hashes match the source target files.
- The authorization and deployed Supervisor, Worker, configuration and pre/post hashes match the
  reviewed identities.
- `latencies.csv` contains exactly 1 correctness, 10 warmup and 100 measurement rows.
- All 111 `infer_enter` and `infer_return` events match by sequence, phase and iteration.
- All outputs are finite; normalized and postprocessed correctness are 111/111.
- Maximum normalized absolute error is `2.86102294921875e-06`.
- Worker exit code is zero; stdout and stderr are empty; recovery and diagnostic records are absent.
- Independent percentile recomputation matches `worker_result.json`.

## Segmented measurement

| Boundary | Mean ms | P50 ms | P95 ms | P99 ms | Max ms |
|---|---:|---:|---:|---:|---:|
| Preprocess | 2.508 | 2.404 | 3.392 | 3.651 | 4.712 |
| Inference | 107.412 | 107.126 | 115.505 | 116.369 | 116.775 |
| Postprocess | 0.125 | 0.118 | 0.127 | 0.146 | 0.666 |
| Total | 110.053 | 109.644 | 117.995 | 118.831 | 119.227 |

The largest difference between recorded total time and the sum of the three measured segments is
approximately `0.0111 ms`.

These values describe one offline frozen-input host pipeline. They are not a robot control-period
budget or a real-time guarantee.

## Thermal and latency observation

The highest periodic package and any-sensor samples were `91 C` and `92 C`, below the frozen
`100 C` software stop. The stop therefore did not trigger and may not be retroactively replaced by
a lower threshold after the result.

However, 26 exposed throttle-counter paths increased during the run. Linux documents these
counters as transitions of core or package Thermal Status into the throttled state and notes that
they can indicate performance limited by thermal events. Package state is broadcast across logical
CPUs, so the path count is not a count of independent thermal sources:

- <https://origin.kernel.org/doc/html/latest/admin-guide/thermal/intel_thermal_throttle.html>

A five-second post-run idle control showed zero counter increments and temperature recovery. No
kernel log entry was present in the run window. This supports association with the bounded load
window, but not a cooling fault, duration or root cause.

The latency series was also non-stationary: inference mean decreased from `113.338 ms` in the first
measurement quartile to `102.323 ms` in the last. Therefore the observed percentiles are reported as
diagnostic measurements rather than a steady-state performance admission. The direction of the
trend does not support a simple claim that thermal events caused latency to rise.

## Human decision and learning result

The human owner accepted `PASS — SHORT STAGE ONLY` and routing of thermal throttling to a separate
diagnosis while keeping Stability unauthorized. The owner explained that the frozen `100 C` hard
limit was not reached, that counter growth cannot be used to retroactively fail Short or declare a
hardware fault, and that duration and cause remain unknown.

## Next gate

The one-attempt short authorization is consumed. No rerun is permitted from it.

Stability remains blocked until the open diagnosis has a reviewed evidence plan. Any future
stability attempt still requires a separate run ID, readiness review and human authorization.
