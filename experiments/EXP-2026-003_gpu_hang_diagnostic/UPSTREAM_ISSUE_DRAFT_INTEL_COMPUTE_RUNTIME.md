# Upstream issue draft — Intel compute-runtime

状态：`SUBMITTED — INTEL COMPUTE-RUNTIME ISSUE #1012`  
目标仓库：`intel/compute-runtime`  
创建日期：2026-09-30

公开 issue：https://github.com/intel/compute-runtime/issues/1012  
公开证据包：https://github.com/user-attachments/files/32858204/stage2d_public_evidence_20260930.zip  
证据包 SHA-256：`c09d304198daffe88417b8c27941dfd927dd0287347f173f20ca49bc9d0a9d0f`

## 提交确认记录

- [x] 项目所有者确认相关工程与系统信息可以公开。
- [x] 已附上 `gdb_all_threads.txt`、结果 JSON、遥测 CSV 和诊断代码的 ZIP。
- [x] 已披露 AI 协助，并注明所有 GPU 运行由项目所有者明确启动和审核。
- [x] 首先提交 Intel compute-runtime；暂不重复提交 OpenVINO，等待组件归属意见。
- [x] “正在使用最新驱动”保持未勾选；正文明确说明当前版本为冻结故障现场。

---

## Proposed title

`[Bug][Linux][OpenCL] Intermittent synchronous OpenVINO FP32 infer never returns; main thread observed in libigdrcl.so with one CPU core busy (Arrow Lake-P, 25.18.33578.77)`

## Issue body

### Pre-submission checklist

- [x] I searched existing public compute-runtime and OpenVINO issues.
- [x] I found related high-CPU/hang reports, but no issue matching this runtime version, hardware, Linux/OpenVINO FP32 single-request path, and failure signature.
- [x] The report distinguishes stopped-time observation from root-cause attribution.
- [x] The affected deployment path has been disabled; this report is for diagnosis, not a claim that GPU execution is safe.

### Summary

An isolated OpenVINO worker performing repeated synchronous FP32 inference on an Intel Arrow Lake-P integrated GPU intermittently stops making progress inside `InferRequest.infer()`.

The failure reproduced in a bounded diagnostic run after 12,396 synchronous inference calls had returned. Call 12,397 was entered but did not return within a 15-second watchdog interval. At the watchdog observation, the process was still in the Linux `R (running)` state and consumed approximately one CPU core.

A bounded GDB attach captured all 37 threads and detached normally. The Linux main thread crossed `_pyopenvino`, OpenVINO Runtime, Intel GPU Plugin, and then had its top nine unresolved frames inside the stripped Intel OpenCL Compute Runtime library `libigdrcl.so`.

This localizes the stopped-time execution path but does **not** prove that `libigdrcl.so` contains the originating defect. I am requesting help identifying the unresolved frames and determining which additional low-perturbation evidence would best distinguish a normal completion wait, prolonged polling/spinning, livelock, delayed GPU completion, or an earlier fault.

### Hardware

- System: Lenovo ThinkBook 16 G7 IAH laptop
- CPU: Intel Core Ultra 7 255H
- Integrated GPU: Intel Arrow Lake-P Graphics
- PCI ID: `8086:7d51` (revision `03`)
- Kernel driver in use: `i915`
- Discrete GPU is also present, but OpenVINO device identity was explicitly checked and the test targeted `GPU.0`, reported as `Intel(R) Arc(TM) Graphics (iGPU)`.
- System memory: approximately 32 GB
- AC power connected; platform profile was `performance`

### Software

- OS: Ubuntu 24.04, x86_64
- Kernel: `7.0.0-31-generic`
- OpenVINO: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- Intel GPU Plugin build: `2026.3.1-22476-759c5a6ab8c-releases/2026/3`
- `intel-opencl-icd`: `25.18.33578.77-1146~24.04`
- `libigc2`: `2.11.43-1146~24.04`
- `libigdgmm12`: `22.7.2-1146~24.04`
- GDB: `15.1`

Observed OpenCL runtime binary:

