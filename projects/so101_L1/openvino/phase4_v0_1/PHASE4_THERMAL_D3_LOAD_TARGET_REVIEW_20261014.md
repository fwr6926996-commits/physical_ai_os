# Phase 4 Thermal D3-LOAD Target Evidence Review

Protocol: `P4-DK2500-THERMAL-D3-LOAD-001` version `0.1`

Run ID: `thermal_d3_load_20261014_01`

Review date: `2026-10-14`

Execution result: `COMPLETE — ONE AUTHORIZED ATTEMPT, NO RETRY`

Engineering review result: `PASS — BOUNDED D3 EVIDENCE COMPLETE; COUNT TRANSITION REPRODUCED`

Diagnosis impact: `NARROWED — CPU-ONLY LOAD IS SUFFICIENT FOR THE OBSERVED COUNT SIGNAL`

Admission impact: `NONE — EXPLORATORY CONTROL ONLY`

Learning result: `PASS`

Authorization beyond evidence review: `NONE`

## Decision

The single authorized D3-LOAD attempt completed its 30-second pre-observation and 600-second
formal observation with a complete evidence chain. Twelve arithmetic workers delivered an average
aggregate CPU busy value of `85.772%`, the target remained below the frozen `100 C` hard stop and
all workers were stopped and collected.

Under this controlled CPU-only condition, `throttle_count` increased on the same 26 exact paths
that had nonzero deltas in the earlier Short run. D2-IDLE had produced no increments. The supported
answer to the frozen D3 question is therefore **yes**: this CPU-only load was sufficient to
reproduce the monitored counter signal without OpenVINO or the model.

This is not a root-cause result. It does not show why the platform entered the reported state,
whether thermal, power, firmware or another control produced the operating-point change, or how
long individual limiting intervals lasted.

## Frozen identity and integrity

The result contains and matches the reviewed frozen hashes:

- protocol: `a3f5b60a84f8f1d67eb7daaf030d660663766cd8acd5fc012174014f78ca0763`;
- remote sampler/load controller:
  `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe`;
- local Supervisor: `098142645256d454881599850343248525d5cf5ec74426b7f462c695c0367c11`;
- authorization: `c9082cef198e307465509bffde17b910766823690be74449807a8f5a4982e221`.

Preserved evidence-file hashes:

- `raw_events.jsonl`: `772ea0f34451d9188f47047f9e30e05a16aca19b848d263772e73dfc393d7a22`;
- `result.json`: `093ea7cce4a2d8ba6df8e761a95aa6f837c46c441167586d4a2b85cfac501324`;
- `command.json`: `c85551c9f3ef2352b988514e4bfc78672a7238e54a8604a4343cc5b5919dd2c3`;
- `stderr.txt`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The command record redacts the dedicated SSH-key path. Remote return code was `0`, stderr was
empty, and no timeout, recovery, parse error, reconnect or retry occurred.

## Independently verified sequence

- events: 131 — one runtime identity, one load start, 127 samples, one load stop and one completion;
- final target-monotonic elapsed time: `630.000068488 seconds`;
- adjacent sample intervals: `4.999890529–5.000158124 seconds`;
- maximum schedule lag: `0.186616 ms`;
- maximum interface-read duration: `17.044042 ms`;
- boot IDs observed: one;
- inventory signatures observed: one;
- samples with read errors: zero;
- raw `/proc/stat` windows independently recomputed: 126, with zero mismatches.

The pre-observation average CPU busy value was `0.01905%`. At the formal boundary the package
temperature was `48 C`, the maximum readable sensor was `51 C`, and no pre-observation throttle
field had increased. All frozen entry conditions passed.

## Load-control and cleanup evidence

- requested and started workers: `12/12`;
- formal CPU busy: minimum `85.741%`, mean `85.772%`, maximum `85.998%`;
- formal windows below `60%`: zero;
- stopped workers still alive after cleanup: zero;
- worker exit codes: `12/12` equal to `0`;
- worker records: `12/12`, each with an iteration count and checksum;
- cleanup method: bounded `SIGTERM`; `SIGKILL` fallback was not needed.

This verifies the D3 load-control contract for this attempt. It does not qualify the controller for
deployment or prove behavior under an unrelated parent, network or kernel failure.

## Thermal, frequency and counter evidence

The maximum readable temperature was `91 C`, below the frozen `100 C` stop. The package sensor
ranged from `48 C` to `91 C`; the run-wide package mean was `59.213 C`. The maximum occurred in
the first two formal samples, five and ten seconds after load entry.

Counter changes were time-localized by the five-second samples:

- sequences 7, 8 and 9, covering the first 15 seconds after load entry, each contained increases
  on 26 exact `throttle_count` paths;
- no later sample through the remaining approximately 585 seconds contained another monitored
  throttle-field increase;
