# Phase 4 Thermal D2-PREFLIGHT Implementation Review

Protocol: `P4-DK2500-THERMAL-D2-PREFLIGHT-001` version `0.1`

Mock evidence:
`evidence/phase4_0_harness/thermal_d2_preflight_mock_validation_20261013.json`

Engineering result: `PASS — NO-TARGET MOCK ONLY`

Learning result: `PASS`

Target authorization: `NONE`

## Implementation boundary

The implementation has three isolated roles:

1. `phase4_thermal_d2_remote_probe.py` is streamed to system Python over SSH stdin. It performs
   one read of identity, boot, thermal-throttle, hwmon-temperature and CPU-frequency interfaces,
   emits one JSON object to stdout and has no target-write or sampling-loop path.
2. `phase4_thermal_d2_preflight.py` is the local supervisor. Production mode requires a matching
   one-attempt authorization and dedicated SSH key before it can create a run directory or invoke
   SSH. Fixture mode cannot accept authorization or SSH arguments.
3. `validate_phase4_thermal_d2_preflight_mock.py` supplies local artificial payloads and never
   invokes SSH.

Implementation SHA-256 values:

- remote probe: `9da45e6ef16a38a20206bc8e343b2c9052b156d155534a5548dbfefa756b4e6f`
- local runner: `eb976ad3dda9bd1d3c8adcea50d038af39b7cb2c8583e7d9d364476260a623d6`
- mock validator: `d7c8203a8fe3736a52bee7f6fd436e43063b2cb4588463f125aa1d89ada2bcd7`

## Mock verification

The no-target mock demonstrated:

- a complete matching payload becomes `MOCK_PREFLIGHT_PASS_REVIEW_PENDING`;
- kernel identity drift produces `IDENTITY_MISMATCH:kernel`;
- one incomplete throttle group produces `INCOMPLETE_THROTTLE_GROUP`;
- no identifiable package sensor produces `NO_CPU_PACKAGE_TEMPERATURE`;
- artificial `101 C` produces `THERMAL_ABNORMAL_STATE`;
- no readable frequency path produces `NO_READABLE_CPU_FREQUENCY`;
- production mode without authorization fails before an evidence directory is created;
- every mock result records `target_accessed: false`.

Python compilation, JSON validation, diff checks and the existing ten Phase 4 unit/integration tests
passed.

## Evidence boundary

This review proves only local parsing, Gate classification, target-mode authorization protection
and preservation of artificial payloads. It does not prove SSH connectivity, target identity,
actual sysfs topology, interface permissions, temperature values, frequency coverage or target-side
no-write behavior.

Partial target facts, if later observed during a failed authorized preflight, must be preserved but
cannot be promoted to PASS.

## Remaining gates

The human owner demonstrated that:

- a frozen identity mismatch requires Review even when interfaces remain readable;
- missing frequency paths cannot be represented as `0 MHz`, and coverage must constrain later
  monitoring design;
- a readable count is a preservable partial fact but cannot replace missing total/max evidence;
- no-target mock PASS validates local logic only;
- target-preflight PASS would prove current one-shot readability only and must be reviewed before
  any `D2-IDLE` design or execution.

Before any target access:

1. final implementation and protocol hashes must be frozen;
2. a run ID and separate one-attempt authorization must be created from those exact hashes;
3. the human owner must execute the first target preflight.

No target access, `D2-IDLE`, load, Short rerun or Stability is authorized by this review.
