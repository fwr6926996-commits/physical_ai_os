# Phase 4 CPU FP32 Stability Design Proposal

Template: `EXPERIMENT_PROTOCOL.md` version `0.1` (`TRIAL`)

Proposal date: `2026-10-14`

Proposed protocol ID: `P4-DK2500-CPU-FP32-STABILITY-002`

Classification: `QUALIFICATION — PROPOSAL ONLY`

Status: `ACCEPTED FOR NO-TARGET IMPLEMENTATION — EXECUTION NOT AUTHORIZED`

Owner: human

Governing protocol: `P4-DK2500-CPU-FP32-001`

Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`

## Question and decision

Question: can the frozen V2.9 model execute repeated synchronous inference for 30 minutes on the
recorded DK-2500 CPU FP32 backend, using the frozen input and correctness threshold, without an
inference exception, non-finite/incorrect output, process failure, watchdog timeout, thermal hard
stop or incomplete required evidence?

A passing result may admit only the recorded DK-2500 CPU FP32 **offline frozen-input repeated-call
path** for the Phase 4 engineering gate. It cannot establish changing-input behavior, the full
preprocess/control/postprocess loop, robot task success, real-time behavior, collision safety,
E-stop effectiveness, another backend or another hardware/software identity.

## Evidence entering the design

- Round 1 correctness passed on explicit DK-2500 CPU FP32.
- Round 2 Short passed its frozen correctness and execution gates.
- Short observed the 26-path thermal-throttle count pattern and did not receive performance
  admission.
- D2-IDLE produced no monitored throttle-field increment.
- D3-LOAD reproduced the same 26-path count pattern without OpenVINO/model execution, only during
  the first three five-second loaded windows; sustained load then continued without later monitored
  increments or a `100 C` stop.
- The duration fields did not provide duration evidence. Root cause remains unknown.

These results unblock Stability design and readiness review. They do not authorize Stability.

## Protected frozen candidate

The following remain unchanged from the governing protocol and configuration:

- target: DK-2500 identity `hepintelpc`, Intel Core Ultra 5 225U;
- OpenVINO: exact `2026.2.1-21919-ede283a88e3-releases/2026/2`;
- device/precision/performance hint: explicit `CPU` / `f32` / `LATENCY`;
- model XML/BIN and frozen reference tensor hashes from `phase4_frozen_config.json`;
- input: `state float32[1,6]`, `wrist_image float32[1,3,480,640]`;
- output: normalized `action_chunk float32[1,100,6]`;
- correctness: every call, `rtol=1e-4`, `atol=1e-5`;
- warmup: 10 calls;
- formal duration: 1800 seconds;
- latency window: 60 seconds;
- progress watchdog: 15 seconds without evidence growth;
- external telemetry interval: 5 seconds;
- thermal hard stop: any readable sensor `>= 100 C`;
- recovery: `SIGTERM`, five-second grace, then bounded `SIGKILL` fallback;
- physical route: strict no-touch SSH with unobstructed airflow;
- maximum attempts: one named attempt, no automatic retry or reconnect.

The Stability Worker continues to consume the already-normalized frozen model input. Unlike Short,
it does not run portable preprocessing or action postprocessing on every call. This preserves the
original Stability boundary and qualifies repeated model inference, not the full host pipeline.

## Proposed readiness changes

Only the external Supervisor, validation and evidence contract should change. The production
Worker and measured synchronous inference path should remain unchanged.

### 1. Thirty-second pre-observation

Before starting the Worker, the Supervisor should record seven samples at five-second spacing and
require:

- average aggregate CPU busy `<= 10%` across the six intervals;
- no monitored throttle-field increase;
- at the final entry sample, package temperature `<= 60 C`;
- at the final entry sample, maximum readable sensor `<= 65 C`;
- stable boot ID and thermal/frequency/throttle interface inventory;
- no read, parse, monotonic-time or counter-decrease error.

Failure produces preserved `PRECONDITION_NOT_MET_REVIEW_REQUIRED` or
`INTERFACE_OR_TIMEBASE_FAILURE_REVIEW_REQUIRED` evidence. Because target access and an evidence
attempt occurred, the named authorization is consumed and cannot be retried.

The pre-observation controls starting state; it is not a cooling-health test and does not prove the
machine is thermally safe.

### 2. Authorization and implementation binding

The production Supervisor should reject the run before Worker creation, model access or inference
unless the run-specific authorization matches:

- protocol ID/version and exact protocol SHA-256;
- run ID and `stability` stage;
- target identity and package directory;
- exact Supervisor, Worker, monitor, monitor dependency, frozen-config and pre/post implementation
  SHA-256 values;
- 30-second pre-observation, 1800-second formal duration, 15-second watchdog, 5-second telemetry,
  2100-second overall limit and no-retry policy.

The current authorization check identifies the run and stage but does not enforce these hashes.
Adding the binding prevents reviewed code/configuration from being silently replaced between
readiness and execution.

### 3. Raw thermal and resource evidence

At pre-observation and every five seconds during Worker execution, preserve a structured event with:

- target monotonic timestamp, schedule lag and interface-read duration;
- boot ID and exact interface inventory;
- all readable temperature sensors and the identified package sensor;
- all exact `throttle_count`, `throttle_total_time_ms` and `throttle_max_time_ms` fields;
- exact per-path instantaneous frequencies;
- aggregate `/proc/stat`, process RSS/thread state and system available memory.

Every throttle field is compared only with the same path. Package paths exposed through sibling
logical CPUs must not be summed. Unchanged time fields remain “no duration evidence”, not zero
duration.

`throttle_count` growth is diagnostic and requires post-run review; it is not an automatic
Stability failure. Temperature `>=100 C`, missing required interfaces, counter decrease, boot or
inventory change, or invalid sampling time is a stop/failure condition.

### 4. Overall bound and evidence-first recovery

In addition to the existing startup and per-iteration watchdogs, the Supervisor should enforce a
2100-second overall limit covering pre-observation, startup/compile, warmup, formal execution and
bounded recovery. Partial events, latencies, telemetry and stderr/stdout must be flushed and
preserved before classification. No failure class permits an automatic retry.

## Metrics and precommitted gates

Hard PASS conditions:

- target, runtime, artifacts and implementation hashes match;
- pre-observation passes;
- compile/load, initial correctness and ten warmups complete;
- formal measurement reaches at least 1800 seconds;
- every measured output has the frozen shape/dtype, is finite and passes correctness;
- inference exceptions, process crashes and progress watchdog timeouts: zero;
- observed `>=100 C` samples: zero;
- required event, latency, telemetry and structured result evidence is complete;
- independent review recomputes duration, event pairing, correctness, latency windows, resources,
  temperatures and exact-path counter changes.

Hard FAIL or stop conditions:

- identity, hash, device, shape or dtype mismatch;
- incorrect/non-finite output or inference exception;
- Worker failure, missing progress, overall timeout or failed bounded recovery;
- any readable sensor `>=100 C`;
- required interface loss, boot/inventory change, counter decrease, sampling-time failure or
  incomplete required evidence.

Diagnostic-only observations:

- latency percentiles and 60-second windows;
- RSS, available-memory, frequency and CPU-activity trends;
- throttle count/time-field changes below the thermal hard stop;
- temperature trajectory below `100 C`.

Diagnostic observations may require a separate decision but cannot silently replace the frozen
PASS/FAIL gates after execution.

## Watchdog interpretation boundary

For Stability, `infer_enter` occurs immediately before the synchronous inference path, while
`infer_return` is written only after output copy, correctness calculation, CSV flush and event
serialization. A watchdog timeout proves that one complete recorded iteration failed to return
within 15 seconds. It does not by itself prove that OpenVINO internals, the CPU plugin or hardware
caused the loss of progress.

The Supervisor remains outside the Worker and owns evidence preservation and bounded termination.
The Worker must not attempt to restart itself.

## Implementation and validation plan

1. Add pre-observation, hash-bound authorization, overall timeout and structured thermal evidence
   to `phase4_cpu_supervisor.py` without changing `phase4_cpu_worker.py`.
2. Extend local artificial tests for precondition rejection, authorization mismatch, interface
   loss, thermal stop, overall timeout, partial evidence and successful cleanup.
3. Run the existing Phase 4 unit/prepost regressions and a new no-target Stability mock.
4. Freeze exact protocol and implementation hashes.
5. Perform one no-model target preflight that verifies the deployed hashes and current interfaces;
   it must not read/compile the model or run inference.
6. Write a readiness review. Only then may the human owner decide whether to authorize one named
   Stability attempt.

## Conditions requiring a new protocol version

Changing the target, runtime, model/input, device/precision/hint, duration, thresholds, watchdog,
telemetry interval, Worker inference path, retry policy, physical setup, hard gates or evidence
contract requires a new version before execution.

## Current decision boundary

This proposal authorizes no code deployment, target preflight, model access, inference, Stability
execution, retry, deployment, real-time or physical-safety claim.

Human design acceptance is required before implementation. The critical accepted meaning must be:

1. the pre-observation makes the starting condition comparable but does not prove safety;
2. hash binding proves the authorized files match the reviewed files, not that their logic is
   correct;
3. a throttle-count increase below `100 C` remains review evidence rather than an automatic fail;
4. even a passing 30-minute result qualifies only the frozen-input offline inference boundary.

## Human design and learning review — 2026-10-14

The human owner accepted the design meaning before implementation. The owner explained that hash
binding establishes execution-file identity and accepted the additional limitation that identical
files do not prove correct logic. The owner also kept throttle-counter changes below the frozen
thermal stop as review evidence rather than an automatic Stability failure: if the precommitted
correctness, progress, duration, process, evidence and thermal gates pass, the Stability gate may
pass while thermal/performance interpretation remains separate.

This acceptance permits local implementation, artificial validation and regression only. It does
not permit DK-2500 access, file deployment, no-model target preflight, model execution or Stability.