```text
path: /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so
package: intel-opencl-icd 25.18.33578.77-1146~24.04
Build ID: 58ccca242c62c0629c06940ee3d7b8a40b298e35
SHA-256: d43af828e1acfcce4a2c042167ecacb270e9356fa55a3a557f18cd55b79540da
binary: stripped
```

### OpenVINO configuration and input contract

The worker used one compiled model and one synchronous infer request:

```python
config = {
    ov.properties.hint.performance_mode:
        ov.properties.hint.PerformanceMode.LATENCY,
    ov.properties.hint.inference_precision: ov.Type.f32,
}
compiled = core.compile_model(model, "GPU.0", config)
request = compiled.create_infer_request()

while within_test_window:
    request.infer(inputs)
```

Inputs:

```text
state:       [1, 6]
wrist_image: [1, 3, 480, 640]
```

Model/evidence artifact hashes:

```text
IR XML:          54615bff5874f134521353c8240ecff6f95277e51c094b543713bc1d6c60879e
IR BIN:          96c225f0676edcb44b641906e93222d0f52883a7ed6956725c904266c717848a
reference input: cd2da1c65e4f5ec99d3d4189d186908b717e5eb74e9062638e3a646b2ed06b75
reference output:b63021c20ede458096693431f620010d46f497b54c7c0b7b6ffd8713deda3d5a
```

The model artifacts are not attached to this draft pending a licensing/privacy review. I can provide additional model details or a permitted reproducer if maintainers identify what is required.

### Expected behavior

Every synchronous `request.infer(inputs)` call should either return successfully or report a bounded error. The host process should not remain indefinitely CPU-active inside the GPU execution path without returning or producing an error.

### Actual behavior

In diagnostic run `stage2d_r1_20260930_01`:

- Initial correctness: PASS.
- Measurement calls completed before the failure: 12,385.
- Including one initial call and ten warmups, returned-call sequence: 12,396.
- Entered-call sequence at timeout: 12,397.
- Both shared boundary snapshots were stable: `enter=12397`, `return=12396`.
- Last completed measurement elapsed time: `233.663175 s`.
- Watchdog fired after `15.074147 s` without a returned inference/heartbeat.
- Worker at timeout: `R (running)`, `99.9%` CPU, 37 threads, RSS 681,037,824 bytes.
- All 12,385 recorded measurement outputs were finite and correct.
- Maximum absolute output error: `1.430511474609375e-06`.
- Completed-call latency: p50 `18.153212 ms`, p95 `24.782856 ms`, p99 `29.541771 ms`, maximum `39.548584 ms`.
- No latency ramp or correctness error preceded the failure.

The watchdog first took a bounded GDB snapshot, then recovered the worker with SIGTERM. GDB returned successfully in `1.047426 s`, detached, and the target was observed running afterward. The worker then exited with code `-15` as expected from recovery.

### Main-thread stack boundary

The main Linux thread was identified in the all-thread backtrace. From Python toward the stopped top frames, the call chain was:

```text
Python evaluation
→ _pyopenvino
→ ov::InferRequest::infer()
→ ov::IAsyncInferRequest::infer()
→ OpenVINO Runtime execution
→ libopenvino_intel_gpu_plugin.so
→ libigdrcl.so
→ nine unresolved libigdrcl.so frames at the top
```

Frame ranges in the saved backtrace:

```text
frames 0–8:   /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so
frames 9–19:  libopenvino_intel_gpu_plugin.so
frames 20–25: libopenvino.so.2631
frames 26–27: _pyopenvino
remaining:    Python/libc startup
```

The other 36 threads were observed in futex waits at frame 0. Some deeper frames on secondary threads also entered `libigdrcl.so`. I am not interpreting that fact as proof of deadlock or lock ownership.

### Reproduction history

The failure is intermittent but has occurred repeatedly under the same frozen GPU FP32 path:

