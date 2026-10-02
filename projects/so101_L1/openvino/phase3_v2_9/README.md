# Phase 3 V2.9 255H Intel Pre Deployment

This directory is the active, clean-room evidence workspace for the V2.9 Phase 3 rerun. It preserves the previous V2.8 artifacts unchanged and references them only as historical comparison data.

## Governing sources

- Repository policy: `/home/lucas/physical_ai_os/AGENT.md`
- L1 execution book: `/home/lucas/physical_ai_os/docs/reference/l1/SO-101_PhysicalAI_Runtime_L1_最终执行书_V2.9_S1S2_EmploymentGate增强版.docx`
- Source document SHA-256: `95cd404a72f0c03435b0728aa0bd169f78a6b782f9063a4b6659cbc953bec5ef`

## Execution modes

| Work | Mode | Human critical step |
|---|---|---|
| Baseline inventory, hashes, repetitive reruns, evidence formatting | DELEGATE | Review results |
| Export, conversion, compile/load and correctness already encountered in V2.8 | ASSIST | Review important configuration and failures |
| First segmented preprocess/inference/postprocess benchmark | LEARN | Run the first host-side benchmark and explain the boundaries |
| First INT8 PTQ feasibility experiment | LEARN | Approve calibration/accuracy design and run the first critical experiment |
| First real bottleneck profiling capture | LEARN | Run one profiling capture and interpret the dominant layer with Codex |
| Repeated device/precision benchmarks after the first example | DELEGATE | Review anomalies and evidence |
| Final Phase 3 acceptance | Human-owned | Explain, reproduce, modify, debug, and accept |

## Phase boundary

This workspace covers ThinkBook Core Ultra 7 255H pre-deployment only. DK-2500 deployment, Phase 4 long-run edge acceptance, robot motion, ROS 2 runtime integration, and later phases are out of scope.

## Closeout state

- Engineering result: `PARTIAL_PASS_CPU_FP32_ONLY`
- Active runtime: `active_runtime_config.yaml`
- Retrospective and acceptance: `PHASE3_RETROSPECTIVE_AND_ACCEPTANCE.md`
- Post-closeout Review–Route–Feedback: `PHASE3_REVIEW_ROUTE_FEEDBACK_ADDENDUM_20261001.md`
- L1 Addenda applicability review: `PHASE3_L1_ADDENDA_APPLICABILITY_REVIEW_20261001.md`
- Independent learning verification: `PHASE3_INDEPENDENT_LEARNING_VERIFICATION.md`
  (`ACCEPTED`)
- CPU-only Phase 4 entry waiver: `../../../../docs/decisions/ADR-0001-phase4-cpu-only-entry.md`
- Phase 4 has not started; the waiver permits bounded CPU-only qualification only after Phase 4 hardware/software truth and protocol freeze.
