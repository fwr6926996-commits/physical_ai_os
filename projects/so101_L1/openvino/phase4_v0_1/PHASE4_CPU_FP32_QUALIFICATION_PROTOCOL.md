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

- [x] DK-2500 hardware manifest is complete for entry. CPU, EDAC memory channel/size topology, storage, firmware/BIOS, 120 W adapter, active fan/heatsink assembly, open-board placement and approximately 20°C unobstructed ambient setup are captured in `DK2500_HARDWARE_SOFTWARE_TRUTH_20261003.md`. Memory vendor/part/speed and fan RPM are descriptive or measurement gaps, not inferred facts.
- [x] DK-2500 software baseline is captured, including OS, kernel, OpenVINO, CPU plugin and relevant driver versions.
- [x] Available OpenVINO devices and full names are recorded: CPU and NPU are visible; GPU is not visible in the current userspace baseline.
- [x] VM1 drift decision is accepted. Option A preserves the observed OpenVINO 2026.2.1 target baseline; no OpenVINO upgrade or GPU runtime installation is authorized.
- [x] Policy Package was copied to the target and all eight selected files independently matched their source SHA-256 values. Evidence: `evidence/phase4_0_truth/policy_package_transfer_verification_20261003.json`.
- [x] Selected artifact location `/home/hepintel/physical_ai_os_artifacts/phase4_entry/policy_package_v2_9` is writable and had approximately 60 GB free before the 338 MB transfer.
- [ ] Physical-intervention rule is frozen before execution: either establish ESD handling control before any board handling/cable change, or use a strict no-touch SSH route in which the current wiring and placement remain unchanged and any need for physical intervention stops the run. Do not directly ground the PCB or improvise a mains connection.
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
- Exact DK-2500 CPU identity guard candidate: `Intel(R) Core(TM) Ultra 5 225U`
- Accepted OpenVINO baseline candidate: `2026.2.1-21919-ede283a88e3-releases/2026/2`; Option A was accepted by the human owner on 2026-10-03 and will become frozen only with the complete protocol

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

- Hardware and software manifests, beginning with
  `evidence/phase4_0_truth/dk2500_truth_20261003.json`.
- Target-side Policy Package identity evidence:
  `evidence/phase4_0_truth/policy_package_transfer_verification_20261003.json`.
- Command/configuration record and Git commit.
- Policy and reference hashes.
- Correctness JSON.
- Raw latency CSV and structured summary.
- Synchronized resource, thermal, frequency, utilization and power/throttle evidence where supported.
- Stability result and review.
- Phase 4 admission decision referencing this protocol.

## Pre-run decision

No command in this protocol is authorized while any `TBD` remains material or the status is `DRAFT_NOT_FROZEN_NOT_AUTHORIZED_FOR_EXECUTION`.

## Entry review update — 2026-10-03

- Direct Ethernet SSH identity is established and independently verified.
- Initial hardware/software truth is captured without model execution or system mutation.
- CPU identity is known; OpenVINO CPU and NPU are visible.
- GPU is not visible because the Intel GPU userspace compute runtime is not installed; this does not
  block the CPU-only route and does not authorize a driver installation.
- VM1 found material drift from the Phase 3 runtime baseline. The human owner accepted Option A:
  preserve OpenVINO 2026.2.1 as the DK-2500 baseline candidate without upgrading it.
- The CPU FP32 Policy Package was copied to the dedicated target artifact directory. All eight
  selected file hashes match; rejected INT8 candidates were intentionally excluded. No model was
  loaded or executed.
- Hardware truth is sufficient for entry configuration. Stability duration, resource thresholds,
  input stream and retry policy remain unresolved. Fan RPM and electrical power are unavailable;
  thermal, frequency and throttle behavior must therefore be captured as runtime evidence.
- ESD handling control is not established. Board handling and cable changes remain blocked. Before
  qualification, select either a verified ESD handling route or a strict no-touch SSH route.
- Protocol status remains `DRAFT_NOT_FROZEN_NOT_AUTHORIZED_FOR_EXECUTION`.
