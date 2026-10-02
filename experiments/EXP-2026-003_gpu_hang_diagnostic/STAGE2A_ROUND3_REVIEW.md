# EXP-2026-003 Stage 2A Round 3 Review

## Verdict

`HANG_REPRODUCED_WATCHDOG_RECOVERED`

Round 3 reproduced the historical symptom class in the frozen historical worker path. Stage 2A stops immediately. Round 4 is prohibited.

## Verified evidence

- Run ID: `stage2a_r3_20260924_01`
- Device: Intel Arc iGPU `GPU.0`
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- Historical baseline source hash matched the Phase 3 manifest.
- Last completed inference: 4,450 at 84.680417 seconds.
- Every completed output was finite and correct.
- Maximum absolute error: `1.430511474609375e-06`.
- No heartbeat arrived for 15.074460 seconds.
- Worker snapshot at timeout: `running`, CPU 99.9%, RSS 623,583,232 bytes, 37 threads.
- Watchdog recovered the worker with SIGTERM; exit code `-15`.
- Latency p50: 18.302101 ms; p95: 25.037086 ms; p99: 29.560155 ms.
- Maximum observed sensor temperature: 73 °C.
- Post-hoc kernel journal query returned no entries for the run/failure window.

Evidence SHA-256:

- `result.json`: `22e2ac0c826684e0eb8e54f6b617b66d13ebd85dbb66590a283a220484a559db`
- `latencies.csv`: `df4691cd3588b0c8cceed8da8114bf37d3f129f57353ac759f87215313098365`
- `supervisor_telemetry.csv`: `8150e24b4d95280d9624e9ceddc0e85bb3b501b1c94df44cbb4338822249c64c`
- `stage2a_classification.json`: `ea6bc16811d42faf4939c7fb6891889530d5d5558928d1a1397943e5b621dde2`

## Comparison

| Run | Outcome | Last/total iterations | Stop time | p50 ms | Mean ms | Max temp °C |
|---|---|---:|---:|---:|---:|---:|
| Historical R1 | Hang | 3,270 | 94.118 s | 31.656 | 28.698 | 72 |
| Historical R2 | Hang | 1,794 | 52.000 s | 31.652 | 28.902 | 68 |
| Stage 2A R1 | No hang | 15,750 | 300.006 s | 18.300 | 18.990 | 72 |
| Stage 2A R2 | No hang | 15,734 | 300.002 s | 18.314 | 19.007 | 72 |
| Stage 2A R3 | Hang | 4,450 | 84.680 s | 18.302 | 18.971 | 73 |

Round 3 hung with essentially the same pre-hang latency distribution as successful Rounds 1 and 2. Therefore lower current latency does not prevent the observed symptom and cannot explain the successful rounds.

Temperatures overlapped successful and failed runs. Worker RSS was not higher than the successful rounds. Completed outputs remained correct. None of these signals provided a pre-failure acceptance warning.

## Evidence boundary

The historical worker sends a heartbeat only after synchronous inference, output retrieval/copy, correctness work and Queue communication. The missing next heartbeat therefore localizes loss of progress only to that combined interval. It does not yet prove that `request.infer(inputs)` itself failed to return.

The `running` process state and approximately one CPU core of activity describe the timeout snapshot; they do not identify which internal layer was making or failing to make progress.

The empty kernel journal supports only “no kernel report was observed.” It does not exclude a driver or hardware issue.

## Decision

- Close Stage 2A after Round 3 under the frozen stop rule.
- Prohibit Round 4.
- Allow Stage 2B design because a current fault signal has been recovered.
- Do not execute Stage 2B until one low-perturbation observation variable, its A/B sequence and stop rules are frozen.
- Keep GPU.0 `CLOSED_NOT_ADMITTED` and Phase 3 `PARTIAL PASS — CPU FP32 ONLY`.
