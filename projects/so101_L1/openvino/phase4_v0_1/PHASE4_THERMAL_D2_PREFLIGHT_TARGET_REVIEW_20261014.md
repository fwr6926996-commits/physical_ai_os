# Phase 4 Thermal D2-PREFLIGHT Target Evidence Review

Protocol: `P4-DK2500-THERMAL-D2-PREFLIGHT-001` version `0.1`

Run ID: `thermal_d2_preflight_20261014_01`

Review date: `2026-10-14`

Execution result: `COMPLETE — ONE AUTHORIZED ATTEMPT, NO RETRY`

Engineering review result: `PASS — CURRENT ONE-SHOT INTERFACE READABILITY ONLY`

Learning result for target-evidence interpretation: `PASS`

Authorization beyond evidence review: `NONE`

## Decision

The frozen target identity matched and the required interfaces were readable and parseable in the
single authorized snapshot. D2-PREFLIGHT therefore passes its narrow engineering question: the
current DK-2500 interface set is technically usable as evidence input for a later reviewed
`D2-IDLE` design.

This is not an idle-baseline result. It does not authorize `D2-IDLE`, a load experiment, a Short
reinterpretation or rerun, Stability, deployment, real-time or safety claims. The only action
performed after execution was review of the preserved evidence.

## Evidence identity and integrity

Evidence directory:
`evidence/phase4_0_harness/thermal_d2_preflight_20261014_01/`

Artifact SHA-256 values:

- authorization: `3b198cb715d9fcee25e99208b28c2d3edae46097f1961953eaed382b70930a95`
- `result.json`: `d61f181e905a29a281b4e16622ade165120ca3f103bd0da9adeb81596b8f6636`
- `remote_stdout.txt`: `09e64e448c90c6efedb188b9954d41433f6ca14ab38510ef7c20f417c187d564`
- `remote_stderr.txt`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `command.json`: `261d303a7e2660324263b979217724ada1034147fa48792be6520fff2c4cf2f7`

Independent checks established that:

- the authorization hash embedded in `result.json` matches the preserved authorization;
- the protocol, runner and remote-probe hashes match the readiness snapshot;
- the parsed `payload` in `result.json` is exactly equal to the JSON in `remote_stdout.txt`;
- remote return code was `0`, stderr was empty, timeout was false and no retry occurred;
- the saved command redacts the dedicated private-key path;
- the frozen probe has no file-write, OpenVINO, model, load-generation, configuration-change or
  sampling-loop code path.

The payload's protected-action fields are declarations produced by the frozen probe, not an
independent external audit. Their credibility comes from the reviewed probe code and exact hash,
not from the boolean fields alone.

## Verified target evidence

### Identity

All frozen identity checks passed:

- hostname `hepintelpc`;
- CPU `Intel(R) Core(TM) Ultra 5 225U`;
- OS `Ubuntu 24.04.4 LTS`;
- kernel `6.17.0-35-generic`;
- Python `3.12.3`;
- boot ID and uptime were present.

### Interface completeness

- 28 throttle groups were discovered: 14 core exposures and 14 package exposures;
- all 28 contained parseable count, total-time and maximum-time fields;
- no read errors were reported;
- 14 of 14 online logical CPUs exposed readable current-frequency paths;
- frequency coverage was `1.0`;
- one identifiable CPU-package temperature sensor was readable.

### One-shot values

- CPU-package temperature: `57.0 C`;
- maximum readable sensor temperature: `58.0 C`, below the `100 C` stop threshold;
- instantaneous frequency range: `400.0–4800.0 MHz`;
- maximum preserved throttle count on one path: `6094`;
- maximum preserved total-time value on one path: `122 ms`;
- maximum preserved single-time value on one path: `6 ms`.

These path values remain separate. They were not summed across CPU or package exposures.

## Evidence limitations and open gaps

### No behavior delta

The counters are cumulative within the recorded boot and were read only once. This snapshot cannot
show whether any counter increased during the probe, during the earlier Short run or during any
particular time interval. A nonzero count is historical state, not proof of a new event in this
attempt.

### Counter semantics remain unresolved

Fourteen groups had a positive count with `0 ms` total time; most were core groups, while two were
package exposures. Package fields are also exposed under every logical CPU and some duration values
repeat across paths. Readability and parseability are proven, but aliasing, sharing and the semantic
relationship between count and duration are not.

Therefore these fields must not be summed, converted into an event rate or used to infer throttle
duration until a later protocol defines before/after deltas and reviews their topology.

### Snapshot temperature and frequency are not idle evidence

The `57 C` package temperature and `400–4800 MHz` frequencies are instantaneous observations. They
do not prove a stable idle temperature, stable frequencies, absence of background activity or a
thermal cause. The SSH session, Python process and interface reads also create small diagnostic
perturbation even though no deliberate load was generated.

### Cross-host time is not aligned

The remote payload timestamp is approximately `317.5 seconds` later than the local result
timestamp, even though the result is written after the remote command returns. This is strong
evidence of an apparent host-clock offset, but the one-way snapshot does not measure the exact
offset or its stability.

Clock alignment was not a frozen PASS gate for one-shot readability, so this does not invalidate
D2-PREFLIGHT. It does prevent precise correlation of local and target events until a later design
uses a reviewed clock-alignment method or keeps timing within one monotonic target clock.

## Supported and prohibited conclusions

Supported:

- the frozen DK-2500 identity matched at this attempt;
- the required interfaces were currently readable and parseable;
- the snapshot was preserved consistently under the frozen implementation;
- the interface set is sufficient input for a later D2-IDLE design review.

Not supported:

- throttling occurred during this attempt or the earlier Short run;
- the count and duration fields describe the same event semantics;
- any particular component caused throttling;
- `57 C` is the stable idle temperature;
- frequency variation is normal, abnormal or caused by temperature;
- DK-2500 has passed thermal qualification, Stability, deployment, real-time or safety gates.

## Route and next gate

The target-evidence engineering review and learning check are complete. The human owner
demonstrated that an unchanged before/after cumulative count supports no increment within that
observed interval but does not erase historical events or identify a thermal cause. The owner also
demonstrated that cross-host timestamp subtraction includes host-clock offset and therefore cannot
be treated directly as network or inference latency. Repeated package paths remain separate because
their sharing and aliasing semantics have not been established.

A separate human decision may now authorize design of D2-IDLE. It may not authorize D2-IDLE
execution without a new frozen protocol and a later explicit execution decision.

Repository-to-Notion projection is pending and non-gating; the repository evidence and this review
remain authoritative.
