# Phase 4 Thermal D2-IDLE Design Proposal

Status: `DESIGN REVIEWED — IMPLEMENTATION NOT AUTHORIZED — EXECUTION NOT AUTHORIZED`

Date: `2026-10-14`

Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`

Entry evidence:

- `PHASE4_THERMAL_D2_PREFLIGHT_TARGET_REVIEW_20261014.md`
- run `thermal_d2_preflight_20261014_01`

## Purpose and evidence question

D2-IDLE is the no-deliberate-load control for a possible later D3-LOAD comparison. It asks:

> During one bounded observation on the frozen DK-2500, with no OpenVINO, model or deliberate CPU
> load, do the preserved per-path thermal-throttle counters change, and what temperature, frequency
> and host-activity context accompanies those changes?

D2-IDLE does not investigate an internal OpenVINO cause and cannot by itself explain the earlier
Short result. It establishes condition A only. A later D3-LOAD would be condition B, with deliberate
CPU load as the single changed variable and all other material conditions held constant.

## Why D2-PREFLIGHT is insufficient

D2-PREFLIGHT proved one-shot readability. Its nonzero fields are cumulative values within the
recorded boot. One sample has no before/after delta and cannot show whether a value changed in the
observed interval.

D2-IDLE must therefore preserve a bounded sequence and calculate each path's delta from its own
first and last values. It must never sum values from repeated package exposures.

## Proposed controlled architecture

```text
Local Supervisor
  -> one bounded SSH session
    -> one target-side read-only sampler process
      -> target monotonic timestamp + one interface snapshot per interval
      -> JSONL streamed to stdout only
  -> raw evidence written only on the local machine
