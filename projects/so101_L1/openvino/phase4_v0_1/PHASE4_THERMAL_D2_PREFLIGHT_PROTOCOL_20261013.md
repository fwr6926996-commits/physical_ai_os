# Phase 4 Thermal Diagnosis D2-PREFLIGHT Protocol

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D2-PREFLIGHT-001`
- Protocol version: `0.1`
- Title: DK-2500 thermal-interface one-shot read-only feasibility check
- Owner: human
- Reviewers: human owner and Codex
- Date frozen: `2026-10-13`
- Classification: `EXPLORATORY — TARGET INTERFACE PREFLIGHT`
- Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`
- Governing D1 review: `PHASE4_THERMAL_D1_MOCK_REVIEW_20261013.md`
- Status: `READY FOR AUTHORIZATION DECISION — TARGET ACCESS NOT AUTHORIZED`
- Frozen snapshot: exact protocol and implementation SHA-256 values recorded in
  `PHASE4_THERMAL_D2_PREFLIGHT_READINESS_REVIEW_20261014.md`
- Readiness review: `PHASE4_THERMAL_D2_PREFLIGHT_READINESS_REVIEW_20261014.md`

Frozen implementation SHA-256 values:

- remote probe: `9da45e6ef16a38a20206bc8e343b2c9052b156d155534a5548dbfefa756b4e6f`
- local runner: `eb976ad3dda9bd1d3c8adcea50d038af39b7cb2c8583e7d9d364476260a623d6`
- mock validator: `d7c8203a8fe3736a52bee7f6fd436e43063b2cb4588463f125aa1d89ada2bcd7`

## Question and decision

- Question: Does the currently connected DK-2500 expose a complete, readable and parseable set of
  one-shot thermal-throttle, CPU-package-temperature and CPU-frequency interfaces suitable for
  later design of `D2-IDLE`?
- Decision this result may support: begin collaborative design of `D2-IDLE`, or route an interface
  gap to review before any continuous observation.
- Claims this check cannot support: stable idle temperature, absence or duration of idle throttling,
  load association, Short reinterpretation, Stability readiness, performance admission,
  deployment, real-time behavior or physical safety.

## Frozen target and protected boundaries

Expected target identity, subject to final pre-run review:

- SSH identity: `hepintel@hepintelpc` over the existing direct Ethernet route.
- Expected hostname: `hepintelpc`.
- Expected CPU: `Intel(R) Core(TM) Ultra 5 225U`.
- Expected OS: Ubuntu `24.04.4 LTS`.
- Expected kernel: `6.17.0-35-generic`.
- Expected Python: system Python `3.12.3`.
- Physical route: strict no-touch SSH; existing board placement, cooling and cabling remain
  unchanged.

Protected boundaries:

- no package installation, update, permission change or network reconfiguration;
- no file creation on the target;
- no OpenVINO import, model access, compile, inference or CPU-load generation;
- no repeated or timed sampling loop;
- no fan, governor, power-profile, thermal-policy or firmware change;
- no hardware handling.

The target command must be sent from the local machine over the existing SSH connection, perform
one bounded read of each interface and return structured output to the local evidence directory.

## Interfaces and evidence fields

### Target and boot identity

- hostname;
- CPU model;
- OS release and kernel;
- Python version;
- UTC timestamp;
- boot ID and uptime.

Boot identity is required because cumulative and maximum throttle fields may span the current boot.
Evidence from different boot IDs must not be treated as one continuous counter history.

### Thermal-throttle groups

Discover actual `core_throttle` and `package_throttle` groups under the online CPU topology. For
every discovered group, read and parse together:

- `*_throttle_count`;
- `*_throttle_total_time_ms`;
- `*_throttle_max_time_ms`.

Each path and value is preserved separately. Repeated package paths are never summed into an
independent-event or duration total. A group with any missing or unparseable field is incomplete.

### Temperature

- readable hwmon sensor paths;
- hwmon device names and sensor labels where exposed;
- current Celsius values;
- identifiable CPU package temperature;
- maximum current readable sensor value.

### CPU frequency

- online CPU declaration;
- discovered readable frequency paths;
- current values in MHz;
- total online logical-CPU count;
- readable-path count and explicit coverage ratio;
- missing or unparseable paths.

