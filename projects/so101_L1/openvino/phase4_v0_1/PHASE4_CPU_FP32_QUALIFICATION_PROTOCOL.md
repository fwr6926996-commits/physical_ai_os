# Phase 4 DK 2500 CPU FP32 Qualification Protocol

Protocol ID: `P4-DK2500-CPU-FP32-001`

Template version: `0.1`

Workflow version: `0.1`

Status: `DRAFT_NOT_FROZEN_NOT_AUTHORIZED_FOR_EXECUTION`

Classification: `QUALIFICATION`

Owner: human

## Question and decision

This protocol will determine whether the frozen V2.9 policy package can compile, load, produce correct outputs and run stably on an explicitly selected DK-2500 CPU backend under recorded edge power and thermal conditions.

A passing result may admit only the recorded DK-2500 CPU FP32 offline inference path. It cannot establish robot task success, real-time control behavior, collision safety, E-stop effectiveness or accelerator compatibility.

## Entry conditions

- [ ] DK-2500 hardware manifest is captured, including CPU, memory topology, storage, firmware/BIOS, power supply and cooling state.
- [ ] DK-2500 software baseline is captured, including OS, kernel, OpenVINO, CPU plugin and relevant driver versions.
- [ ] Available OpenVINO devices and full names are recorded.
- [ ] Policy package XML/BIN hashes match Phase 3 V2.9, or a changed package has its own reviewed conversion and reference evidence.
- [ ] `/data` or the selected artifact location has sufficient space and is writable.
- [ ] This protocol is reviewed, all TBD fields are resolved and status changes to `FROZEN_APPROVED` before execution.

## Frozen candidate

- Device: explicit `CPU`
- Precision: explicit `f32`
- Performance hint: `LATENCY`
- Input contract: `state float32[1,6]`, `wrist_image float32[1,3,480,640]`
- Output contract: normalized `action_chunk float32[1,100,6]`
- Correctness threshold: `rtol=1e-4`, `atol=1e-5`
- Model XML SHA-256: `54615bff5874f134521353c8240ecff6f95277e51c094b543713bc1d6c60879e`
- Model BIN SHA-256: `96c225f0676edcb44b641906e93222d0f52883a7ed6956725c904266c717848a`
- Exact DK-2500 CPU identity guard: `TBD_AFTER_HARDWARE_TRUTH`
- OpenVINO version and plugin baseline: `TBD_AFTER_SOFTWARE_TRUTH`

## Qualification sequence

1. Capture hardware/software truth and idle thermal/power baseline.
2. Verify model and reference artifact hashes.
3. Compile and load on explicit CPU FP32.
4. Run frozen-input correctness before any performance ranking.
5. Run a short segmented preprocess/inference/postprocess measurement with raw samples.
6. Review the short run and confirm host state, resource capture and absence of correctness failures.
7. Run the approved 30–60 minute stability qualification.
8. Independently recompute summaries and write the admission review.

## Experimental design

- Baseline: Phase 3 255H CPU FP32 is historical comparison only, not the DK-2500 pass threshold.
- Single changed platform variable: DK-2500 hardware/software environment.
- Warmup iterations: `10`, subject to pre-run review after device truth.
- Short measured iterations: `100`.
- Stability duration: `TBD_30_TO_60_MINUTES_BEFORE_FREEZE`.
- Measurement boundary: offline synchronous inference; segmented pre/post measurements are diagnostic and separately measured.
- Input policy: frozen reference input for regression plus `TBD` representative changing-input stream for Phase 4 stability if available.

## Hard gates

- Explicit DK-2500 CPU identity passes.
- Compile and load complete without fallback to another device.
- Output shape and dtype match the frozen contract.
- Correctness passes before performance measurement.
- Stability completes the frozen duration.
- Inference exceptions: `0`.
- Non-finite outputs: `0`.
- Correctness failures: `0`.
- Process crashes or watchdog timeouts: `0`.
- Required evidence files are complete.

Latency, RAM trend, temperature, frequency, utilization, power proxy and throttle observations must be reported. Their admission thresholds remain `TBD` and must be frozen or explicitly classified as diagnostic before execution.

## Stop and recovery

- Stop immediately on incorrect or non-finite output, process crash, device identity mismatch or unbounded temperature/power condition.
- Do not switch automatically to GPU, NPU, AUTO or HETERO.
- Do not continue to performance ranking after correctness failure.
- Preserve partial evidence before recovery.
- Maximum qualification attempts and retry policy: `TBD_BEFORE_FREEZE`.

## Evidence contract

- Hardware and software manifests.
- Command/configuration record and Git commit.
- Policy and reference hashes.
- Correctness JSON.
- Raw latency CSV and structured summary.
- Synchronized resource, thermal, frequency, utilization and power/throttle evidence where supported.
- Stability result and review.
- Phase 4 admission decision referencing this protocol.

## Pre-run decision

No command in this protocol is authorized while any `TBD` remains material or the status is `DRAFT_NOT_FROZEN_NOT_AUTHORIZED_FOR_EXECUTION`.
