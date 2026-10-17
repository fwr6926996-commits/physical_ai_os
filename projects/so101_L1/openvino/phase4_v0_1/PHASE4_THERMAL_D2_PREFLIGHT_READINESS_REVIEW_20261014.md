# Phase 4 Thermal D2-PREFLIGHT Readiness Review

Protocol: `P4-DK2500-THERMAL-D2-PREFLIGHT-001` version `0.1`

Review date: `2026-10-14`

Engineering result: `READY FOR HUMAN AUTHORIZATION DECISION`

Learning result: `PASS`

Target authorization: `NONE`

Target access during this review: `NONE`

## Decision

The protocol, implementation, no-target mock evidence and learning check are ready for a separate
human decision on one D2-PREFLIGHT target attempt. This readiness decision does not itself authorize
SSH, target reads, a retry, `D2-IDLE`, a load experiment, Short rerun or Stability.

If a later authorized target result is `PREFLIGHT_PASS_REVIEW_PENDING`, the only permitted next
action is independent review of the preserved target evidence. PASS does not automatically
authorize design or execution of `D2-IDLE`.

## Frozen snapshot

The following SHA-256 values define the exact reviewed snapshot:

- protocol `PHASE4_THERMAL_D2_PREFLIGHT_PROTOCOL_20261013.md`:
  `670fc9e1276171a4ea8bac7f94da5adfaed230f43aea891acfb8655382a4101e`
- remote probe `phase4_thermal_d2_remote_probe.py`:
  `9da45e6ef16a38a20206bc8e343b2c9052b156d155534a5548dbfefa756b4e6f`
- local runner `phase4_thermal_d2_preflight.py`:
  `eb976ad3dda9bd1d3c8adcea50d038af39b7cb2c8583e7d9d364476260a623d6`
- mock validator `validate_phase4_thermal_d2_preflight_mock.py`:
  `d7c8203a8fe3736a52bee7f6fd436e43063b2cb4588463f125aa1d89ada2bcd7`

Any change to the protocol, runner or remote probe invalidates a later authorization tied to these
hashes and requires a new readiness review. The validator hash preserves the identity of the mock
control used for this review.

## Evidence reviewed

- D1 protocol and review established the artificial-input logic boundary without target access.
- `thermal_d2_preflight_mock_validation_20261013.json` records
  `PASS_D2_PREFLIGHT_NO_TARGET_MOCK`.
- The implementation review records `PASS — NO-TARGET MOCK ONLY`.
- JSON parsing of the preserved mock evidence passed.
- The exact implementation hashes still match the hashes recorded at mock review.
- Repository diff checking of the D2-PREFLIGHT files passed.

The mock covers successful parsing, identity drift, incomplete throttle fields, missing CPU-package
temperature, a `101 C` stop, missing frequency evidence and the production authorization guard.
It does not describe the DK-2500 interfaces or their present values.

## Learning verification

The human owner demonstrated the following boundaries:

- an identity mismatch means the frozen target state changed and requires Review;
- a missing frequency reading is not `0 MHz`, and actual coverage constrains later monitoring;
- a readable throttle count remains a partial fact when total/max fields are missing, but the
  preflight cannot pass;
- the no-target mock validates calculation, classification and protection logic only;
- a real preflight PASS can prove only current one-shot readability;
- after a real run, the only permitted next action is review of the real evidence.

There is no remaining D2-PREFLIGHT learning gate before a human authorization decision.

## Proposed one-attempt identity

- run ID: `thermal_d2_preflight_20261014_01`
- target: `hepintel@192.168.77.2`
- expected hostname: `hepintelpc`
- dedicated SSH key: `/home/lucas/.ssh/id_ed25519_dk2500`
- timeout: `30 seconds`
- automatic retry: `false`
- local evidence directory:
  `evidence/phase4_0_harness/thermal_d2_preflight_20261014_01/`
- proposed authorization record:
  `evidence/phase4_0_harness/authorizations/thermal_d2_preflight_20261014_01.json`

An authorization record does not yet exist. It must bind the run ID, target, timeout, no-retry
rule, protocol identity and the exact protocol, runner and remote-probe hashes above.

## Controlled-execution boundary

One later authorized attempt may only:

1. stream the frozen remote probe through SSH stdin to system Python;
2. read identity, boot, throttle, package-temperature and CPU-frequency interfaces once;
3. return one JSON payload;
4. preserve stdout, stderr, command metadata and the structured local result;
5. stop after success, first hard failure or the 30-second timeout.

It may not create a target file, install or update software, import OpenVINO, access a model,
generate load, change configuration, run a sampling loop or retry automatically.

## Claims after a later target attempt

A target PASS may support only:

- the frozen target identity matched at that moment;
- the required interfaces were readable and parseable in one snapshot;
- the protected no-load and no-target-write boundaries were reported as preserved;
- the captured evidence is ready for Review.

It cannot establish stable idle temperature, absence or duration of throttling, the cause of the
earlier throttle increment, load association, Short reinterpretation, Stability readiness,
deployment, real-time behavior, hardware health or physical safety.

A target FAIL must preserve partial readable facts and stop. It does not authorize an alternate
command, interface repair, package installation or second attempt.

## Next gate

The only open gate is a separate human-owned decision to authorize or reject the proposed single
target attempt. Until that decision is recorded, target execution remains prohibited.
