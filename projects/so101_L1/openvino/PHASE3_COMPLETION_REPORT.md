# Archived V2.8 Phase 3 Completion Report

Status: `ARCHIVED_DO_NOT_DEPLOY`

This document is historical V2.8 evidence. Its GPU-primary decision was superseded by the V2.9 stability evidence. The only active Phase 3 runtime configuration is `phase3_v2_9/active_runtime_config.yaml`, which admits CPU FP32 only.

## Historical report

Phase 3 is complete with GPU.0 FP32 as the primary Intel inference path and CPU FP32 as the fallback. The NPU can compile and execute the ACT model but does not meet the frozen numerical correctness threshold, and its plugin rejects FP32 inference. GPU.1 is the NVIDIA RTX 5060 and was deliberately excluded. Phase 4 has not started.

## Scope and frozen contract

The experiment used one Policy Package V1 and one fixed input across all tested Intel devices. The model contract is `state float32[1,6]` plus `wrist_image float32[1,3,480,640]`, producing `action_chunk float32[1,100,6]`. Correctness was compared against the frozen PyTorch CPU normalized action chunk using `rtol=1e-4` and `atol=1e-5`.

All latency figures are synchronous model-only inference. They exclude loading, compilation, preprocessing, postprocessing, robot I/O, and control-loop timing. Each admitted backend used 10 warm-up iterations followed by 100 measured iterations with the `LATENCY` performance hint.

## Device results

| Device path | Compile and infer | Correctness | P50 ms | P95 ms | P99 ms | Phase 3 decision |
|---|---:|---:|---:|---:|---:|---|
| CPU explicit FP32 | PASS | PASS | 57.18 | 61.91 | 64.92 | Fallback |
| GPU.0 default precision | PASS | FAIL | - | - | - | Rejected |
| GPU.0 explicit FP32 | PASS | PASS | 17.85 | 27.29 | 35.48 | Primary |
| NPU default precision | PASS | FAIL | - | - | - | Compatibility evidence only |
| NPU explicit FP32 | Unsupported | Not run | - | - | - | Excluded |
| GPU.1 RTX 5060 | Not tested | Not tested | - | - | - | Outside Intel-only scope |

GPU.0 FP32 is approximately 3.20 times faster than CPU FP32 at P50, 2.27 times faster at P95, and 1.83 times faster at P99. Its maximum absolute error is `1.431e-6`, which passes the frozen threshold. The default GPU precision produced a maximum error of `1.328e-3`, so explicit FP32 is part of the runtime contract rather than an optional tuning setting.

The NPU default path compiled in 1463.93 ms and completed first inference in 102.91 ms, proving model and plugin compatibility at that layer. It produced a maximum absolute error of `2.485e-3` and failed strict correctness. A separate FP32 request was rejected by the plugin, which reported only `f16` and `i8` as supported values. In accordance with the gate ordering, no NPU latency score was produced after correctness failed.

## Runtime decision

The Phase 3 runtime must select devices explicitly. The primary path is `GPU.0` with a full-name guard for Intel Arc Graphics, `LATENCY`, and `f32`. The fallback is `CPU` with a full-name guard for the Intel Core Ultra 7 255H, `LATENCY`, and `f32`.

`GPU.1`, `NPU`, `AUTO`, and `HETERO` are forbidden in the frozen Core configuration. This prevents accidental RTX selection, preserves device attribution, and keeps a failed NPU correctness path out of deployment.

## Evidence integrity

The CPU FP32 and GPU.0 FP32 reports were independently recomputed from their 100-row CSV files and matched exactly. The Policy Package core artifacts and Phase 3 evidence have SHA-256 entries in `policy_package_v1/policy_package_v1.sha256`.

The filename `act_cpu_reference.xml` is historical; the IR itself is the same device-neutral OpenVINO model used for the CPU, GPU.0, and NPU tests. It was not renamed during closeout to avoid breaking existing evidence references.

## Phase boundary

This report closes only the ThinkBook Core Ultra 7 255H Intel pre-deployment phase. It does not claim DK-2500 performance, 30-60 minute edge stability, power, temperature, memory, real-time control behavior, or robot success. Those belong to later phases. No Phase 4 action was executed during this closeout.
