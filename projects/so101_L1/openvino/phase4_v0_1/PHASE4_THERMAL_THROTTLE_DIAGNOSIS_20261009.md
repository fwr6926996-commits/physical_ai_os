# Phase 4 Thermal Throttle Diagnosis

Diagnosis ID: `P4-DK2500-THERMAL-20261009-01`

Owner: human

Affected run: `phase4_r2_short_20261008_01`

Status: `NARROWED — LOAD-ENTRY COUNT SIGNAL REPRODUCED; ROOT CAUSE UNKNOWN`

Current disposition date: `2026-10-14`

Current next gate: `STABILITY DESIGN AND READINESS REVIEW — EXECUTION NOT AUTHORIZED`

## Identity and impact

The Short hard gates passed, but thermal throttle counters increased during the approximately
14-second supervised CPU FP32 run. The observation prevents a steady-state performance claim and
requires a reviewed diagnostic evidence plan before Stability authorization. It does not
retroactively fail Short or establish a hardware defect.

## Observed facts

- The run completed 111/111 calls without correctness, process or watchdog failure.
- Package and maximum-sensor telemetry reached `91 C` and `92 C`; the frozen `100 C` software stop
  did not trigger.
- Twenty-six exposed core/package throttle-counter paths increased between the Supervisor's before
  and after snapshots.
- A later five-second idle control recorded zero increments across 28 paths and temperature recovery
  to approximately `40-43 C`.
- No kernel journal entry was present in the run window.
- The target exposes `core/package_throttle_count`, `*_total_time_ms` and `*_max_time_ms`, but the
  Short harness recorded before/after values only for the count fields.
- Inference mean decreased across the four measurement quartiles rather than increasing.

Official interpretation baseline:

- Linux documents `core_throttle_count` and `package_throttle_count` as transitions of Thermal
  Status from zero to one. It states that the counters can show whether performance was limited by
  thermal events and that package status is broadcast to all CPUs:
  <https://origin.kernel.org/doc/html/latest/admin-guide/thermal/intel_thermal_throttle.html>
- Intel documents Thermal Monitor Status as indicating that the thermal monitor has tripped and is
  currently throttling:
  <https://edc.intel.com/content/www/de/de/design/publications/14th-generation-core-processors-cfg-and-mem-registers/thermal-status-gt-therm-status-gt-0-0-0-mchbar-pcu-offset-59c0/>

## Execution chain

```text
CPU FP32 short load -> package/core temperature and power state
                    -> hardware thermal monitor transitions
                    -> Linux thermal-throttle counters increase
                    -> possible performance limiting
```

## Fault boundary

- Narrowest supported boundary: thermal-monitor throttling events occurred during the bounded CPU
  load window.
- Components inside the open boundary: workload power behavior, CPU thermal monitor, cooling path,
  firmware/platform thermal policy and Linux reporting.
- Not yet implicated: a particular OpenVINO operator, defective CPU, incorrectly mounted heatsink,
  inadequate adapter, kernel fault or robot workload.
- Current evidence cannot prove event duration, precise trigger temperature, duty cycle, causal
  component or physical defect.

## D2/D3 evidence addendum — 2026-10-14

The bounded follow-up plan has now completed its artificial-interface gate, target preflight,
idle control and one authorized CPU-only load control:

- D2-IDLE completed 630 seconds without an increase in any of the 84 separately monitored
  count/total-time/maximum-time fields.
- D3-LOAD completed with 12 arithmetic workers and `85.772%` average aggregate CPU busy.
- D3 reproduced positive `throttle_count` deltas on exactly the same 26 paths as Short without
  using OpenVINO or the model.
- The D3 count changes were confined to the first three five-second loaded windows. Approximately
  585 seconds of continued load produced no later monitored counter increment.
- D3 reached `91 C`, remained below the frozen `100 C` stop and recovered all 12 workers.
- All 28 `throttle_total_time_ms` and all 28 `throttle_max_time_ms` fields remained unchanged.
  This supplies no duration evidence; it does not establish zero duration.

