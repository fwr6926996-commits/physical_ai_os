# Current Phase 3 Execution

The active Phase 3 execution is `phase3_v2_9/` and follows L1 V2.9 plus the repository `AGENT.md` learning and delegation policy.

The earlier files in `policy_package_v1/`, `phase3_gate_summary.json`, `phase3_runtime_config.yaml`, and `PHASE3_COMPLETION_REPORT.md` are retained as the V2.8 historical baseline. They are not sufficient to claim V2.9 Phase 3 completion because V2.9 adds segmented latency and resource evidence, FP32/FP16 and INT8 deployment evidence, bottleneck localization, and an independent learning check.

Current status: `V2_9_EXPERIMENTAL_WORK_COMPLETE__PARTIAL_PASS_CPU_FP32_ONLY__FINAL_HUMAN_ACCEPTANCE_PENDING`

Current report: `phase3_v2_9/PHASE3_FINAL_REPORT.md`

Current runtime configuration: `phase3_v2_9/active_runtime_config.yaml`

Retrospective acceptance record: `phase3_v2_9/PHASE3_RETROSPECTIVE_AND_ACCEPTANCE.md`

GPU.0 is closed as not admitted after two consecutive formal isolated-worker stability failures. CPU FP32 is the only backend that passed correctness and the 30-minute stability gate.

Phase 4 has not started.

The historical V2.8 report, summary and runtime configuration remain evidence only. They are marked `ARCHIVED_DO_NOT_DEPLOY`; no V2.8 GPU-primary configuration is active.
