# Phase 4 Thermal Diagnosis D2-IDLE Target Protocol

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D2-IDLE-001`
- Protocol version: `0.1`
- Owner: human
- Reviewers: human owner and Codex
- Date frozen: `2026-10-14`
- Classification: `EXPLORATORY — BOUNDED TARGET IDLE CONTROL`
- Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`
- Governing design: `PHASE4_THERMAL_D2_IDLE_DESIGN_PROPOSAL_20261014.md`
- Entry evidence: D2-PREFLIGHT run `thermal_d2_preflight_20261014_01`
- Status: `FROZEN — READINESS REVIEW PENDING; EXECUTION NOT AUTHORIZED`

## Question and decision

Question: during one bounded no-deliberate-load observation on the frozen DK-2500, do any exact
thermal-throttle paths increase, and what temperature, frequency and aggregate CPU-activity context
accompanies the interval?

The result may support review of the idle control and a later decision whether to design D3-LOAD.
It cannot explain the earlier Short result, establish a thermal root cause, qualify Stability, prove
hardware health, or authorize deployment, real-time or physical-safety conclusions.

## Frozen target and implementation

- target: `hepintel@192.168.77.2` over direct Ethernet;
- hostname: `hepintelpc`;
- CPU: `Intel(R) Core(TM) Ultra 5 225U`;
- OS: `Ubuntu 24.04.4 LTS`;
- kernel: `6.17.0-35-generic`;
- Python: `3.12.3`;
- throttle inventory: the exact 28 core/package base paths observed by D2-PREFLIGHT;
- frequency inventory: the exact 14 per-CPU paths observed by D2-PREFLIGHT;
- CPU-package temperature: at least one readable package sensor at startup and throughout the run;
- physical state: no touch, unchanged cooling and cabling, unobstructed airflow;
- remote sampler SHA-256: `ce074052dc95510bbf66d822b4d2b8233526c2654417b3bab8bd1570821e2047`;
- local Supervisor SHA-256: `07f320776ee8382401909841cfa1e6adc3f39c369bde219304bb54835f463af3`;
- no-target regression validator SHA-256:
  `a3763d1548260356f4c5686513cd013ecfbb946f7a7921b527372275cda652b4`.

The target sampler checks identity and the reviewed throttle/frequency inventories before the first
sample. A mismatch emits evidence and stops before formal observation.

## Experimental design

- condition: D2-IDLE control A, with no deliberate CPU load;
- single later A/B variable: a future D3-LOAD may add CPU load; D2 does not;
- target writes: none; the sampler source is streamed to system Python over SSH stdin;
- OpenVINO/model access: none;
- pre-observation: 30 seconds, seven samples and six CPU-busy windows;
- formal observation: 600 seconds after the precondition passes;
- interval: five seconds;
- expected unique samples: 127 through approximately 630 seconds;
- attempts: one; retry and reconnect prohibited;
- target monotonic time controls elapsed time; UTC is descriptive only.

## Metrics and gates

- pre-observation average aggregate CPU busy must be `<= 10%`;
- formal average aggregate CPU busy must be `<= 10%`;
- three consecutive formal windows each `> 20%` stop as `IDLE_CONTROL_CONTAMINATED`;
- any readable sensor `>= 100 C` stops as `THERMAL_STOP`;
- every exact throttle path is compared only with itself; paths are never summed;
- count, total-time and maximum-time deltas are preserved separately;
- `/proc/loadavg` is descriptive only;
- complete observation is `IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING`, not qualification PASS.

## Stop and recovery policy

Stop after success or the first identity, inventory, parse, counter, boot, monotonic, sampling,
activity, temperature, SSH or evidence failure. Startup timeout is 30 seconds; lack of a complete
event for 15 seconds triggers the progress watchdog; overall Supervisor timeout is 660 seconds.
The Supervisor terminates the SSH child with `SIGTERM`, then `SIGKILL` if necessary, and preserves
partial stdout/stderr. The remote sampler is intrinsically bounded to the 630-second timeline; loss
of the local SSH process does not authorize reconnect or another attempt.

The run requires a run-specific authorization whose protocol, run ID, target, timeout values and
exact protocol/Supervisor/sampler hashes all match. The authorization is single-use because the
run evidence directory must not already exist.

## Evidence contract

Local evidence only:

- raw `raw_events.jsonl` and `stderr.txt`;
- redacted `command.json`;
- structured `result.json` with independent recomputation;
- exact protocol, Supervisor, sampler and authorization hashes;
- per-path first/last/delta values without cross-path sums;
- target-evidence review before any next experiment decision.

The dedicated SSH private-key path is redacted from command evidence. No target file, package,
configuration, OpenVINO artifact or model is created or changed.

## Result classifications

- `IDLE_OBSERVATION_COMPLETE_REVIEW_PENDING`;
- `IDLE_CONTROL_CONTAMINATED_REVIEW_REQUIRED`;
- `THERMAL_STOP_REVIEW_REQUIRED`;
- `INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED`;
- `SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED`.

Every classification permits review only. None automatically authorizes D3-LOAD, Short, Stability
or deployment.

## Conditions requiring version change

Change protocol version before execution if target identity, inventories, duration, interval,
thresholds, timeout, SSH route, sampler, Supervisor, evidence contract, physical setup or attempt
policy changes. Do not edit frozen sections after authorization or execution.

## Pre-run review

- [x] Exact implementation hashes replace all placeholders.
- [x] No-target regression and existing Phase 4 tests pass.
- [x] Authorization guard fails before target access and evidence-directory creation.
- [ ] Readiness review binds the frozen snapshot.
- [ ] The human separately authorizes one named run.

## Deviations

None. Append deviations; never rewrite the frozen protocol after execution begins.