1. Two earlier Phase 3 stability attempts stopped making inference progress and failed the deployment gate.
2. A restored five-minute historical worker path reproduced after 4,450 correct measurement iterations.
3. A minimally instrumented shared-counter run reproduced with `enter = return + 1`, localizing the loss of progress to one synchronous `infer()` call.
4. A `/proc` snapshot run reproduced with the main thread running and the other threads mostly in futex waits.
5. This GDB run reproduced after 12,385 correct measurement iterations and captured the native stack described above.

Several bounded runs have also completed without reproduction. I do not treat a completed short run as evidence that the earlier failures did not occur.

### Diagnostic limitations

- The GDB result is one stopped-time observation, not a time series and not a causal diagnosis.
- The installed `libigdrcl.so` is stripped.
- This run did not save `info sharedlibrary` or `info proc mappings`, so the recorded ASLR addresses cannot yet be converted reliably into stable module offsets.
- Approximately one CPU core in use is compatible with several mechanisms; it does not by itself prove useful computation or a spin loop.
- No GPU admission or qualification conclusion is being requested from this diagnostic run.

### Questions for maintainers

1. Are matching debug symbols available for Build ID `58ccca242c62c0629c06940ee3d7b8a40b298e35` / release `25.18.33578.77`?
2. Is there a known internal or public issue in this release involving a prolonged OpenCL completion wait or CPU-active non-returning call on Arrow Lake-P/i915?
3. Given the observed path, would you prefer the next bounded capture to collect:
   - symbolized backtraces plus module mappings,
   - two short-interval native snapshots to test whether the same offsets persist,
   - a specific compute-runtime debug flag or trace,
   - or kernel/GPU-side evidence?
4. Is `intel/compute-runtime` the appropriate component for initial triage, or should this be moved/cross-filed to OpenVINO GPU Plugin?

### Attachments proposed after redaction review

- `result.json` — run configuration, correctness, latency, watchdog and telemetry summary.
- `stage2d_result.json` — infer boundary, GDB control result and evidence hashes.
- `gdb_all_threads.txt` — raw 37-thread backtrace.
- `latencies.csv` — all completed measurement calls.
- `supervisor_telemetry.csv` — bounded host telemetry.
- minimal worker and supervisor scripts, or a smaller permitted reproducer.

### Related public reports reviewed

- `intel/compute-runtime#726`: high CPU/stuck workloads with samples in `libigdrcl.so`; different runtime, hardware and application.
- `intel/compute-runtime#363`: historical discussion of CPU-heavy busy waiting for GPU completion; not evidence that this run is in that exact function.
- `intel/compute-runtime#976`: OpenVINO FP32 failure inside the `25.18.33578` runtime family; different hardware, high-concurrency workload and SIGSEGV failure mode.
- `openvinotoolkit/openvino#37736`: OpenVINO 2026.3.1 GPU call intermittently not returning with one CPU core busy; Windows GenAI/INT8/offload path, not this Linux FP32 request path.

### AI assistance and human validation

AI assistance was used to help design the bounded diagnostic harness, organize the evidence, and draft this report. Every GPU run was explicitly started by me on my hardware. I reviewed the reported outputs and will review all attachments and this issue text before any submission. The report intentionally separates measured facts from possible mechanisms and does not claim a root cause.

---

## 本地证据位置（不要原样公开）

```text
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d/stage2d_r1_20260930_01/result.json
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d/stage2d_r1_20260930_01/stage2d_result.json
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d/stage2d_r1_20260930_01/gdb_all_threads.txt
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d/stage2d_r1_20260930_01/latencies.csv
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d/stage2d_r1_20260930_01/supervisor_telemetry.csv
experiments/EXP-2026-003_gpu_hang_diagnostic/evidence/stage2d_preflight/stage2d_r1_20260930_01.json
```

## 草稿审查结论

该草稿可以用于请求上游协助，但当前仍不应直接提交。提交前至少要完成：

1. 模型/IR 可公开性确认；
2. 原始 GDB 输出隐私检查；
3. 附件最小化与打包；
4. 项目所有者逐段确认英文陈述；
5. 明确选择只投 Intel，还是同时给 OpenVINO 建交叉引用。
