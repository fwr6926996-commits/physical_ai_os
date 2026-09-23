# Phase 3 V2.9 Gap Analysis

## Outcome

The V2.8 run is useful historical evidence but does not satisfy the expanded V2.9 gate. Phase 3 must be rerun under a new evidence namespace. No old model, benchmark, or failure record will be overwritten.

## V2.9 requirements and current gaps

| V2.9 requirement | Existing evidence | Rerun decision |
|---|---|---|
| Same Policy Package and fixed input/output contract | V2.9 package regenerated; `[1,6]`, `[1,3,480,640]` -> `[1,100,6]`; frozen tensors match V2.8 hashes | Technical PASS |
| Export, convert, compile, and load evidence | V2.9 rerun has explicit stage timings, hashes and CPU correctness | Technical PASS |
| Explicit Intel device selection and RTX isolation | GPU.0 identity guard and GPU.1 exclusion exist | Retain design; recapture host device evidence |
| CPU and iGPU correctness plus P50/P95/P99 | V2.9 CPU/GPU.0 FP32 correctness and percentiles captured; GPU.0 bimodal tail reproduced in 300-sample diagnostic | Technical PASS; GPU tail diagnosis remains open |
| Preprocess, inference, and postprocess timing | First formal CPU segmented run captured; independent-process limitation declared | Technical PASS for diagnostic segmentation |
| RAM and temperature evidence | CPU FP32 30-minute streamed-evidence run shows +430,080 bytes process RSS, 75.95°C first-5-minute mean vs 76.32°C last-5-minute mean, 91°C peak, with no sustained upward trend. GPU.0 monolithic and isolated-worker hangs prevented a complete 30-minute resource record; parent telemetry remained operational and showed no temperature or post-startup RSS precursor in the two formal isolated attempts. | CPU PASS; GPU.0 closed as not admitted after repeated stability failures |
| Stable execution on 255H | Human froze 30 minutes per admitted backend; CPU FP32 completed 30,654 inferences with zero exceptions, non-finite outputs or correctness failures. GPU.0 failed in monolithic runs and then failed two consecutive formal isolated-worker attempts after 94.12 and 52.00 seconds; both were recovered by watchdog and all completed outputs before each stall were correct. | CPU PASS; GPU.0 FAIL and CLOSED_NOT_ADMITTED under the precommitted stop rule. Exact root cause remains unlocalized. |
| FP32 and FP16 comparison | V2.9 CPU/GPU.0/NPU matrix captured; only CPU/GPU.0 FP32 pass strict correctness | Technical PASS with reduced-precision rejection recorded |
| INT8 PTQ deployment evidence | Basic mixed PTQ completed with 300 calibration and 100 non-overlapping validation samples; artifact size reduced 73.75%, but strict correctness failed with material joint-specific and first-action errors | Closed as reproducible negative evidence by human Option A; no qualified latency ranking, robot execution or accuracy recovery |
| NPU actual compatibility record | V2.9 FP16 compile/infer PASS but strict correctness FAIL; FP32 compile unsupported with traceback evidence | Technical PASS as reproducible negative evidence |
| Real bottleneck localization | CPU FP32 profiling captured 478 execution nodes; convolution family is the primary cost (~59% of profiled mean-time sum), fully-connected execution is secondary (~34%); no single node dominates | Technical PASS and independent concept/interface interpretation PASS; result is CPU-specific and profiling latency is not a formal benchmark |
| Independent learning verification | Missing | User explains the mechanism, identifies files, changes one parameter, reproduces the path, and states the debugging route |

## Architecture decisions that remain human-owned

The following choices are not silently frozen by Codex:

1. The minimum duration for the 255H stability run. V2.9 requires stable execution but gives the explicit 30–60 minute duration only for DK-2500 Phase 4.
2. The calibration sample policy and task-level acceptance metric for INT8 PTQ.
3. Final admission of a reduced-precision backend after reviewing accuracy, latency, and resource trade-offs.
4. GPU.0 architecture choice and bounded recovery sequence are resolved: the isolated-worker path produced two consecutive failures, triggering the human-frozen stop rule. GPU.0 is closed as not admitted for this Phase 3 deployment; no Round 3 is authorized.

## Completion rule

Phase 3 may be marked complete only after the engineering evidence passes the V2.9 gate and the independent learning check is accepted by the user. Technical completion without explainability is recorded as Mystery Debt, not final acceptance.
