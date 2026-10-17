# Phase 4 Thermal D2-IDLE Implementation Review

Review date: `2026-10-14`

Governing protocol: `P4-DK2500-THERMAL-D2-IDLE-MOCK-001` version `0.3`

Final mock evidence:
`evidence/phase4_0_harness/thermal_d2_idle_mock_validation_20261014_03.json`

Engineering result: `PASS — NO-TARGET IMPLEMENTATION AND ARTIFICIAL-INPUT MOCK ONLY`

Learning result: `PASS`

Target execution readiness: `NOT READY — HARD-DISABLED`

Target authorization: `NONE`

Target access during implementation and mock: `NONE`

## Decision

The D2-IDLE target-side sampler source, local evidence Supervisor, artificial fixture generator and
mock validator pass the reviewed no-target implementation boundary. The implementation correctly
classifies the accepted artificial timing, activity, thermal, counter and interface cases, and the
Supervisor preserves bounded stream-failure evidence.

This is not target readiness. The production path remains deliberately disabled in code. No SSH
command, target authorization or executable D2-IDLE target protocol exists.

## Final frozen implementation identity

- protocol v0.3:
  `0f7b240f4b9da4a5e2aaf6c83d57397ef26eb1e001e93411276da8761036160a`
- target-side sampler source:
  `877b1a63df5e714ea7f6fb960b7e7b3bc103a72664da0a30a8ba677c1e484429`
- local Supervisor:
  `2a04f6b9f91d4988f59c99fae1bf537a30ab953e49b958d993641d7d8aeca7ea`
- mock validator:
  `edba7d0e0215d8f3a69b008cd18eee266c90b15b7818aa470e6d4453497e0444`
- final Round 3 evidence:
  `82cdac98bae5d5060ab805062bc4809d45724af2571a7900c9a5184165fe14a9`

Python compilation, JSON validation and the existing ten Phase 4 unit/integration tests passed.

## Implemented roles

### Target-side sampler source

- standard-library, stdout-only JSONL design;
- fixed 30-second pre-observation and 600-second formal observation;
- 127-sample, five-second target-monotonic schedule;
- per-sample inventory signature, boot ID, throttle paths, temperatures, frequencies,
  `/proc/stat`, `/proc/loadavg`, read duration and schedule lag;
- CPU-busy calculation using the frozen eight-field formula;
- pre-average, formal-average and consecutive-high activity guards;
- temperature, interface, counter, timebase and read-duration stops;
- no file-write, OpenVINO, model or deliberate-load path.

The source was not run on DK-2500 or the local host during this validation. Its actual interface
compatibility therefore remains unproven.

### Local Supervisor

- direct artificial-fixture classification;
- selector-driven nonblocking byte-stream consumption;
- startup and progress timeout structure;
- complete-line progress rule;
- partial stdout/stderr preservation;
- tolerant parsing that records damaged or incomplete JSONL tails;
- bounded `SIGTERM` then `SIGKILL` recovery path;
- independent recomputation of CPU busy and exact per-path throttle deltas;
- explicit omission of cross-path sums;
- no retry loop;
- production/target mode hard-disabled before evidence-directory creation.

### Validator

Round 3 retained the full classifier matrix and added real local child streaming. It verified:

- 127-sample quiet completion at 5% artificial busy;
- pre-observation contamination at 15%;
- three consecutive formal windows at 25%;
- complete formal average contamination at 15%;
- 100 C thermal stop;
- missing path, negative counter, boot change and monotonic reversal;
- sample read consuming the interval and missed sampling deadline;
- malformed `/proc/stat`;
- production hard-disable and fixture rejection of target arguments;
- complete streamed evidence;
- complete-line watchdog timeout with `SIGTERM`;
- partial-line watchdog timeout with `SIGTERM`, 3424 raw stdout bytes preserved and
  `INCOMPLETE_JSONL_TAIL` recorded;
- `target_accessed: false` and `execution_authorized: false` in the aggregate evidence.

## Preserved review history

Round 1 `_01` passed the classifier matrix but lacked Supervisor stream/watchdog validation. That
gap is recorded in `PHASE4_THERMAL_D2_IDLE_MOCK_ROUND1_REVIEW_20261014.md`.

Round 2 `_02` passed complete-line streaming and watchdog recovery but used blocking text
`readline()` and did not guarantee partial-line evidence preservation. That gap is recorded in
`PHASE4_THERMAL_D2_IDLE_MOCK_ROUND2_REVIEW_20261014.md`.

Neither earlier PASS is rewritten as full implementation readiness. Version `0.3` and `_03` are the
current no-target implementation evidence.

## Supported conclusions

- accepted artificial sequences are classified consistently;
- CPU-busy arithmetic and accepted control thresholds are represented in code;
- exact throttle paths remain separate and are never summed;
- local streaming progress loss, including a stalled partial line, is bounded and recoverable;
- raw partial evidence can survive the tested watchdog path;
- current target execution cannot start through the Supervisor.

## Unsupported conclusions and remaining gates

The evidence cannot establish:

- that the sampler runs correctly against DK-2500 `/proc` and `/sys`;
- that its real sampling perturbation is acceptable;
- that the frozen target identity and all 28 real throttle groups are enforced in a production
  entry gate;
- that SSH streaming, target-side termination or target-side no-write behavior works;
- any actual idle, thermal, throttle, performance, Stability, deployment or safety behavior.

Before a target execution decision, a later target protocol must bind the exact target identity,
reviewed interface inventory, SSH command, run ID, code/protocol hashes and one-attempt
authorization. Enabling the target path changes the Supervisor hash and therefore requires another
review; this mock authorization cannot be reused.

## Learning verification

Learning verification passed on `2026-10-14`.

The operator demonstrated that:

- the Round 3 result validates the implemented classification, calculation, streaming,
  watchdog and recovery logic only under artificial input and local child-process conditions;
- that result cannot establish DK-2500 interface behavior, actual idle or thermal behavior,
  SSH execution behavior, Stability, deployment readiness or physical safety;
- a pre-observation average of 8% permits entry into formal observation under the frozen rule;
- three consecutive formal windows at 21%, 23% and 22% exceed the 20% threshold and must be
  classified as `IDLE_CONTROL_CONTAMINATED`, followed by stop, evidence preservation and no
  automatic retry; and
- `IDLE_CONTROL_CONTAMINATED` means the idle control was not quiet enough to support the intended
  comparison. It is not evidence of hardware damage or a hardware fault.

This closes the learning gate for the no-target implementation and artificial-input mock. It does
not widen the engineering result or create target execution authority.

## Next gate

The next possible action is a separate human decision on whether to begin designing and freezing
an executable D2-IDLE target protocol. No target protocol design, target enabling, authorization
file, SSH or D2-IDLE execution is authorized by this review.
