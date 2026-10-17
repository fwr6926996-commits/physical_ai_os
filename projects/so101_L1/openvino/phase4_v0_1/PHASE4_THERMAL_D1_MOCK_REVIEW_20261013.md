# Phase 4 Thermal Diagnosis D1 Mock Review

Protocol: `P4-DK2500-THERMAL-D1-MOCK-001` version `0.1`

Evidence:
`evidence/phase4_0_harness/thermal_d1_mock_validation_20261010_01.json`

Human execution timestamp: `2026-10-13T13:46:37.930384+00:00`

Engineering result: `PASS`

Learning result: `PASS`

Target execution: `NONE`

## Engineering verification

- Evidence JSON is valid and uses the frozen protocol ID and version.
- Sampler SHA-256 matches the frozen value:
  `663825e677415750e75ed73bed00ebbbde9d8b13c45ce0a945749e8e6abc49c4`.
- Validator SHA-256 matches the frozen value:
  `11f7258f11a6c27cb8099acc61b3e745965cc28c965d2a3034fe48f7ce9f5a26`.
- The known artificial sequence preserved two package paths and reported per-path deltas of
  `+2` transitions, `+8 ms` cumulative time and `+1 ms` maximum-time change.
- No duplicate-path sum was emitted.
- One missing `max_time_ms` field reduced two groups to one complete group and produced
  `MOCK_INTERFACE_INCOMPLETE` with a non-zero return code.
- Artificial `101 C` produced `MOCK_THERMAL_STOP` with a non-zero return code.
- Omitting the mandatory fixture rejected execution before creating a run directory.
- The evidence explicitly records `target_accessed: false` and `execution_authorized: false`.

## Learning verification

The human owner demonstrated that:

- missing evidence is not equivalent to a zero value;
- mock input validates software behavior, not the real DK-2500 interface;
- duplicate package paths can be valid repeated views of the same package status and must be
  preserved without being summed into independent events;
- a non-zero return code is the expected fail-closed outcome for the missing-field and thermal-stop
  controls;
- D1 permits only design of the next interface-feasibility step and does not authorize target
  access or idle sampling.

One terminology issue was found during learning review: `D2-A` and `D2-B` looked like experimental
A/B groups even though they were only sequential substeps. Future records use the clearer names
`D2-PREFLIGHT`, `D2-IDLE` and, if later justified, `D3-LOAD`.

## Evidence boundary

D1 proves the bounded mock parser, completeness gate, duplicate-path handling, synthetic thermal
stop classification and absence of a target-reading mode for the frozen implementation.

D1 does not prove that DK-2500 exposes readable count, total-time, maximum-time, temperature or
frequency interfaces. It does not characterize idle or load behavior and does not authorize
Stability, deployment, real-time or physical-safety claims.

## Decision

D1 is complete with separate engineering and learning PASS results.

The only permitted next activity is collaborative design of `D2-PREFLIGHT`. No DK-2500 command,
interface read, idle observation or load execution is authorized by this review.
