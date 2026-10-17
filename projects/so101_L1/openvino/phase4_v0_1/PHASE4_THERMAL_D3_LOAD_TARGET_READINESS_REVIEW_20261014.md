# Phase 4 Thermal D3-LOAD Target Readiness Review

Protocol: `P4-DK2500-THERMAL-D3-LOAD-001` version `0.1`

Review date: `2026-10-14`

Engineering result: `READY FOR ONE HUMAN AUTHORIZATION DECISION`

Learning result: `PASS`

Target authorization: `NONE`

Target access during implementation and review: `NONE`

## Decision

The D3 target protocol, 12-worker load controller, parent-death protection, target identity and
interface gate, run-specific authorization gate, local Supervisor and no-target regression are
ready for a separate human decision on one target attempt. This review does not itself authorize
SSH, CPU load or target execution.

## Frozen snapshot

- target protocol:
  `a3f5b60a84f8f1d67eb7daaf030d660663766cd8acd5fc012174014f78ca0763`;
- target sampler/load controller:
  `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe`;
- D3 Supervisor:
  `098142645256d454881599850343248525d5cf5ec74426b7f462c695c0367c11`;
- D3 validator:
  `da9394e429f5ac3d323430477b162d1be427ae15c837cede4a628759a7998fcc`;
- final readiness mock evidence:
  `ead89e595cc3e68fe61f146e10b62f395e518505e26218964a76818b1816d119`.

Any change to the protocol, sampler/load controller or Supervisor invalidates a later authorization
bound to these hashes.

## Verified readiness evidence

- D3 no-target mock status: `PASS_D3_LOAD_NO_TARGET_MOCK_VALIDATION`;
- `target_accessed: false`, `execution_authorized: false`;
- accepted preconditions, load thresholds, thermal stop and counter rules classified correctly;
- 12/12 local workers started, remained alive and stopped with 0 survivors;
- 12/12 graceful-stop records were collected;
- abrupt parent exit left 0 surviving workers through Linux parent-death signaling;
- target entry without matching authorization failed before evidence creation;
- D2 artificial regression passed;
- Phase 4 test suite passed `10/10`;
- Python compilation, JSON validation and whitespace checks passed.

Preserved readiness evidence:
`evidence/phase4_0_harness/thermal_d3_load_mock_validation_20261014_02.json`.

## Controlled target boundary

One later authorized attempt may only:

1. use the dedicated SSH key and frozen DK-2500 identity/interfaces;
2. complete a 30-second no-load pre-observation;
3. start exactly 12 arithmetic workers only if activity, temperature and throttle preconditions
   pass;
4. observe for at most 600 loaded seconds with five-second samples;
5. stop all workers on completion or the first frozen stop condition;
6. preserve local raw and structured evidence;
7. avoid retry, reconnect, OpenVINO, models, external stress tools and configuration changes.

D3 intentionally creates sustained CPU load. The 100 C thermal hard stop, 60/65 C entry controls,
worker liveness checks, Supervisor watchdog and parent-death signal bound but do not eliminate that
risk. The board must remain untouched with unobstructed airflow during execution.

## Proposed one-attempt identity

- run ID: `thermal_d3_load_20261014_01`;
- target: `hepintel@192.168.77.2`;
- pre-observation: 30 seconds;
- formal load observation: at most 600 seconds;
- startup timeout: 30 seconds;
- complete-event watchdog: 15 seconds;
- overall Supervisor timeout: 660 seconds;
- automatic retry/reconnect: false;
- evidence directory:
  `evidence/phase4_0_harness/thermal_d3_load_20261014_01/`;
- proposed authorization:
  `evidence/phase4_0_harness/authorizations/thermal_d3_load_20261014_01.json`.

The authorization does not exist. It must bind this run ID, target, timeout values, no-retry rule
and the exact protocol, sampler and Supervisor hashes above.

## Claims after execution

Even a complete result may establish only whether this controlled CPU-only load condition produced
throttle-field increments and the observed activity/thermal context. It cannot be labeled a Short
reproduction, root cause, hardware-health result, Stability qualification, deployment readiness,
real-time guarantee or physical-safety result.

## Next gate

The only open gate is a human decision to authorize or reject the named one-attempt D3 run. After
execution, the only permitted next action is evidence review; no automatic retry, Short rerun,
Stability or deployment transition is authorized.
