# Experiment Protocol Template

Template version: `0.1`

Status: `TRIAL`

Compatible workflow: `0.1`

## Identity

- Protocol ID:
- Title:
- Owner:
- Reviewers:
- Date frozen:
- Classification: `EXPLORATORY` / `QUALIFICATION`
- Governing requirement:
- Git commit or frozen snapshot:

## Question and decision

- Question this experiment answers:
- Decision this result may support:
- Claims this experiment cannot support:

## Frozen artifacts and environment

- Hardware manifest and state:
- Software baseline:
- Model or policy package and hashes:
- Dataset, input source or input hashes:
- Device, backend and precision:
- Runtime configuration:
- Power, thermal and host-load controls:

## Experimental design

- Baseline or control:
- Single changed variable:
- Constants:
- Warmup:
- Sample count or duration:
- Repetitions:
- Measurement boundary:

## Metrics and gates

- Correctness metrics and thresholds:
- Task-relevant metrics and thresholds:
- Performance metrics:
- Resource and stability metrics:
- Hard PASS conditions:
- Hard FAIL conditions:
- Diagnostic-only observations:

## Run and stop policy

- Maximum runs:
- Success stop:
- Failure stop:
- Timeout and recovery:
- Conditions requiring a new protocol version:

## Evidence contract

- Raw outputs:
- Structured result:
- Logs and telemetry:
- Artifact hashes:
- Review record:

## Pre-run review

- [ ] Inputs, environment and hashes are frozen.
- [ ] Metrics and thresholds were defined before results were observed.
- [ ] Exploratory and qualification evidence are distinguishable.
- [ ] Stop and recovery behavior is bounded.
- [ ] Human-owned decisions and physical safety boundaries are explicit.

## Deviations

Do not edit the frozen sections after execution begins. Append dated deviations here and state whether the run remains valid, becomes exploratory, or requires a new protocol.
