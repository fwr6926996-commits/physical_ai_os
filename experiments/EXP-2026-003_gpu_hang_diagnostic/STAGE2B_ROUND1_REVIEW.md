# EXP-2026-003 Stage 2B Round 1 Review

## Verdict

`HANG_INFER_ENTERED_NOT_RETURNED`

The first Stage 2B attempt reproduced the intermittent hang and produced a stable infer-boundary snapshot. The frozen stop rule closes Stage 2B immediately; Rounds 2 and 3 are prohibited.

## Verified runtime evidence

- Run ID: `stage2b_r1_20260924_01`.
- Device: Intel Arc iGPU `GPU.0`.
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`.
- Frozen Stage 2B worker SHA-256: `7093c14a6b6eeed5fb3aa234a6e05c96b89d1e1039c661872e028490377f5672`.
- Last completed measurement iteration: 3,873 at 74.190910 seconds.
- Last completed output: finite and correct; maximum absolute error `1.430511474609375e-06`.
- Watchdog timeout: 15.089199 seconds without heartbeat.
- Worker at timeout: running, CPU 99.9%, RSS 628,322,304 bytes, 37 threads.
- Recovery: SIGTERM; worker exit code `-15`.
- Completed-call latency p50: 18.399545 ms; p95: 25.533745 ms; p99: 29.655285 ms.
- Maximum observed sensor temperature: 76 °C.
- Post-hoc kernel journal query returned no entries.

## Boundary evidence

Fixed mapping with initial inference plus ten warmups:

```text
heartbeat infer sequence = measurement iteration + 11
                         = 3,873 + 11
                         = 3,884
```

Stable snapshots after bounded worker recovery:

```text
snapshot 1: E=3,885, R=3,884
snapshot 2: E=3,885, R=3,884
H=3,884
```

Therefore:

```text
E = R + 1
R = H
```

The 3,884th synchronous inference returned and its heartbeat reached the parent. The worker then recorded entry into the 3,885th `request.infer(inputs)` call. No matching return was recorded before the 15-second watchdog recovery.

## Evidence integrity

- `latencies.csv` contains 3,873 continuous rows with no sequence gap.
- Nonfinite outputs: 0.
- Correctness failures: 0.
- Both shared snapshots are identical.
- The preflight worker hash matches the result worker hash and frozen protocol hash.

Evidence SHA-256:

- `result.json`: `5c63fc41a8f5156f421ccde1bb7719e660397b44c09c91528d41e4093c284b3c`
- `latencies.csv`: `00bbc4cf1d0217fc3b55a082cd09e95e8950da17790ebbaa44569d075e172153`
- `supervisor_telemetry.csv`: `7edf66214a9f23b21b890e4cf4f90578a3097ceab7189260fced08638820d3c7`
- `stage2b_boundary_result.json`: `f3009c265051c7929d17365ab46864c403e3b80d2365b67bbefa875993825b37`

## Strongest supported conclusion

During this reproduced event, the worker entered synchronous OpenVINO `request.infer(inputs)` call 3,885 and did not return from that call within the watchdog window.

## Unsupported conclusions

- This does not identify whether OpenVINO Runtime, Intel GPU Plugin, user-mode compute runtime, i915, firmware or GPU hardware is causal.
- It does not prove the native operation was doing no internal work; it proves only that control did not return to the Python line after `request.infer`.
- The empty kernel journal does not exclude a driver or hardware problem.
- The observation does not qualify or readmit GPU.0.

## Decision

- Close Stage 2B after Round 1.
- Prohibit Stage 2B Rounds 2 and 3.
- Route the remaining internal-boundary question to Stage 2C design.
- Keep GPU.0 `CLOSED_NOT_ADMITTED` and Phase 3 `PARTIAL PASS — CPU FP32 ONLY`.
