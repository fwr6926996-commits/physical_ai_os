# Phase 4 Thermal D3-LOAD Design Proposal

Status: `PROPOSED — DESIGN REVIEW REQUIRED; IMPLEMENTATION AND EXECUTION NOT AUTHORIZED`

Date: `2026-10-14`

Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`

Control evidence:

- D2-IDLE protocol `P4-DK2500-THERMAL-D2-IDLE-001` version `0.1`;
- D2-IDLE run `thermal_d2_idle_20261014_01`;
- `PHASE4_THERMAL_D2_IDLE_TARGET_REVIEW_20261014.md`.

## Evidence question

D3-LOAD is proposed as condition B for the completed D2-IDLE condition A. It asks:

> With the same DK-2500 identity, physical setup, sampling interfaces, timing and evidence rules,
> does a controlled CPU-only load cause any exact thermal-throttle field to increase, and what
> temperature, frequency and aggregate CPU-activity context accompanies the observation?

D3 does not reproduce the OpenVINO Short workload. A positive result would show only that this
controlled CPU-load condition is sufficient to reproduce a reported throttle transition. A
negative result would show only that it was not reproduced in this one bounded condition.

## Proposed single changed variable

Condition A had no deliberate load. Condition B adds exactly one load mechanism:

- `12` independent CPU worker processes;
- each worker repeatedly performs a deterministic fixed-width integer arithmetic loop;
- Python standard library only;
- no OpenVINO, model, NumPy, external stress utility or package installation;
- no CPU affinity, governor, fan, power-profile, priority or system configuration change;
- no target file creation.

The target has 14 logical CPUs. Twelve workers should create a strong sustained CPU demand while
leaving two logical CPUs available to the sampler, SSH and ordinary system work. The theoretical
worker-to-logical-CPU ratio is approximately `85.7%`; this is a design expectation, not an observed
CPU-busy guarantee.

The arithmetic result is not a correctness workload and is not compared with Short inference. A
small final checksum per worker is diagnostic only and prevents the work from being a no-op.

## Matched D2 controls

The following remain unchanged from D2-IDLE:

- target identity, OS, kernel and Python version;
- exact 28 throttle base paths and 14 frequency paths;
- direct-Ethernet SSH route and dedicated key;
- no-touch physical setup, unchanged cooling/cabling and unobstructed airflow;
- target-monotonic timing; UTC remains descriptive only;
- 30-second no-load pre-observation;
- five-second sampling interval;
- maximum 600-second formal observation;
- maximum 127 samples through approximately 630 seconds;
- 15-second complete-event progress watchdog;
- 30-second startup allowance and 660-second Supervisor timeout;
- 100 C readable-sensor hard stop;
- one attempt, no retry or reconnect;
- local-only evidence preservation and exact per-path deltas without sums.

The worker processes start only after sample 6 completes and the preconditions pass. Formal sample
7 is the first sample after load start. All workers terminate on completion or the first stop.

## Proposed preconditions

Before starting workers:

- six pre-observation CPU-busy windows must average `<= 10%`;
- no throttle count, total-time or maximum-time field may increase during pre-observation;
- CPU-package temperature at the 30-second boundary must be `<= 60 C`;
- maximum readable sensor temperature at that boundary must be `<= 65 C`;
- target identity, boot ID and interface inventory must remain valid.

The temperature boundaries are experimental comparability controls, not vendor safety limits. In
D2-IDLE, the 30-second boundary was `49 C` package and `50 C` maximum sensor. If a D3 precondition
fails, preserve evidence and stop without starting load or retrying.

## Proposed load-control validity

Once the 12 workers start:

- every worker must remain alive until controlled shutdown;
- formal average aggregate CPU busy must be `>= 70%`;
- after the first two formal windows, three consecutive windows below `60%` classify
  `LOAD_CONTROL_INVALID` and stop;
- worker startup and shutdown events, PIDs and final checksums are evidence fields;
- a missing worker, unexpected exit or invalid CPU-busy calculation is an evidence failure.

The 70%/60% values are proposed control boundaries, not thermal or performance limits. They allow
for scheduler and system activity while distinguishing the intended high-load condition from an
under-delivered load. They require artificial-input and local-process mock validation before any
target readiness decision.

## Thermal and throttle behavior

- any readable temperature `>= 100 C` stops load immediately;
- a missing temperature, frequency or throttle path stops load;
- boot change, monotonic reversal, negative counter delta or missed sampling deadline stops load;
- a positive throttle-field delta is recorded but is not by itself a hard stop;
- count, total-time and maximum-time fields remain separate;
- repeated package exposures are never summed;
- no online interpretation changes the frozen duration or thresholds.

Keeping the maximum formal duration at 600 seconds preserves the D2 comparison window. The 100 C
hard stop and worker termination bound thermal exposure. Hardware protection behavior is not a
substitute for these software controls.

## Proposed result classifications

- `LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING` — sequence complete and load control valid;
- `LOAD_CONTROL_INVALID_REVIEW_REQUIRED` — load delivery or worker-liveness contract failed;
- `PRECONDITION_NOT_MET_REVIEW_REQUIRED` — idle/temperature/throttle entry condition failed before
  workers started;
- `THERMAL_STOP_REVIEW_REQUIRED` — readable sensor reached 100 C;
- `INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED`;
- `SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED`.

Completion is not a PASS for hardware, cooling, Stability or deployment. Throttle reproduction is
an observation inside a valid load condition, not a result-classification failure by itself.

## Evidence contract

- run-specific authorization bound to exact protocol, load-runner, sampler and Supervisor hashes;
- raw JSONL and stderr preserved locally;
- redacted SSH command record;
- load-worker start, liveness and stop events;
- all 127 samples or all samples through the first stop;
- exact per-path first/last/delta values without cross-path sums;
- independent recomputation of CPU busy, worker liveness, temperature maximum, timing and every
  throttle delta;
- separate target-evidence review before diagnosis or Stability decisions.

## Risks and protected boundaries

D3 deliberately drives sustained CPU activity and may reproduce thermal throttling or reach the
100 C software stop. It must therefore remain one bounded, supervised attempt with automatic
worker termination. No person should touch the board during execution.

The experiment may not:

- run OpenVINO or a model;
- install or invoke an external stress package;
- change affinity, governor, power profile, fan policy, firmware or cooling;
- write target evidence or source files;
- retry after precondition, load-control, thermal, interface or transport failure;
- continue into Short, Stability or deployment.

## Required gates

1. Human accepts or changes the 12-worker load, 70%/60% validity boundaries and 60/65 C entry
   temperature controls.
2. Implement the D3 target sampler/load controller and local Supervisor without target access.
3. Mock-test load startup, liveness, cleanup, under-delivery, temperature stop and partial evidence.
4. Complete engineering review; preserve exact hashes.
5. Make a separate human decision on one named target attempt.
6. After execution, review evidence before changing the diagnosis or Stability gate.

This proposal authorizes none of the implementation or execution steps by itself.
