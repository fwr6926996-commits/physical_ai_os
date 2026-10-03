# Phase 4 DK 2500 CPU FP32 Qualification Protocol

Protocol ID: `P4-DK2500-CPU-FP32-001`

Template version: `0.1`

Workflow version: `0.1`

Status: `DRAFT_FREEZE_PROPOSAL_NOT_AUTHORIZED_FOR_EXECUTION`

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
- [x] Physical-intervention rule: the human owner selected the strict no-touch SSH route. Current wiring and placement remain unchanged; any need for board handling, cable change or physical reset stops the run. Do not directly ground the PCB or improvise a mains connection.
- [ ] This protocol is independently reviewed, the freeze proposal is explicitly accepted and status changes to `FROZEN_APPROVED` before execution.

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

## Freeze proposal — human acceptance pending

- OpenVINO baseline: exact observed `2026.2.1-21919-ede283a88e3-releases/2026/2`
- Device/precision/hint: explicit `CPU` / `f32` / `LATENCY`; no fallback
- Warmup: `10` iterations
- Short measurement: `100` iterations
- Stability duration: `30 minutes`
- Stability input: frozen `reference_model_input.pt` only
- Correctness check: every inference, `rtol=1e-4`, `atol=1e-5`
- Latency sample: every inference; summary window `60 seconds`
- External telemetry interval: `5 seconds`
- Infer loss-of-progress watchdog: `15 seconds` without evidence growth
- Startup/compile evidence timeout: `180 seconds`
- Software thermal stop: any observed core/package sensor `>=100°C`; the exposed core critical limit is `105°C`
- Maximum attempts: one attempt per qualification stage per explicit human authorization; no automatic retry
- Recovery: preserve partial evidence, send `SIGTERM`, wait `5 seconds`, then `SIGKILL` if still alive
- Physical route: strict no-touch SSH; any required physical intervention stops the run

The frozen reference input supports regression and repeated-call stability only. Representative
changing-input behavior is a future experiment and is not an admission claim of this protocol.

## Qualification sequence

1. Capture hardware/software truth and idle thermal/power baseline.
2. Verify model and reference artifact hashes.
3. Compile and load on explicit CPU FP32.
4. Run frozen-input correctness before any performance ranking.
5. Run a short segmented preprocess/inference/postprocess measurement with raw samples.
6. Review the short run and confirm host state, resource capture and absence of correctness failures.
7. Run the approved 30-minute stability qualification.
8. Independently recompute summaries and write the admission review.

## Experimental design

- Baseline: Phase 3 255H CPU FP32 is historical comparison only, not the DK-2500 pass threshold.
- Single changed platform variable: DK-2500 hardware/software environment.
- Warmup iterations: `10`, subject to pre-run review after device truth.
- Short measured iterations: `100`.
- Stability duration proposal: `30 minutes`.
- Measurement boundary: offline synchronous inference; segmented pre/post measurements are diagnostic and separately measured.
- Input policy proposal: frozen reference input only. Changing-input stability is explicitly out of scope.

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

Latency, RSS/available-memory trend, frequency, utilization and throttle-counter deltas must be
reported but are diagnostic-only because no end-to-end control budget or validated resource limit
exists. The 120 W adapter rating is configuration evidence, not workload power; RAPL is unavailable.
These observations cannot independently fail correctness/stability admission, but they may require a
separate performance or thermal decision. Temperature `>=100°C` is a hard stop, not a pass threshold.

## Stop and recovery

- Stop immediately on incorrect or non-finite output, process crash, device identity mismatch or unbounded temperature/power condition.
- Do not switch automatically to GPU, NPU, AUTO or HETERO.
- Do not continue to performance ranking after correctness failure.
- Preserve partial evidence before recovery.
- One attempt per stage (`compile/correctness`, short measurement, 30-minute stability) per explicit
  human authorization. No automatic retry. Infrastructure failure, watchdog timeout or incomplete
  evidence stops the stage; any rerun requires preserved prior evidence, a new run ID, a written
  classification and new human authorization.
- Infer loss-of-progress watchdog: `15 seconds`. Startup/compile evidence timeout: `180 seconds`.
- Supervisor recovery: preserve available evidence, send `SIGTERM`, wait `5 seconds`, then send
  `SIGKILL` if the Worker has not exited.

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

No qualification command is authorized while the status is
`DRAFT_FREEZE_PROPOSAL_NOT_AUTHORIZED_FOR_EXECUTION`. The freeze proposal requires explicit human
acceptance and an independent pre-run review before the status may become `FROZEN_APPROVED`.

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
- Hardware truth is sufficient for entry configuration. Fan RPM and electrical power are
  unavailable; thermal, frequency and throttle behavior must therefore be captured as runtime
  evidence.
- The human owner selected the strict no-touch SSH route. Board handling, cable changes and physical
  reset stop the run.
- Duration, diagnostic-only resource treatment, frozen-input scope, attempt limit and recovery are
  now proposed for human acceptance above.
- Protocol status remains `DRAFT_FREEZE_PROPOSAL_NOT_AUTHORIZED_FOR_EXECUTION`.
