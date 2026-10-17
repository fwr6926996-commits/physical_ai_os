# Phase 4 Thermal D2-IDLE Target Evidence Review

Protocol: `P4-DK2500-THERMAL-D2-IDLE-001` version `0.1`

Run ID: `thermal_d2_idle_20261014_01`

Review date: `2026-10-14`

Execution result: `COMPLETE — ONE AUTHORIZED ATTEMPT, NO RETRY`

Engineering review result: `PASS — BOUNDED IDLE CONTROL EVIDENCE COMPLETE`

Admission impact: `NONE — EXPLORATORY CONTROL ONLY`

Authorization beyond evidence review: `NONE`

## Decision

The single authorized D2-IDLE run completed its 30-second pre-observation and 600-second formal
observation with a complete, internally consistent evidence chain. The idle-control activity gates
passed, all 28 exact throttle groups remained readable, and none of the 84 separately compared
count/total-time/maximum-time fields increased during the bounded interval.

This establishes condition A: no new throttle-interface increment was observed during this one
bounded no-deliberate-load control. It does not show that the DK-2500 never throttles, explain the
earlier Short increment, prove hardware health, or qualify Stability or deployment.

## Frozen identity and integrity

The result contains the reviewed frozen hashes:

- protocol: `afab06716230f566c6823d50b53ad7315a54ca1cd676c64be3639c2740df77e7`;
- remote sampler: `ce074052dc95510bbf66d822b4d2b8233526c2654417b3bab8bd1570821e2047`;
- local Supervisor: `07f320776ee8382401909841cfa1e6adc3f39c369bde219304bb54835f463af3`;
- authorization: `07ed1c54b3b8c70ad1d8e6f4b9ab2838bf77fc18e3f3a9b9b478eb289f596cce`.

Evidence-file hashes:

- `raw_events.jsonl`: `693718c670aa3d2e62794917d970eca125a03d36a0ab5f2a89389586ef4d2b02`;
- `result.json`: `b0deab1e21f94a9416f9e3bb9b0ba64f0977013017c3a92b3b9d0733ef317cb9`;
- `command.json`: `17034b90de13030adb8d9cad68719ba3f44289250b72dac47532068bd6120a78`;
- `stderr.txt`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The authorization hash, implementation hashes and protocol hash match the current frozen files.
The command record redacts the SSH private-key path. Remote return code was `0`, stderr was empty,
no timeout, recovery, JSON parse error, reconnect or retry occurred.

## Independently verified sequence

- events: 129 — one runtime identity, 127 samples and one completion event;
- final target-monotonic elapsed time: `630.00016148 seconds`;
- adjacent sample intervals: `4.999891325–5.000179833 seconds`;
- maximum schedule lag: `0.206196 ms`;
- maximum interface-read duration: `7.213041 ms`;
- boot IDs observed: one;
- inventory signatures observed: one;
- classification reasons: none.

The raw `/proc/stat` fields were independently recomputed for all 126 windows and exactly matched
the reported aggregate CPU-busy values.

## Idle-control evidence

- pre-observation average aggregate CPU busy: `0.0285727905%`, below `10%`;
- formal-observation average aggregate CPU busy: `0.0245304448%`, below `10%`;
- maximum single-window aggregate CPU busy: `0.0714285714%`;
- no three consecutive windows exceeded `20%`;
- maximum load-average values were `0.08 / 0.03 / 0.01` and remain descriptive only.

The run therefore satisfies the precommitted operational definition of this idle control. These
numbers are experiment-control evidence, not a universal definition of an idle or healthy system.

## Thermal and frequency context

- maximum readable sensor temperature: `78 C`, at sample 0 on `Core 8`;
- CPU-package temperature at sample 0: `76 C`;
- at sample 1, five seconds later, the maximum readable sensor was `53 C`;
- CPU-package temperature across the run: minimum `45 C`, mean `49.315 C`, maximum `76 C`;
- final CPU-package temperature: `50 C`;
- observed instantaneous frequency range: `400.0–4801.42 MHz`;
- mean of all instantaneous per-path frequency readings: `1053.502 MHz`.

The initial temperature peak is preserved as a transient observation. It remained below the
precommitted `100 C` hard stop and did not coincide with a throttle-field increment. This run does
not establish its cause, whether it is normal, or a hardware-health limit.

## Throttle evidence

For each of 28 exact base paths, `throttle_count`, `throttle_total_time_ms` and
`throttle_max_time_ms` were compared only with the same path:

- fields compared: 84;
- positive deltas: 0;
- zero deltas: 84;
- negative deltas: 0;
- cross-path sums: intentionally omitted.

The supported statement is: no monitored throttle field increased during this 630-second D2-IDLE
interval. Historical nonzero counters remain historical facts and are not reset or disproven.

## Design–reality update

The earlier Short run observed new throttle-counter increments while model inference was active.
D2-IDLE did not reproduce an increment when deliberate load, OpenVINO and the model were absent.
This narrows the investigation: the idle condition alone did not reproduce the earlier symptom in
this one attempt.

It does not isolate which missing factor matters. CPU load, OpenVINO/model work, temperature
history, timing and other Short-specific conditions remain bundled in the earlier observation. A
causal statement requires a later controlled condition B, not comparison by narrative alone.

## Supported and prohibited conclusions

Supported:

- the frozen target and interfaces passed the startup contract for this attempt;
- the evidence sequence and idle control were complete under the frozen protocol;
- none of the monitored throttle fields increased during this interval;
- the result is suitable as condition A for considering a controlled D3-LOAD design.

Not supported:

- the DK-2500 never throttles at idle;
- the earlier Short increment was caused by OpenVINO, model inference or CPU load;
- `78 C` is normal, abnormal, safe or unsafe for this hardware;
- the cooling system or hardware is healthy or defective;
- Phase 4 Stability, deployment, real-time or physical-safety readiness.

## Route and next gate

D2-IDLE experimental work and target-evidence review are complete. No repeat is justified under the
current protocol. The next possible action is a separate human decision whether to design D3-LOAD
as condition B with deliberate CPU load as the single changed variable and the other D2 controls
held constant.

This review does not authorize D3 design, implementation or execution, and it does not authorize
Stability or deployment.
