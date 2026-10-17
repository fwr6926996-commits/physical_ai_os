# Phase 4 Round 3 CPU FP32 Stability Review

Review date: `2026-10-15`

Protocol: `P4-DK2500-CPU-FP32-STABILITY-002`, version `0.2`

Run: `phase4_r3_stability_20261014_01`

Engineering result: `PASS — STABILITY STAGE ONLY`

Backend admission: `PENDING HUMAN DECISION`

Phase acceptance: `NOT DECIDED`

## Decision

Independent recomputation found no frozen hard-gate failure. The run therefore passes the Phase 4
CPU FP32 Stability stage for the exact recorded DK-2500, OpenVINO, model, frozen-input and
repeated-synchronous-inference boundary.

This is not yet a human backend-admission decision or Phase 4 acceptance. It does not establish
changing-input behavior, full preprocessing/control/postprocessing behavior, real-time control,
robot task success, E-stop effectiveness, collision safety or another target/backend.

## Frozen identity and execution

- one hash-bound authorization was used; authorization SHA-256:
  `3de4d013bbc686a3b564bc9d71da3d1f9d12c615d997aa64ac43fb21ffeb7804`;
- run ID and result directory were unused before execution;
- all protocol, Supervisor, Worker, monitor, dependency, configuration and pre/post hashes matched;
- device / precision / hint: explicit `CPU` / `f32` / `LATENCY`;
- Worker exit code: `0`;
- recovery: none;
- automatic retry: none;
- Worker stdout/stderr: empty;
- Supervisor result: `STAGE_PASS_REVIEW_PENDING` before independent review.

## Entry gate

The frozen 30-second pre-observation passed before Worker/model access:

- average aggregate CPU busy: `0.0214%` (`<=10%`);
- throttle-field increment paths: `0`;
- final package temperature: `48 C` (`<=60 C`);
- final maximum sensor temperature: `49 C` (`<=65 C`);
- interface/timebase failures: none.

The earlier no-model-preflight observation of `76 C` was correctly not reused as the entry
decision. The dedicated pre-observation measured the actual authorized starting state.

## Correctness, progress and duration

Independent parsing of `events.jsonl` and `latencies.csv` found:

- correctness calls: `1`;
- warmup calls: `10`;
- formal measurement calls: `11,918`;
- `infer_enter`: `11,929`;
- `infer_return`: `11,929`;
- missing returns / orphan returns: `0 / 0`;
- non-finite / incorrect returns: `0 / 0`;
- maximum absolute error: `2.86102294921875e-06`;
- formal measurement duration: `1800.0845 s`;
- watchdog timeout, process crash or inference exception: none;
- final event: `worker_completed`.

This supports the frozen repeated-inference Stability claim. It does not prove what would happen
with changing observations or robot actuation.

## Latency evidence

Overall inference-only latency:

- mean: `150.578 ms`;
- P50 / P95 / P99: `150.429 / 161.487 / 168.826 ms`;
- min / max: `96.196 / 223.469 ms`.

Across the first and last complete 60-second windows:

- P50: `145.343 -> 151.449 ms` (`+4.201%`);
- P95: `157.779 -> 161.798 ms` (`+2.547%`);
- maximum window P95 / P99: `165.234 / 173.391 ms`.

The protocol deliberately treats these values as diagnostic. No precommitted performance or
real-time threshold was crossed because none was defined for this Stability gate. The result must
not be converted into performance or control-frequency admission.

## Thermal and throttle evidence

The structured monitor contains one identity event and `368` samples: seven pre-observation, 360
Worker-runtime and one final sample. There were no read errors, monitor failures, boot changes,
counter decreases or samples at/above the frozen `100 C` stop.

- maximum package temperature: `91 C`;
- maximum sensor temperature: `93 C`;
- throttle-count increase: `26/28` exact paths;
- count changes occurred only across the first four loaded five-second windows and stopped after
  scheduled elapsed `50 s`;
- `throttle_total_time_ms` increased on `12/28` paths, only in the first two loaded windows, with a
  maximum single-path delta of `47` reported milliseconds;
- `throttle_max_time_ms` increased on `10/28` paths, with a maximum path delta of `5` reported
  milliseconds;
- duplicated package paths were compared only with themselves and were not summed.

Unlike D3, this run does contain positive duration-field evidence. It supports the bounded statement
that some exposed package duration fields increased early under load. It still does not prove a
thermal, firmware, kernel, OpenVINO or hardware root cause, and repeated package exposure prevents
turning the fields into a summed platform-wide duration.

These observations do not retroactively fail Stability: positive throttle values below the
precommitted `100 C` stop were explicitly frozen as diagnostic-only evidence.

## Resource evidence

The Supervisor's start sample preceded model/runtime loading and recorded about `8.7 MB` RSS. The
first comparable periodic sample, after loading, recorded `937,312,256` bytes; the last periodic
sample recorded `937,963,520` bytes. The comparable first-to-last change was therefore only
`+651,264` bytes across the formal window, with a periodic range of `937,312,256` to `937,963,520`
bytes.

Available system memory did not show a monotonic exhaustion pattern. This run does not support a
continuing memory-leak claim. It also does not establish a general memory bound outside this frozen
workload.

## Evidence integrity

Machine-readable independent recomputation:
`evidence/phase4_3_stability/independent_review.json`

The recomputation binds the SHA-256 of every raw evidence file and records event pairing,
correctness, latency, monitor, exact-path throttle and resource results. `git diff --check`, JSON
parsing and the existing Phase 4 `10/10` regression suite remain required before final handoff.

## Supported conclusion

The exact DK-2500 CPU FP32 frozen-input offline repeated-inference path passed the frozen 30-minute
Stability protocol without incorrect/non-finite output, missing progress, exception, process
failure, evidence failure or thermal hard stop.

## Conclusions not supported

- performance or real-time admission;
- full host-pipeline or changing-input stability;
- robot task success, collision safety or E-stop effectiveness;
- a proven root cause for throttle counter/time-field changes;
- portability to another DK-2500 state, software version, model, backend or platform;
- automatic Phase 4 acceptance.

## Next human gate

The human owner must separately decide whether this reviewed evidence admits **CPU FP32 only for
the frozen offline backend interface** and whether Phase 4 should close, remain partial or route
additional work. No rerun is permitted under the consumed authorization.