```

The target sampler should discover the interface inventory once, emit that inventory, and then read
the same frozen paths for the rest of the run. A missing, added or unparseable path after start is an
evidence failure rather than a zero value.

## Accepted design constants

These constants were accepted for the implementation design. They are not an execution protocol or
target authorization:

- target and software identity: same strict fields as D2-PREFLIGHT;
- target file writes: none;
- OpenVINO/model access: none;
- deliberate CPU load: none;
- physical setup: strict no-touch, unchanged cooling and cabling;
- operator activity on DK-2500: none during the observation;
- pre-observation duration: `30 seconds`;
- formal-observation duration: `600 seconds` after pre-observation passes;
- maximum sampling timeline after the first sample: `630 seconds`;
- sampling interval: `5 seconds`;
- expected unique samples: `127` from approximately `t=0` through `t=630 seconds`;
- pre-observation samples: `7`, defining six five-second CPU-busy windows;
- formal-observation samples: `121`, reusing the `t=30-second` sample as its first sample;
- progress watchdog: `15 seconds` without a complete sample;
- overall startup allowance: `30 seconds` before the first sample;
- thermal hard stop: any readable sensor `>= 100 C`;
- maximum evidence-producing attempts: one;
- automatic retry or reconnect: prohibited.

The five-second interval matches the existing Phase 4 external-telemetry cadence and limits probe
traffic. The ten-minute formal observation, after the 30-second activity guard, is proposed as a
bounded exploratory baseline, not as stability qualification or proof of long-term idle behavior.

## Time model

Every target sample should record:

- target `time.monotonic_ns()` before and after interface reads;
- target UTC as descriptive context only;
- elapsed time derived only from the target monotonic clock;
- sample-read duration;
- scheduled versus actual sample index;
- boot ID.

Local receive time may be recorded for transport diagnosis but must not be subtracted from target
UTC to claim inference, sampling or network latency. The approximately `317.5-second` apparent
host-clock offset observed in D2-PREFLIGHT makes cross-host wall-clock subtraction invalid without a
separate alignment method.

The boot ID must remain unchanged during the run. A monotonic timestamp reversal, boot-ID change,
missed sample deadline or sample-read duration reaching the full interval invalidates the time
series.

## Per-sample evidence

Each JSONL sample should preserve:

- sample sequence and target monotonic time;
- target UTC and boot ID;
- every frozen throttle count, total-time and maximum-time path;
- all readable temperatures and the identified package temperature;
- all frozen CPU current-frequency paths;
- `/proc/stat` CPU totals needed to calculate interval busy percentage;
- `/proc/loadavg` as descriptive context;
- sample-read duration and read errors.

No process list, unrelated environment variables, network identifiers or storage identifiers are
needed.

## Delta and topology rules

For every exact path, preserve:

- first value;
- last value;
- delta;
- whether the delta is negative, zero or positive.

Summaries may report the number of paths with positive deltas and the minimum/maximum individual
path delta. They must state that summation was intentionally omitted.

A positive `core_throttle_count` or `package_throttle_count` delta supports that Linux reported
thermal-status transitions during the bounded interval. It does not identify the cause, exact trip
temperature, performance loss or hardware defect.

The `total_time_ms` and `max_time_ms` fields remain diagnostic because their relationship to count
and the repeated package topology is not yet established. A count increase with zero duration
increase must be preserved as an observed mismatch, not repaired or discarded.

## Idle-control validity — selected design

"No deliberate load" is necessary but not sufficient to prove an actually quiet host. D2-IDLE
must also capture interval CPU busy percentage and load average. The human owner selected a
precommitted activity guard rather than a descriptive-only control.

The selected operational definition is:

- use the first `30 seconds` as pre-observation rather than formal idle evidence;
- require pre-observation average aggregate CPU busy percentage `<= 10%` before measurement begins;
- require formal-observation average aggregate CPU busy percentage `<= 10%`;
- classify and stop as `IDLE_CONTROL_CONTAMINATED` after three consecutive five-second windows each
  exceed `20%` aggregate CPU busy;
- preserve all partial evidence and do not retry automatically;
- record `/proc/loadavg` as descriptive context, not as a CPU-busy percentage or hard gate.

Aggregate CPU busy percentage must be calculated from consecutive `/proc/stat` total and idle-field
deltas. The formula and boundary cases require no-target mock validation before implementation can
be considered ready.

The `10%` and `20%` values are precommitted experimental control boundaries, not vendor limits,
hardware-health criteria or universal definitions of idle. They prevent a materially busy host from
being silently described as the no-load control while tolerating short background activity.

## Accepted design hard stops

- target identity mismatch;
- interface inventory differs from the reviewed start inventory during sampling;
- missing or unparseable required field;
- boot ID changes or a counter delta becomes negative;
- target monotonic time reverses;
- no complete sample for `15 seconds`;
- a sample read consumes the complete `5-second` interval;
- any readable temperature reaches `100 C`;
- deliberate load, OpenVINO/model access, target write or system change occurs;
- SSH loss or Supervisor evidence-write failure.

After any stop, preserve partial evidence and terminate the remote sampler through the local
Supervisor. Do not reconnect or restart automatically.

## Proposed result classifications

- `IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING`: sequence and evidence contract complete;
- `IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED`: precommitted activity guard violated;
- `THERMAL_STOP_REVIEW_REQUIRED`: temperature hard stop reached;
- `INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED`: path, counter, boot or monotonic contract failed;
- `SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED`: progress, SSH or evidence preservation failed.

Completion is not thermal qualification. Every result remains review-pending.

## Evidence contract proposal

- one run-specific authorization bound to frozen hashes;
- local command record with SSH key path redacted;
- raw target JSONL stream;
- raw stderr;
- structured result with per-path deltas and no package summation;
- exact protocol, supervisor and sampler hashes;
- independent recomputation of sample count, timing, temperature maximum, activity metrics and every
  path delta;
- separate target-evidence Review;
- separate learning verification before any D3-LOAD design decision.

## Claims explicitly prohibited

D2-IDLE cannot establish:

- why the earlier Short run throttled;
- whether OpenVINO caused a thermal event;
- normal or defective cooling hardware;
- exact throttle duration or performance loss unless the interface semantics are separately
  validated;
- loaded thermal behavior;
- Stability readiness;
- deployment, real-time or physical safety.

## Design gates remaining

1. Human review of the A/B role and time model. `COMPLETE — LEARNING PASS`
2. Human selection and justification of idle-validity policy. `COMPLETE — OPTION B ACCEPTED`
3. Freeze the duration, interval, watchdog and remaining stop rules. `COMPLETE — DESIGN ACCEPTED`
4. Implement target sampler and local Supervisor without target access.
5. Validate timing, counter-delta, activity, missing-path and stop behavior using artificial input.
6. Complete independent engineering and learning reviews.
7. Only then present a separate D2-IDLE execution decision.

This proposal authorizes none of those implementation or execution steps by itself.