- 26 of 28 exact count paths increased from the formal boundary to completion;
- the two zero-delta paths were the `cpu12` and `cpu13` core-count paths;
- all 28 `throttle_total_time_ms` paths and all 28 `throttle_max_time_ms` paths had zero delta.

Package paths exposed under multiple logical CPUs are retained separately and are not summed or
interpreted as independent physical events.

Instantaneous frequency samples ranged from `400.0` to `4800.217 MHz`. During the first two loaded
samples, per-path frequency means were approximately `2912` and `2847 MHz` while the package was
`91/90 C`; at the third loaded sample the mean was approximately `1350 MHz` and the package was
`56 C`, while aggregate CPU busy remained approximately `85.76%`.

The temperature, frequency and count changes are consistent with a rapid platform operating-point
transition after load entry. They do not identify which controller requested it or prove that every
frequency reduction was caused by the thermal monitor.

## Count/time-field evidence conflict

The count fields changed while the exposed total-time and maximum-time fields did not. Both facts
are preserved. The review must not turn unchanged time fields into a measured zero-duration event,
and it must not derive duration by dividing, summing or otherwise transforming duplicated count
paths.

The run can localize count transitions to three five-second observation windows. It cannot measure
the duration of the underlying limiting state within those windows. The semantics and update
behavior of the time fields on this kernel/platform remain an interface question and should be
routed to source/official-document research rather than another unfrozen target run.

## Comparison with D2-IDLE and Short

- D2-IDLE condition A: no deliberate load and zero increases across all 84 monitored fields.
- D3-LOAD condition B: 12 CPU workers and increases on 26 count paths, with zero time-field deltas.
- Phase 4 Short: increases on the same 26 count paths while CPU FP32 OpenVINO inference was active.

Because D3 changed the deliberate CPU load condition and reproduced the same nonzero path set
without OpenVINO or the model, OpenVINO/model execution is not necessary for this counter pattern
to occur. This does not prove that generic CPU load is the only cause of the Short observation or
that the two runs had identical internal platform states.

## Design–reality update

The earlier diagnosis left CPU load, OpenVINO/model behavior, cooling, firmware policy and counter
reporting bundled together. D2 and D3 now separate one part of that bundle:

1. the idle control did not reproduce the signal;
2. the CPU-only load did reproduce the same path pattern;
3. the D3 signal occurred only at load entry rather than throughout sustained load;
4. the duration fields did not supply valid duration evidence.

The evidence supports a bounded interpretation of transient load-entry thermal/power-management
behavior. It rejects neither a platform-policy explanation nor a cooling contribution, and it does
not establish a defect.

## Supported and prohibited conclusions

Supported:

- the frozen target, interfaces, load controller and evidence chain completed for this attempt;
- CPU-only load was sufficient to reproduce the monitored 26-path count pattern;
- the observed count changes were confined to the first three five-second loaded windows;
- sustained load continued without later monitored count increments or a `100 C` stop;
- all load workers were recovered cleanly.

Not supported:

- an exact throttle duration or duty cycle;
- a proven thermal, power, firmware, kernel, cooling or hardware root cause;
- a claim that the unchanged time fields mean no limiting occurred;
- a claim that arithmetic load and OpenVINO inference are internally identical;
- hardware-health, steady-state performance, Stability, deployment, real-time or physical-safety
  admission.

## Route and proposed next gate

D3 execution is complete and must not be repeated under the consumed authorization. The
`throttle_total_time_ms`/`throttle_max_time_ms` behavior is routed to bounded source and official
interface research; no additional target experiment is presently justified for that question.

Subject to human interpretation acceptance, the thermal diagnosis no longer needs to block the
**design and readiness review** of the existing CPU FP32 Stability stage. Stability execution
remains separately gated and must retain external supervision, the frozen `100 C` stop, raw
counter/temperature evidence, bounded recovery, one named run and no automatic retry. D3 does not
itself authorize or pass Stability.

Before that route is accepted, the human owner should be able to explain:

1. why the D3 count result answers a sufficiency question but not a root-cause question;
2. why unchanged time fields cannot be reported as zero throttle duration;
3. why the first-15-second localization does not mean each event lasted 15 seconds;
4. what remains separately required before Stability can execute.

## Human learning verification

The human owner correctly distinguished sufficiency from root cause: the CPU-only load and count
changes were observed together, while thermal management, power management and firmware policy
remain possible explanations inside the unresolved mechanism boundary.

The owner also explained that five-second observation windows localize when a change was detected
but do not establish that an event lasted for all three windows. For the conflicting duration
fields, the accepted statement is: no duration evidence was produced; the duration is unknown and
must not be reported as zero.

Finally, the owner retained human control of the next gate: current facts and material experiment
inputs must be frozen, the Stability protocol and readiness must be reviewed, and a named execution
must receive separate authorization. Learning verification therefore passes without authorizing
Stability execution.
