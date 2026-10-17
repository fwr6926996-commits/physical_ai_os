# Phase 4 Thermal D2-IDLE Target Readiness Review

Protocol: `P4-DK2500-THERMAL-D2-IDLE-001` version `0.1`

Review date: `2026-10-14`

Engineering result: `READY FOR ONE HUMAN AUTHORIZATION DECISION`

Learning result: `PASS — D2-IDLE DESIGN AND MOCK BOUNDARIES`

Target authorization: `NONE`

Target access during protocol implementation and review: `NONE`

## Decision

The executable D2-IDLE target protocol, startup identity/interface gate, run-specific authorization
gate, local Supervisor and no-target regression are ready for a separate human decision on one
bounded target attempt. This readiness result does not itself authorize SSH or D2-IDLE execution.

The earlier first-encounter learning work is not repeated. The human owner has already demonstrated
the distinction between artificial logic validation and target evidence, and between an
`IDLE_CONTROL_CONTAMINATED` result and a hardware fault.

## Frozen snapshot

- target protocol:
  `afab06716230f566c6823d50b53ad7315a54ca1cd676c64be3639c2740df77e7`
- remote sampler:
  `ce074052dc95510bbf66d822b4d2b8233526c2654417b3bab8bd1570821e2047`
- local Supervisor:
  `07f320776ee8382401909841cfa1e6adc3f39c369bde219304bb54835f463af3`
- no-target regression validator:
  `a3763d1548260356f4c5686513cd013ecfbb946f7a7921b527372275cda652b4`
- target-readiness no-target regression evidence:
  `9b13fcb851b780366b7e20dbf916088ff35138e5e4b4cc41a28b38f408d3caa1`

Changing the protocol, Supervisor or sampler invalidates any later authorization bound to this
snapshot and requires a new readiness review.

## Review evidence

- no-target regression status: `PASS_D2_IDLE_NO_TARGET_MOCK_VALIDATION`;
- target accessed: `false`;
- execution authorized: `false`;
- quiet 127-sample artificial sequence completed;
- activity, temperature, interface, counter, monotonic and sampling failures classified as frozen;
- complete-line and partial-line progress loss triggered bounded Supervisor recovery;
- target mode without authorization failed before evidence-directory creation;
- fixture mode rejected authorization and SSH arguments;
- Python compilation passed;
- existing Phase 4 unit/integration suite passed `10/10`;
- repository diff whitespace check passed.

The preserved regression evidence is:
`evidence/phase4_0_harness/thermal_d2_idle_target_readiness_mock_20261014_01.json`.

## Controlled target boundary

One later authorized attempt may only:

1. use `/home/lucas/.ssh/id_ed25519_dk2500` and `hepintel@192.168.77.2`;
2. stream the frozen sampler to `/usr/bin/python3 -u -` over one SSH session;
3. reject target identity or the frozen 28 throttle/14 frequency inventories before sampling;
4. perform the 30-second pre-observation and, only if valid, the 600-second formal observation;
5. preserve local raw and structured evidence;
6. stop on completion or the first frozen failure, with no retry or reconnect.

It may not write a target file, run OpenVINO or a model, create deliberate load, alter software,
network, power, fan, governor, firmware or hardware state, or continue into D3-LOAD or Stability.

## Proposed one-attempt identity

- run ID: `thermal_d2_idle_20261014_01`;
- target: `hepintel@192.168.77.2`;
- startup timeout: `30 seconds`;
- progress watchdog: `15 seconds` without a complete event;
- overall Supervisor timeout: `660 seconds`;
- automatic retry: `false`;
- evidence directory:
  `evidence/phase4_0_harness/thermal_d2_idle_20261014_01/`;
- proposed authorization record:
  `evidence/phase4_0_harness/authorizations/thermal_d2_idle_20261014_01.json`.

The authorization record does not yet exist. It must bind this run ID, target, timeout values,
no-retry rule and the exact protocol, Supervisor and sampler hashes above.

## Remaining limitations

The no-target checks cannot prove the current DK-2500 identity or interface state, real sampler
perturbation, SSH behavior, actual idle activity, temperatures, frequencies or throttle deltas.
Those are exactly the bounded questions of the proposed target attempt. Even a completed attempt
remains review-pending and cannot establish Stability, deployment readiness, real-time behavior,
hardware health or physical safety.

## Next gate

The only open gate is a human decision to authorize or reject the named one-attempt run. If
authorized, execution must use the exact frozen snapshot. After execution, the only permitted next
action is review of the preserved target evidence; no automatic retry or D3-LOAD transition is
allowed.
