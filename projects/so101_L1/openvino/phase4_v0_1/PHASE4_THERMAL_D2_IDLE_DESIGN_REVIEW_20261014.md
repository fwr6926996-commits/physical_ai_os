# Phase 4 Thermal D2-IDLE Design Review

Review date: `2026-10-14`

Reviewed proposal: `PHASE4_THERMAL_D2_IDLE_DESIGN_PROPOSAL_20261014.md`

Engineering design result: `PASS — BOUNDED IDLE-CONTROL DESIGN`

Learning result: `PASS`

Implementation authorization: `NONE`

Target execution authorization: `NONE`

## Decision

The D2-IDLE evidence question, A/B role, target-local time model, activity guard, sampling timeline,
stop rules and claim boundaries are accepted as the basis for a later implementation decision.

This review does not freeze an executable protocol. It does not authorize code implementation,
mock execution, SSH, target sampling, D3-LOAD, Stability or deployment.

## Accepted experiment role

- D2-IDLE is condition A: no deliberate CPU load.
- A possible later D3-LOAD is condition B: deliberate CPU load is the intended single changed
  variable.
- D2-IDLE can establish only a bounded no-deliberate-load control. It cannot explain the earlier
  Short result by itself.

## Accepted timing and sampling design

- target `time.monotonic_ns()` is the duration authority;
- target UTC and local receive time are descriptive only;
- pre-observation: `30 seconds`, 7 samples and six five-second activity windows;
- formal observation: `600 seconds`, 121 samples, reusing the final pre-observation sample as the
  formal initial sample;
- complete sequence: 127 unique samples through approximately `t=630 seconds`;
- sampling interval: `5 seconds`;
- progress watchdog: `15 seconds` without a complete sample;
- startup allowance: `30 seconds` before the first sample;
- maximum evidence-producing attempts: one;
- automatic retry and reconnect: prohibited.

The target-local monotonic clock prevents the approximately `317.5-second` cross-host wall-clock
offset from being misreported as sampling, network or inference duration.

## Accepted activity guard

CPU busy percentage will be calculated from consecutive aggregate `/proc/stat` snapshots. The
exact field formula and boundary cases must be frozen in the implementation protocol and validated
with artificial input before any target access.

Accepted operational limits:

- pre-observation average busy must be `<= 10%` before formal observation begins;
- formal-observation average busy must be `<= 10%` for a valid idle control;
- three consecutive five-second windows each above `20%` cause early
  `IDLE_CONTROL_CONTAMINATED` classification and stop;
- a formal sequence whose final average exceeds `10%` is also classified as contaminated;
- `/proc/loadavg` is descriptive context only;
- contamination is not a hardware failure and never authorizes automatic retry.

The limits are experimental control boundaries, not vendor specifications or universal idle
criteria.

## Accepted evidence and stop boundaries

- preserve every throttle path independently and never sum repeated package exposures;
- compute first/last delta for each exact path;
- preserve count/duration disagreements without repair;
- record temperature, frequency, host activity, boot ID, monotonic timing, read duration and read
  errors at each sample;
- stop on target identity drift, path-set drift, missing fields, boot change, negative counter
  delta, monotonic reversal, watchdog expiry, a sample consuming the full interval, any readable
  temperature `>= 100 C`, protected-boundary violation, SSH loss or local evidence-write failure;
- preserve partial evidence after every stop;
- write no target file and run no OpenVINO, model or deliberate load.

## Learning verification

The human owner demonstrated that:

- D2-IDLE is the A control and future deliberate CPU load is the intended B variable;
- wall-clock UTC can differ between hosts or jump during synchronization;
- target-local monotonic time is therefore required for elapsed-time calculation;
- an idle control needs a precommitted activity limit rather than an after-the-result label.

## Remaining gates

The only permissible next decision is whether to authorize implementation of the sampler,
Supervisor and artificial-input mock tests. That implementation decision must still prohibit target
access.

After implementation, engineering and learning reviews must pass before an executable D2-IDLE
protocol and separate one-attempt target authorization can be considered.
