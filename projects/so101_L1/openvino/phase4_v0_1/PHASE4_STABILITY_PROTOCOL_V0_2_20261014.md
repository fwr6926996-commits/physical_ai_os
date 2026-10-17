# Phase 4 DK-2500 CPU FP32 Stability Protocol

Template version: `0.1` (`TRIAL`)

Protocol ID: `P4-DK2500-CPU-FP32-STABILITY-002`

Protocol version: `0.2`

Date frozen: `2026-10-14`

Classification: `QUALIFICATION`

Status: `FROZEN DESIGN — IMPLEMENTATION AND READINESS PENDING; EXECUTION NOT AUTHORIZED`

Owner: human

Governing protocol: `P4-DK2500-CPU-FP32-001`

Governing diagnosis: `P4-DK2500-THERMAL-20261009-01`

## Question and claim boundary

Determine whether the frozen V2.9 model can complete 30 minutes of repeated synchronous inference
on the recorded DK-2500 CPU FP32 backend, using the frozen input and correctness threshold, without
an inference exception, incorrect/non-finite output, process failure, watchdog timeout, thermal
hard stop or incomplete required evidence.

A pass admits only this offline frozen-input repeated-inference boundary. It cannot establish
changing-input or full host-pipeline behavior, robot task success, real-time control, physical
safety, hardware health, another backend or another hardware/software identity.

## Frozen candidate and environment

- target identity: `hepintelpc`, Intel Core Ultra 5 225U;
- OpenVINO: `2026.2.1-21919-ede283a88e3-releases/2026/2`;
- backend: explicit `CPU`, precision `f32`, performance hint `LATENCY`;
- artifact and reference hashes: exact values in the hash-bound `phase4_frozen_config.json`;
- normalized inputs: `state float32[1,6]`, `wrist_image float32[1,3,480,640]`;
- normalized output: `action_chunk float32[1,100,6]`;
- correctness on every call: `rtol=1e-4`, `atol=1e-5`;
- physical route: strict no-touch SSH, unobstructed airflow and recorded physical setup;
- no backend fallback, runtime update, configuration change or physical intervention.

The Stability Worker consumes the already-normalized frozen input. Preprocessing and action
postprocessing are not inside this repeated-call boundary.

## Frozen execution design

- pre-observation: 30 seconds, seven exact-path samples at five-second spacing;
- pre-observation average aggregate CPU busy: `<=10%`;
- pre-observation throttle-field increases: zero;
- entry package temperature: `<=60 C`;
- entry maximum readable sensor: `<=65 C`;
- initial correctness calls: one;
- warmup calls: ten;
- formal duration: at least 1800 seconds;
- input: frozen reference input only;
- latency sample and correctness check: every inference;
- latency summary window: 60 seconds;
- structured external telemetry: every five seconds;
- loss-of-progress watchdog: 15 seconds without evidence growth;
- startup/compile timeout: 180 seconds;
- overall limit: 2100 seconds including pre-observation and bounded recovery;
- thermal hard stop: any readable sensor `>=100 C`;
- attempts: one named run after separate human authorization;
- automatic retry and reconnect: prohibited;
- recovery: preserve partial evidence, `SIGTERM`, five-second grace, then `SIGKILL` fallback.

A precondition rejection consumes the named attempt because target access and evidence collection
have occurred. Any new attempt requires a new run ID, preserved prior evidence, written
classification and new human authorization.

## Hard gates

PASS requires all of the following:

- target/runtime/artifact/implementation identity matches the authorization;
- the pre-observation passes;
- compile/load, initial correctness and ten warmups complete;
- formal measurement reaches at least 1800 seconds;
- every output has the frozen shape and dtype, is finite and passes correctness;
- inference exceptions, Worker crashes and progress timeouts: zero;
- observed `>=100 C` samples: zero;
- boot ID and required interface inventory remain stable;
- no throttle counter decreases, sampling-time failure or required-interface loss occurs;
- required raw and structured evidence is complete;
- independent evidence review passes.

Stop/fail on the first identity/hash mismatch, incorrect or non-finite output, exception, process
failure, progress or overall timeout, observed `>=100 C`, required-interface loss, boot/inventory
change, counter decrease, invalid sampling time or incomplete evidence.

## Diagnostic-only observations

Latency distributions and windows, temperature below the hard stop, exact-path throttle changes,
frequency, CPU activity, RSS and available-memory trends must be reported. They do not silently
replace the frozen hard gates.

A positive `throttle_count` delta below `100 C` requires review but is not an automatic Stability
failure. Each field is compared only with the same exact path; duplicated package paths are not
summed. Unchanged `total_time_ms` or `max_time_ms` fields provide no duration evidence and must not
be interpreted as zero duration.

## Evidence contract

- run-specific authorization bound to target, package directory, parameters and exact protocol,
  Supervisor, Worker, monitor, monitor dependency, config and pre/post hashes;
- pre-observation decision and all raw structured monitor events;
- Worker event JSONL, raw per-inference CSV and Worker result;
- Supervisor telemetry, stdout/stderr, process recovery and Supervisor result;
- exact artifact/runtime identity;
- independent recomputation of event pairing, duration, correctness, latency windows, thermal and
  resource trends and exact-path throttle changes;
- separate human-owned admission review.

## Watchdog boundary

`infer_enter` is emitted immediately before the Stability inference path. `infer_return` is emitted
after output copy, correctness calculation, CSV flush and event serialization. A timeout proves
that a complete recorded iteration did not return within 15 seconds; it does not identify an
OpenVINO, plugin, operating-system or hardware root cause.

The external Supervisor owns evidence preservation and bounded Worker termination. The Worker does
not restart itself.

## Pre-run review

- [x] Parameters and claim boundary accepted before target execution.
- [x] Exploratory thermal evidence kept separate from this qualification.
- [x] Human retained the final execution and admission decisions.
- [ ] Supervisor-only implementation completed without changing the Worker path.
- [ ] Artificial validation and existing regressions passed.
- [ ] Exact implementation hashes frozen.
- [ ] Target no-model deployment preflight passed.
- [ ] A readiness review proposed one run ID.
- [ ] Human separately authorized that run.

## Deviations

None. Do not edit the frozen sections after execution begins. A material change requires a new
protocol version; an execution deviation must be appended and classified without rewriting the
original evidence.
