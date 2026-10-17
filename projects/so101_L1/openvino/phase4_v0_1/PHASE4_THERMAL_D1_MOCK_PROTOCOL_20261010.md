# Phase 4 Thermal Diagnosis D1 Mock Protocol

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D1-MOCK-001`
- Protocol version: `0.1`
- Owner: human
- Classification: `EXPLORATORY — MOCK ONLY`
- Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`
- Status: `COMPLETE — ENGINEERING PASS; LEARNING PASS`
- Sampler SHA-256:
  `663825e677415750e75ed73bed00ebbbde9d8b13c45ce0a945749e8e6abc49c4`
- Validator SHA-256:
  `11f7258f11a6c27cb8099acc61b3e745965cc28c965d2a3034fe48f7ce9f5a26`

## Question and decision

- Question: Does the proposed sampler correctly interpret artificial count, cumulative-time and
  maximum-time fields, fail closed on incomplete evidence, preserve duplicate package paths without
  summing them, classify the frozen thermal stop and prohibit target access?
- Decision supported: whether the mock mechanism is adequate to begin designing `D2-PREFLIGHT`, the target
  read-only interface check.
- Prohibited claims: any statement about actual DK-2500 interfaces, temperature, throttling,
  OpenVINO, CPU-load behavior, Stability, deployment, real-time behavior or physical safety.

## Frozen artificial inputs

### Normal and duplicate-path case

Two artificial package paths (`cpu0`, `cpu1`) carry the same values:

| Sample | count | total time ms | max time ms | temperature C |
|---|---:|---:|---:|---:|
| before | 10 | 100 | 5 | 40 |
| after | 12 | 108 | 6 | 91 |

Expected per-path changes are `+2`, `+8 ms` and `+1 ms`. Both paths must remain visible and no
summed package-event or duration field may be produced.

### Failure controls

1. Remove `max_time_ms` from one path: result must be `MOCK_INTERFACE_INCOMPLETE`, exit non-zero.
2. Provide `101 C`: result must be `MOCK_THERMAL_STOP`, exit non-zero.
3. Omit the fixture argument: the D1 program must reject execution before creating a run directory.

## Experimental design

- Baseline: artificial values with known expected interpretation.
- Single changed variable for each failure control: one missing field, temperature above the frozen
  stop, or absence of the mandatory artificial fixture.
- Hardware/model/backend: none accessed.
- Repetitions: one human-triggered validator execution; no automatic retry.
- Measurement boundary: JSON fixture input to structured mock result output.

## Metrics and gates

Hard PASS requires all of the following:

- exact expected per-path deltas;
- two duplicate paths preserved and no sum emitted;
- incomplete group rejected with non-zero exit;
- 101 C classified as mock thermal stop with non-zero exit;
- target mode unavailable without a fixture;
- result explicitly records `target_accessed: false` and mock-only interpretation limits.

Any mismatch is D1 FAIL and must be reviewed before another attempt.

## Run and stop policy

- Maximum evidence-producing executions: one.
- Automatic retry: prohibited.
- The human owner performs the first execution.
- Any unexpected traceback, missing output, status mismatch or target access stops the workflow.
- D1 PASS permits only `D2-PREFLIGHT` design; it does not authorize the preflight or idle sampling.

## Evidence contract

- Structured result:
  `evidence/phase4_0_harness/thermal_d1_mock_validation_20261010_01.json`
- Output must refuse overwrite.
- Result records sampler/validator SHA-256, all four control outcomes and prohibited claims.
- Review record is created only after the human execution is inspected.

## Pre-run review

- [x] Question, artificial inputs and expected outputs defined before human execution.
- [x] Mock evidence is explicitly separated from target evidence.
- [x] Stop behavior and one-execution limit are bounded.
- [x] No DK-2500, model or load access exists in D1.
- [x] Static checks complete and implementation hashes frozen.
- [x] Human owner executed the command and explained the result on 2026-10-13.

Review record: `PHASE4_THERMAL_D1_MOCK_REVIEW_20261013.md`

## Deviations

None. No accepted D1 execution has occurred.
