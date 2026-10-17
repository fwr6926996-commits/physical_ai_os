# Phase 4 Thermal D3-LOAD No-Target Mock Protocol

Protocol ID: `P4-DK2500-THERMAL-D3-LOAD-MOCK-001`

Protocol version: `0.1`

Classification: `IMPLEMENTATION VALIDATION — ARTIFICIAL INPUT AND LOCAL CHILD PROCESSES`

Status: `FROZEN FOR NO-TARGET MOCK; TARGET EXECUTION NOT AUTHORIZED`

## Scope

Validate the accepted D3 classification, CPU worker lifecycle and protected target gate without
accessing DK-2500. Artificial JSONL validates calculation and classification. A short local
child-process case validates 12-worker start, liveness, graceful stop, checksum collection and
parent-controlled cleanup; it is not a thermal or performance load test.

## Frozen design values

- workers: 12 independent processes;
- formal average aggregate CPU busy minimum: 70%;
- sustained low-busy boundary: three consecutive post-warmup windows below 60%;
- entry package/max-sensor limits: 60/65 C;
- target thermal stop: 100 C;
- target timeline: 30-second pre-observation plus at most 600 seconds formal observation;
- target sample interval: five seconds;
- target execution and SSH: prohibited in this mock; target entry requires a separately matching
  protocol and authorization.

## Required artificial cases

- complete valid load sequence;
- pre-observation activity contamination;
- pre-observation throttle increment;
- package and maximum-sensor entry-temperature rejection;
- sustained load under-delivery;
- formal-average under-delivery;
- temperature hard stop;
- worker-start/stop evidence mismatch;
- negative throttle field or interface failure;
- target mode without matching authorization rejected before evidence creation.

## Required local lifecycle case

Start 12 workers for a short bounded interval, prove they are alive, stop them through the parent,
collect exit state and worker records, and prove no worker remains alive. The case must not read
DK-2500 interfaces or use SSH, OpenVINO, a model or an external stress package.

## PASS

All required cases classify as frozen, the local lifecycle leaves no live worker, existing D2 and
Phase 4 regressions pass, and aggregate evidence records `target_accessed: false` and
`execution_authorized: false`.

## Interpretation limits

PASS supports implementation behavior under artificial/local conditions only. It cannot establish
DK-2500 load delivery, temperature, throttling, cleanup over SSH, hardware health, Stability,
deployment, real-time or safety behavior. A separately frozen target protocol, readiness review and
human authorization remain mandatory.
