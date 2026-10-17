# Phase 4 Thermal Diagnosis D3-LOAD Target Protocol

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D3-LOAD-001`
- Protocol version: `0.1`
- Owner: human
- Reviewers: human owner and Codex
- Date frozen: `2026-10-14`
- Classification: `EXPLORATORY — CONTROLLED CPU-LOAD CONDITION B`
- Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`
- Control A: D2-IDLE run `thermal_d2_idle_20261014_01`
- Status: `FROZEN — READINESS REVIEW PENDING; EXECUTION NOT AUTHORIZED`

## Question and permitted decision

Question: with D2 controls held constant, is a 12-worker CPU-only load sufficient to reproduce an
increase in any exact thermal-throttle field, and what temperature, frequency and aggregate CPU
activity accompanies the interval?

The result may update the thermal diagnosis and support a later Stability-gate decision. It cannot
reproduce the OpenVINO Short workload, identify a root cause, establish hardware health, or
authorize Stability, deployment, real-time or physical-safety claims.

## Frozen target and artifacts

- target: `hepintel@192.168.77.2` via direct Ethernet;
- dedicated key: `/home/lucas/.ssh/id_ed25519_dk2500`;
- identity: `hepintelpc`, Intel Core Ultra 5 225U, Ubuntu 24.04.4 LTS,
  kernel 6.17.0-35-generic, Python 3.12.3;
- exact 28 throttle base paths and 14 frequency paths from D2-PREFLIGHT;
- shared target sampler/load-controller SHA-256:
  `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe`;
- D3 Supervisor SHA-256:
  `098142645256d454881599850343248525d5cf5ec74426b7f462c695c0367c11`;
- D3 mock validator SHA-256:
  `da9394e429f5ac3d323430477b162d1be427ae15c837cede4a628759a7998fcc`.

## Single changed variable

D2-IDLE condition A used no deliberate load. D3 condition B starts exactly 12 forked CPU workers
after the 30-second pre-observation. Each uses deterministic fixed-width integer arithmetic.
OpenVINO, models, NumPy, external stress tools, affinity, governor, fan, power and firmware changes
are prohibited.

Workers use anonymous pipes only and create no target files. Normal stops use `SIGTERM` with bounded
`SIGKILL` fallback. Every worker configures Linux parent-death `SIGTERM` so an unexpectedly lost
parent sampler cannot leave an orphan load.

## Timing, controls and gates

- pre-observation: 30 seconds, seven samples and six windows;
- formal load observation: at most 600 seconds;
- sampling interval: five seconds; maximum 127 samples through approximately 630 seconds;
- pre-observation average CPU busy: `<= 10%`;
- no pre-observation throttle-field increment;
- at load entry: package temperature `<= 60 C`, maximum sensor `<= 65 C`;
- exactly 12 workers must start and remain alive;
- formal average CPU busy: `>= 70%`;
- after two formal warmup windows, three consecutive windows below `60%` stop as load invalid;
- any readable sensor `>= 100 C` stops load immediately;
- startup timeout 30 seconds, complete-event watchdog 15 seconds, overall timeout 660 seconds;
- one attempt; retry and reconnect prohibited.

Identity, boot ID, inventory, parse, counter monotonicity, target monotonic time, sample duration and
schedule-lag rules remain identical to D2. Each throttle field is compared only with the same exact
path; cross-path sums are prohibited. A positive throttle delta is evidence, not a hard stop.

## Stop and recovery

Stop at completion or the first precondition, load-control, thermal, interface, timebase, SSH or
evidence failure. Terminate all workers before emitting the final terminal event whenever the
parent sampler remains alive. The local Supervisor terminates the SSH child on watchdog/overall
timeout; remote parent loss is backed by Linux parent-death signaling in every worker.

Partial stdout/stderr must be preserved. No stop permits a retry, alternate command, configuration
change or continuation into another phase.

## Evidence contract

- run-specific authorization bound to run ID, target, timeout values and exact protocol,
  sampler/load-controller and Supervisor hashes;
- local raw JSONL, stderr, redacted command and structured result;
- worker start PIDs, liveness, exit codes, cleanup method, iteration counts and checksums;
- all samples through completion or the first stop;
- independent recomputation of CPU busy, timing, temperatures and every throttle delta;
- separate target-evidence review before any diagnosis or Stability decision.

## Result classifications

- `LOAD_OBSERVATION_COMPLETE_REVIEW_PENDING`;
- `LOAD_CONTROL_INVALID_REVIEW_REQUIRED`;
- `PRECONDITION_NOT_MET_REVIEW_REQUIRED`;
- `THERMAL_STOP_REVIEW_REQUIRED`;
- `INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED`;
- `SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED`.

Every result is review-pending. Completion is not hardware, cooling, Stability or deployment PASS.

## Conditions requiring a new version

Change version before execution if target identity, worker count or algorithm, timing, thresholds,
hard stops, SSH route, protected boundaries, sampler, Supervisor, evidence contract, physical setup
or attempt policy changes. Never rewrite the frozen protocol after authorization or execution.

## Pre-run review

- [x] Exact implementation hashes replace placeholders.
- [x] D3 mock, D2 regression and Phase 4 tests pass.
- [x] Target mode without matching authorization fails before target access.
- [ ] Readiness review binds the frozen snapshot and one proposed run ID.
- [ ] Human separately authorizes that run.

## Deviations

None. Append deviations rather than editing frozen evidence after execution begins.
