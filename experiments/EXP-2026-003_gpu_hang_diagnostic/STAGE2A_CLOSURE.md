# EXP-2026-003 Stage 2A Closure

## Status

`CLOSED — INTERMITTENT HISTORICAL HANG SYMPTOM REPRODUCED`

## Sequence

- Round 1: five minutes complete; no hang reproduced.
- Round 2: five minutes complete; no hang reproduced.
- Round 3: hang reproduced after 84.680417 seconds; watchdog recovered the worker.
- Frozen maximum reached through the failure stop rule; Round 4 is prohibited.

## Strongest supported conclusion

Under the current recorded environment, the unchanged historical GPU.0 FP32 isolated-worker path can still intermittently stop producing post-inference heartbeats. The symptom reproduced without correctness degradation, rising latency, abnormal temperature, or obvious RSS growth in the completed samples.

## What changed in our understanding

- Stage 1 non-reproduction did not indicate that the problem disappeared.
- The historical failure path remains reproducible in the current software versions.
- High pre-hang latency is not a necessary condition: Round 3 hung with the same low-latency distribution as the two successful current rounds.
- Short successful runs are especially weak evidence for an intermittent fault.

## What remains unknown

- Whether the worker stopped inside `request.infer(inputs)` or in output retrieval, correctness processing, or Queue heartbeat publication.
- Which native layer, if any, is causal.
- Which hidden environmental or timing condition changes the outcome between runs.
- The probability of recurrence; one failure in three current trials is not a reliable rate estimate.

## Route

Route to Stage 2B `Experiment`: compare the reproduced historical control path with a minimally instrumented path that records entry to and return from `request.infer` using one low-perturbation shared-state mechanism. Freeze the A/B sequence, repetitions and stop policy before implementation or execution.

Do not route this evidence to GPU admission, Phase 4, a driver change, or an architecture-level root-cause claim.