The new evidence establishes that CPU-only load is sufficient for the monitored count pattern and
that OpenVINO/model execution is not necessary for it to occur. It does not prove a thermal,
power, firmware, kernel, cooling or hardware root cause. The temperature/frequency/count sequence
is consistent with a rapid platform operating-point transition after load entry, but the
responsible controller and underlying condition remain unknown.

The duration-field semantics and update behavior are routed to bounded source and official
interface research. Repeating D3 is not justified. The diagnosis no longer blocks Stability
**design and readiness review**, provided the existing external supervision, `100 C` hard stop,
raw thermal/counter evidence, bounded recovery, named-run authorization and no-automatic-retry
rules remain protected. Stability execution is not authorized by this disposition.

Primary target review:
`PHASE4_THERMAL_D3_LOAD_TARGET_REVIEW_20261014.md`.

## Hypothesis matrix

| Hypothesis | Supporting evidence | Contradicting/insufficient evidence | Status | Next discriminating check |
|---|---|---|---|---|
| Current cooling/platform policy permits brief thermal-monitor events under the CPU workload | `91-92 C` samples, load-window count growth, idle zero-growth control | No run-window duration counters; no direct fan RPM | OPEN | Capture before/after count, total-time and max-time fields with denser temperature context |
| Short spikes crossed an internal trip between five-second samples | Counter semantics and sparse telemetry permit missed peaks | No time-aligned status or sub-second sample | OPEN | Bounded read-only sampling design outside the measured pipeline |
| Counter growth is a reporting/driver artifact rather than hardware thermal transitions | Very large count deltas and duplicate package paths require careful interpretation | Official Linux semantics identify Thermal Status transitions; idle control did not grow | OPEN, LOWER PRIORITY | Check current kernel implementation/known platform behavior and time counters |
| The events alone prove a cooling hardware fault | None | Correct completion, temperature recovery and missing causal evidence | REJECTED AS CURRENT CONCLUSION | Requires physical and comparative evidence before reopening |

## Diagnostic plan — proposal only

1. Do not rerun Short and do not start Stability.
2. Extend external, non-model evidence capture to record before/after `count`, `total_time_ms` and
   `max_time_ms` fields without adding writes inside the measured Worker pipeline.
3. Mock-test parsing, missing-interface handling and evidence preservation.
4. Establish a bounded idle control and one separately reviewed exploratory CPU-load control with
   the same physical setup; freeze its maximum attempts and `100 C` stop before execution.
5. Decide from duration and control evidence whether the phenomenon is brief expected protection,
   sustained thermal limitation requiring cooling action, or still unresolved.
6. Only then present the unchanged 30-minute Stability protocol for a new human decision, or amend
   it explicitly if the evidence requires different telemetry or stop rules.

The first diagnostic mechanism gate is specified in
`PHASE4_THERMAL_D1_MOCK_PROTOCOL_20261010.md`. D1 uses artificial input only and has no target
reading mode. `D2-PREFLIGHT` interface feasibility, `D2-IDLE` observation and any later `D3-LOAD`
control remain undesigned and unauthorized until their learning and protocol reviews are completed.

The proposed one-shot target-interface gate is drafted in
`PHASE4_THERMAL_D2_PREFLIGHT_PROTOCOL_20261013.md`. It is not frozen and does not authorize target
access.

No diagnostic command or experiment is authorized by this document.

## Original conclusion before D2/D3 addendum

Confirmed root cause: none.

Current classification: `THERMAL_THROTTLING_EVENTS_OBSERVED_DURING_SHORT_LOAD`.

Bounded disposition at that time: Short passed its frozen hard gates; no performance admission;
Stability remained blocked pending review and authorization of the diagnostic plan.

## Current conclusion after D2/D3 addendum

Confirmed root cause: none.

Current classification:
`CPU_ONLY_LOAD_SUFFICIENT_FOR_TRANSIENT_THROTTLE_COUNT_PATTERN_DURATION_UNKNOWN`.

Current bounded disposition: the exploratory thermal diagnosis is complete enough to unblock
Stability design and readiness review. It does not authorize Stability execution, provide a
steady-state performance admission, establish hardware health or change the `100 C` stop rule.