No exact frequency-path count is frozen before discovery because the hybrid CPU may expose
frequency topology through shared policies or asymmetric per-CPU paths.

### Explicit exclusions

Do not capture MAC addresses, storage serials, adapter serials, SSH private-key material, model
artifacts or unrelated environment variables.

## Experimental design

- Baseline or control: none; this is a one-shot feasibility check, not a behavior comparison.
- Changed boundary from D1: artificial fixture input is replaced by read-only target interfaces.
- Constants: target identity, SSH route, physical setup, no-model/no-load scope and `100 C` thermal
  abnormal-state threshold.
- Warmup: none.
- Sample count: exactly one logical snapshot per interface.
- Repetitions: one evidence-producing attempt; automatic retry disabled.
- Measurement boundary: remote read begins after verified SSH connection and ends when one
  structured payload is returned; local evidence preservation follows.
- Overall timeout: `30 seconds`.

## Metrics and gates

### Hard PASS conditions

- actual target identity matches every frozen identity field;
- at least one throttle group is discovered;
- every discovered throttle group contains a parseable count, total-time and maximum-time triplet;
- no repeated package-path sum is produced;
- at least one identifiable CPU package temperature is readable and below `100 C`;
- at least one CPU frequency interface is readable and coverage is reported without inventing
  missing values;
- no interface read or parse error is hidden;
- structured evidence is saved locally with the frozen protocol and implementation identities;
- the result records target access as true and all prohibited actions as false.

### Hard FAIL conditions

- target identity mismatch;
- no throttle group, any incomplete discovered throttle group, or any unparseable throttle value;
- no identifiable CPU package temperature;
- no readable CPU frequency interface;
- any current readable temperature `>= 100 C`;
- SSH/timeout failure, unexpected remote persistence or inability to save complete local evidence;
- any target write, model/runtime access, load generation or other protected-boundary violation.

### Diagnostic-only observations

All instantaneous temperatures, frequencies and throttle values are descriptive snapshots. They do
not become idle-baseline, stability, duration or performance evidence.

Partial readable facts remain preserved when the overall gate fails. Missing evidence is never
converted to zero and a partial result is never reported as complete.

## Run and stop policy

- Maximum evidence-producing attempts: one.
- Automatic retry: prohibited.
- Success stop: one complete structured snapshot returned and preserved.
- Failure stop: first hard-fail condition; preserve all available local stdout, stderr and partial
  structured evidence.
- Timeout and recovery: `30-second` local timeout; terminate the local SSH client. The
  final implementation must contain no remote loop or persistent process.
- A connection or interface failure does not authorize installation, permission changes, alternate
  commands or a second attempt.
- Any change to identity guards, interface set, timeout, gate, evidence contract or target command
  requires a reviewed protocol version change before execution.

## Evidence contract

Proposed evidence root:
`evidence/phase4_0_harness/thermal_d2_preflight_20261014_01/`

Required local artifacts:

- `result.json`: structured identity, interface inventory, completeness checks and classification;
- `remote_stdout.txt`: exact remote standard output;
- `remote_stderr.txt`: exact remote standard error;
- `command.json`: argument-vector representation with no secret key material;
- implementation and protocol SHA-256 values;
- subsequent independent Review record.

The run directory must not already exist and must never be overwritten.

## Pre-run review

- [x] Question and prohibited claims are explicit.
- [x] D1 mock evidence and target preflight evidence are separated.
- [x] One-shot boundary, no-target-write rule and fail-closed behavior are specified.
- [x] Partial facts are preserved without being promoted to a complete PASS.
- [x] Human-owned target execution and physical boundaries are explicit.
- [x] Human accepted the `30-second` timeout and exact identity guards.
- [x] Implementation and no-target mock controls exist and passed engineering review.
- [x] Human explained the identity, partial-evidence, completeness and next-gate boundaries.
- [x] Implementation hashes are frozen; the final protocol hash is recorded in the readiness review.
- [ ] A separate one-attempt human authorization exists.

## Current decision boundary

This protocol does not authorize SSH, target reads, `D2-IDLE`, Short rerun, Stability or any load.
The only permitted next action is a separate human decision on one target-preflight attempt using
the exact frozen identities.

## Deviations

None. No D2-PREFLIGHT target execution has begun.
