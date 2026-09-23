# Phase 3 V2.9 Final Evidence Report

## Outcome

Phase 3 V2.9 experimental work is complete. The engineering gate is **PARTIAL PASS — CPU FP32 ONLY**. The engineering closeout and CPU-only Phase 4 planning waiver are recorded; final independent learning verification remains pending.

CPU FP32 is the only backend that passed the frozen correctness gate and the human-selected 30-minute stability gate. GPU.0 FP32 passed frozen-input correctness and short benchmarks, but repeated native inference stalls occurred in both monolithic and isolated-worker paths; the precommitted two-consecutive-failure rule closed it as not admitted. NPU and reduced-precision candidates did not pass correctness or support gates. GPU.1 remains outside the Intel-only scope.

This result qualifies an offline OpenVINO CPU inference path on the ThinkBook 255H. It does not establish robot safety, real-time control behavior, physical task success, collision avoidance, E-stop behavior, or DK-2500 performance.

## Frozen platform and policy contract

- Host: Lenovo ThinkBook 16 G7+ IAH
- CPU: Intel Core Ultra 7 255H
- GPU.0: Intel Arc Graphics iGPU
- GPU.1: NVIDIA GeForce RTX 5060 Laptop GPU, excluded
- NPU: Intel AI Boost
- Memory: 2 × 16 GB DDR5-5600
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- Inputs: `state float32[1,6]`, `wrist_image float32[1,3,480,640]`
- Output: normalized `action_chunk float32[1,100,6]`
- Correctness gate: `rtol=1e-4`, `atol=1e-5`
- IR SHA-256: XML `54615bff...879e`, BIN `96c225f0...848a`

## Backend admission matrix

| Candidate | Compile/infer | Frozen correctness | Stability | Final Phase 3 status |
|---|---|---|---|---|
| CPU FP32 | PASS | PASS, max abs error `2.623e-6` | PASS, 30 minutes and 30,654 iterations | **ADMITTED** |
| GPU.0 FP32 | PASS | PASS, max abs error `1.431e-6` | FAIL, repeated inference stalls | **CLOSED — NOT ADMITTED** |
| CPU FP16 | PASS | FAIL, max abs error `1.739e-3` | Not eligible | Not admitted |
| GPU.0 FP16 | PASS | FAIL, max abs error `1.328e-3` | Not eligible | Not admitted |
| NPU FP16 | PASS | FAIL, max abs error `2.485e-3` | Not eligible | Compatibility evidence only |
| NPU FP32 | Unsupported | Not run | Not eligible | Not admitted |
| INT8 mixed PTQ | PASS artifact generation | FAIL task-level fidelity evidence | Not eligible | Closed as reproducible negative evidence |
| GPU.1 RTX 5060 | Not tested | Not tested | Not tested | Excluded from Intel scope |

## Qualified CPU evidence

The formal segmented CPU run measured 100 steady-state iterations after 10 warmups:

- preprocessing P95: `0.210 ms`
- OpenVINO inference P50/P95/P99: `52.245 / 55.305 / 56.641 ms`
- postprocessing P95: `0.008 ms`
- inference share of the diagnostic P95 sum: `99.607%`

The 30-minute streamed-evidence stability run completed 30,654 iterations with zero inference exceptions, zero non-finite outputs, and zero correctness failures. Overall P50/P95/P99 were `58.121 / 64.260 / 67.790 ms`. Process RSS changed by `+430,080 bytes`; the first-to-last full-window drift was `+1.276%` at P50 and `+3.299%` at P95. Temperature averaged `75.95°C` over the first five minutes and `76.32°C` over the last five minutes, with a `91°C` observed maximum and no sustained runaway or functional failure.

These figures qualify only the stated offline synchronous inference scope. The independent-stage percentile sum is diagnostic, not a measured end-to-end robot-control distribution.

## GPU.0 closure

GPU.0 showed bimodal short-run latency and later repeated stability failure. Disabling in-worker telemetry did not prevent the stall. A minimal guarded diagnostic once completed five minutes, but the formal isolated-worker sequence then failed twice:

| Round | Last correct inference | Worker elapsed | Failure |
|---|---:|---:|---|
| 1 | 3,270 | `94.12 s` | Heartbeat stopped; 15-second watchdog recovered with SIGTERM |
| 2 | 1,794 | `52.00 s` | Heartbeat stopped; 15-second watchdog recovered with SIGTERM |

All completed outputs before both stalls remained finite and correct. Temperature, steady post-startup RSS, and latency samples did not show a preceding acceptance failure. The exact cause is not proven; the evidence does not assign root cause to OpenVINO, the Intel GPU plugin, the kernel driver, or the Python harness. Under the human-frozen stop rule, no Round 3 is permitted and GPU.0 is not a deployment backend for this Phase 3 result.

## INT8 and profiling conclusions

The INT8 PTQ candidate reduced XML+BIN size by `73.75%`, but failed strict and task-relevant fidelity checks, including material first-action and joint-localized errors. It received no qualified latency rank and no robot-execution authorization. The human-owned architecture decision closed the current feasibility attempt without accuracy recovery.

CPU profiling localized approximately `58.99%` of the profiled mean-time sum to convolution and `34.14%` to fully connected execution. The slowest individual node represented only about `3.9%`, so the CPU bottleneck is distributed rather than a single pathological operation. Profiling overhead and CPU-specific execution mean these results neither replace formal benchmarks nor describe GPU behavior.

## Learning and acceptance state

Completed independent learning checks cover correctness-gated benchmarking, FP32/FP16/INT8/INT16/BF16 concepts, INT8 architecture trade-offs, profiling concept/interface interpretation, stability purpose, and the GPU bounded-recovery architecture decision.

Final Phase 3 acceptance remains human-owned. The final check must demonstrate that the operator can explain the admission decision, identify the critical interfaces and evidence, and reproduce the debugging path without confusing offline correctness or stability with robot safety.

## Phase boundary

Phase 4 has not started. ADR-0001 permits a bounded CPU-only Phase 4 qualification path after DK-2500 hardware/software truth and a frozen Phase 4 protocol; it does not convert the Phase 3 partial pass into a full pass. Any later use of GPU.0, NPU, INT8, AUTO, HETERO, or GPU.1 requires a new scoped architecture decision and new evidence. Under the current Phase 3 result, the only admitted backend is explicit `CPU` with FP32 and the frozen identity/configuration guards.
