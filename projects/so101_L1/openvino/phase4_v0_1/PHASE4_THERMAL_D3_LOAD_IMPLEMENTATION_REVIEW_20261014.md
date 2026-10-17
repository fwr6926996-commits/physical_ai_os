# Phase 4 Thermal D3-LOAD No-Target Implementation Review

Review date: `2026-10-14`

Governing mock protocol: `P4-DK2500-THERMAL-D3-LOAD-MOCK-001` version `0.1`

Engineering result: `PASS — NO-TARGET IMPLEMENTATION AND MOCK ONLY`

Learning result: `PASS`

Target readiness: `NOT READY — HARD-DISABLED`

Target authorization: `NONE`

Target access during implementation and mock: `NONE`

## Decision

The accepted D3 load-control constants, artificial classification and local 12-worker lifecycle pass
the no-target implementation boundary. The D3 Supervisor rejects target mode before creating an
evidence directory. No SSH command, target protocol or authorization record exists.

## Frozen no-target identity

- mock protocol:
  `b46a775190ec6ac1bc1479fb4b850d45e6c75d2e0ab84273b57339861d111937`;
- shared D2/D3 remote sampler source:
  `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe`;
- D3 local Supervisor:
  `45e9505b57365f95e04354e5b02e957d237397db30eb6abf6408adbfda47802c`;
- D3 mock validator:
  `dab315bd9aa912224ffe384084a29c0f7495bc42e091edc99c6a31c87ed918ce`;
- final mock evidence:
  `38939434a92ee79a7b8ed47c157438fea4ee7e1e10e24fcf68837928a4d0d9c6`.

## Worker lifecycle implementation

- 12 workers are created with Linux `fork`; no package or target file is needed;
- every worker performs deterministic fixed-width integer arithmetic;
- an anonymous pipe returns PID, iteration count and checksum during graceful stop;
- normal completion and experiment stops send `SIGTERM`, wait up to three seconds and use
  `SIGKILL` only for remaining workers;
- each worker configures Linux parent-death signal `SIGTERM` and rechecks the parent PID, preventing
  it from continuing as an orphan if the target sampler disappears;
- the parent records worker start, liveness, exits, recovery method and collected records.

Parent-death signaling complements Supervisor cleanup. It does not prove how a future remote
session behaves until the frozen code is reviewed and executed on DK-2500.

## Mock evidence

Artificial cases passed for:

- valid 127-sample load sequence at 80% aggregate busy;
- pre-observation activity and throttle-increment rejection;
- 60 C package and 65 C maximum-sensor entry controls;
- sustained and formal-average load under-delivery;
- unexpected worker exit;
- 100 C thermal stop;
- invalid worker-stop evidence;
- negative throttle counter;
- target hard-disable before evidence creation.

Local child-process cases passed:

- 12/12 workers alive before controlled stop;
- 0 workers alive afterward;
- 12/12 worker records collected under `SIGTERM` cleanup;
- abrupt parent exit left 0 surviving workers.

The existing D2 artificial regression passed, Python compilation passed, the Phase 4 test suite
passed `10/10`, and repository whitespace checking passed.

## Supported conclusions

- accepted D3 thresholds and terminal classes are represented consistently under artificial data;
- the local host can start and clean up the proposed worker mechanism;
- normal parent cleanup and tested parent-death cleanup leave no surviving local worker;
- the current D3 Supervisor cannot access DK-2500.

## Unsupported conclusions

The evidence cannot establish:

- that DK-2500 delivers 70% aggregate CPU busy with 12 workers;
- actual DK-2500 scheduling, temperature, frequency or throttle behavior;
- cleanup behavior over the future SSH path;
- sampling perturbation under target load;
- any cooling, hardware-health, Stability, deployment, real-time or safety conclusion.

## Next gate

The human owner demonstrated that normal parent cleanup handles expected stops, while the Linux
kernel parent-death signal protects against orphan CPU workers when the parent sampler disappears
before its cleanup code can run.

The next permitted action is one bundled target protocol/readiness implementation. It must bind
exact hashes, preserve the target hard stops and remain separately authorized. This review does not
authorize target execution.
