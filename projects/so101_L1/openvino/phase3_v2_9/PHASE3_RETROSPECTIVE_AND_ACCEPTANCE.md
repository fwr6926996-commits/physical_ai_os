# Phase 3 Retrospective and Acceptance

Acceptance record ID: `P3-V2.9-ACCEPTANCE-001`

Workflow basis: retrospective review under Engineering Workflow `0.1`

Decision date: `2026-09-23`

Post-closeout evidence: see
`PHASE3_REVIEW_ROUTE_FEEDBACK_ADDENDUM_20261001.md`. The addendum narrows the GPU.0 observed failure
boundary but does not change this historical gate decision.

## Outcome

- Experimental work: `COMPLETE`
- Engineering gate: `PARTIAL_PASS_CPU_FP32_ONLY`
- Learning verification: `PASS — ACCEPTED 2026-10-01`
- Final human acceptance: `ACCEPTED — PARTIAL PASS CPU FP32 ONLY`
- Phase 4 entry: `ALLOWED_WITH_WAIVER_FOR_CPU_ONLY_QUALIFICATION`

This review does not rewrite Phase 3 as if Workflow 0.1 had governed the original experiments. Original evidence remains unchanged. The review records which practices were present, which were introduced during the work and which become prospective requirements for Phase 4.

## Gate matrix

| Gate | Requirement | Evidence | Result | Limitation or follow-up |
|---|---|---|---|---|
| Hardware and software truth | Bind conclusions to the 255H host, runtime and policy identities | `hardware_manifest.yaml`, `software_baseline.yaml`, Phase 3.0 evidence | PASS WITH GAP | Device identity is strong; future qualification must add synchronized frequency, utilization, power-state and throttle evidence where available |
| Export and CPU compile/load | Preserve the policy contract and validate the FP32 path | Phase 3.1 conversion and review evidence | PASS | Offline model path only |
| CPU FP32 correctness and latency | Correctness before formal performance | Phase 3.2 correctness, CSV and review | PASS | Frozen single-input correctness is a regression gate, not task-level generalization |
| CPU FP32 stability | Complete the human-selected 30-minute gate | Streamed 30-minute result and review | PASS | One offline synchronous run is not a long-term reliability or robot-safety claim |
| GPU.0 FP32 | Correctness and required stability | Correctness evidence; monolithic and isolated stability failures | FAIL CLOSED | Correctness passed, but repeated inference stalls prevented stability admission; exact native root cause remains unknown |
| Reduced precision and NPU | Pass correctness/support before performance ranking | Precision matrix evidence | FAIL OR UNSUPPORTED | Compatibility evidence retained; candidates are not admitted |
| INT8 feasibility | Produce reproducible feasibility evidence and reject an incorrect candidate | INT8 manifest, fidelity report and closure | CLOSED NEGATIVE | Task-level tolerance was not frozen before characterization; future recovery requires a new protocol and human decision |
| Bottleneck localization | Capture and interpret a real profile | CPU profiling evidence and review | PASS | CPU-specific, inference-only and profiling-instrumented |
| Independent learning | Explain admission, interfaces, debugging path and safety boundary | Existing learning checks | PENDING FINAL CHECK | Must remain separate from engineering closeout |

## Retrospective findings

### Practices that worked

- Correctness was required before performance ranking.
- Hardware identity, model hashes and input/output contracts were recorded.
- GPU.0 correctness was not confused with stability admission.
- The isolated GPU sequence had a human-frozen maximum-run and consecutive-failure stop rule.
- INT8 failure was preserved as scoped negative evidence rather than generalized to all INT8 or NPU paths.
- Reports consistently separated offline inference qualification from physical robot safety.

### Process gaps

- Phase 3 artifacts and evidence were not bound to a repository commit during execution.
- V2.8 GPU-primary material remained beside the active V2.9 result and could be mistaken for current configuration.
- Exploratory diagnostics and qualification evidence were distinguishable in prose but not governed by one prospective protocol system.
- The INT8 task-relevant admission metric was intentionally deferred until after characterization, so the run supports characterization and rejection, not a precommitted task-accuracy qualification.
- The GPU watchdog localized loss of progress to the synchronous inference interval but did not capture native stacks, kernel GPU fault state or device-engine telemetry sufficient for root cause.
- Host frequency, utilization, power state and throttle controls were incomplete for cross-run performance attribution.
- Machine-readable schemas and automated consistency checks were not yet present.

## Admission

### Admitted

Only explicit OpenVINO `CPU` with FP32, `LATENCY`, the frozen V2.9 policy hashes and the ThinkBook 255H identity guards is admitted. The active configuration is `active_runtime_config.yaml`.

### Not admitted

GPU.0, GPU.1, NPU, AUTO, HETERO, CPU/GPU FP16 and INT8 are not admitted. GPU.0 is closed for Phase 3 deployment after the frozen stop rule; INT8 is closed as current-candidate negative evidence.

Historical V2.8 files are marked `ARCHIVED_DO_NOT_DEPLOY` and cannot define an active runtime.

## Unresolved work and reopening

- GPU.0 root cause remains unlocalized. No Phase 3 Round 3 is permitted. A future investigation requires a new diagnostic protocol with native and kernel-level observability.
- INT8 recovery remains unauthorized. Reopening requires precommitted task metrics and a new architecture decision.
- Final independent learning verification passed and was accepted on `2026-10-01`; see
  `PHASE3_INDEPENDENT_LEARNING_VERIFICATION.md`.

## Next-phase decision

ADR-0001 permits Phase 4 planning and, after entry prerequisites are met, CPU-only qualification on DK-2500. It does not admit the 255H GPU result, claim DK-2500 compatibility or start Phase 4 automatically.

The first Phase 4 action must be hardware/software truth and protocol freeze. No robot motion is authorized by this record.
