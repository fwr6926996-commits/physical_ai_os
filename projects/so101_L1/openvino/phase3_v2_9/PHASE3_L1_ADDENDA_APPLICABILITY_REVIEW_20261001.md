# Phase 3 L1 Addenda Applicability Review

Review ID: `P3-V2.9-L1-ADDENDA-REVIEW-20261001`

Date: `2026-10-01`

Status: `ACCEPTED AS GOVERNING DESIGN COMPANIONS`

## Documents reviewed

1. `docs/reference/l1/L1V2.9_Deep_Research_Architecture_Audit_Addendum_01_正式版.docx`
   - SHA-256: `eb34eedec544d8f327a321b9e4188055ffcd54aee4a44b7672cb5955e95e8091`
   - Approved: `2026-09-23`
2. `docs/reference/l1/L1V2.9_Portability_Addendum_02_正式版.docx`
   - SHA-256: `e3b4aea1b8cdcf425762fa980d4bc6189e109f726d9238bea6f1c146dc7551b6`
   - Approved: `2026-09-23`

The documents were reviewed as design and governance sources, not as execution instructions. Actual
engineering claims continue to come from repository configuration, tests, logs and preserved
evidence.

## Addendum 01 effect

Addendum 01 retains the V2.9 technical route and Phase order while adding four evidence gates and
five supporting records:

- Gate T0: clock and timestamp contract;
- Gate RT0: host real-time evidence;
- Gate SC0: Safety Case Lite;
- Gate W0: MCU self-failure coverage;
- Evidence O M1: OpenVINO execution metadata;
- Evidence R M1: actual ROS 2 execution identity;
- ADR 01: custom Runtime versus `ros2_control` boundary;
- Research Bridge RB 01: synchronous/asynchronous action-chunk semantics;
- VM1: version-drift watch.

It explicitly preserves completed Phase 3 and permits only a non-retroactive O M1 recovery pass over
existing configuration, logs and reports. Fields that cannot be recovered reliably are historical
evidence gaps; they do not authorize reruns or reversal of the closeout.

## Addendum 02 effect

Addendum 02 adds portability contracts without adding a new main Phase:

- separate portable source assets from exchange artifacts and target-platform artifacts;
- keep vendor APIs behind a unified `InferenceBackend` boundary;
- keep robot-specific units and mappings in device adapters;
- make Observation, Action and PolicyOutput schemas versioned and vendor-neutral;
- require backend capability, health, shutdown and failure behavior to be explicit;
- add Gate PR for portability readiness and E1 for a later real second-backend migration.

It also confirms that interface portability is not proof of functional-safety certification or
equivalent task behavior on another robot or platform.

## Design–Reality reconciliation

Both documents use broad language that Phase 3 was completed or passed under the original V2.9
baseline. Repository evidence provides the more precise actual state:

- experimental work: complete;
- engineering gate: `PARTIAL_PASS_CPU_FP32_ONLY`;
- CPU FP32: admitted on the frozen 255H scope;
- GPU.0: correctness passed but stability failed and remains `CLOSED_NOT_ADMITTED`;
- NPU and reduced precision: not admitted;
- learning verification: passed and accepted on `2026-10-01`;
- Phase 4: not started.

Therefore, the addenda's non-retroactive preservation rule protects the completed Phase 3 decision;
it does not convert the actual partial gate into a full pass or admit a failed backend. This is an
interpretation boundary, not a rejection of either addendum.

## Recoverable Phase 3 metadata

Existing evidence can recover much of O M1, including OpenVINO/plugin versions, device identity,
precision, model/input/output shapes, performance hint, compile/load/warmup state and the frozen
Policy Package hashes. Fields such as streams, requests, inference-thread controls, core scheduling
and CPU pinning must be recorded only when explicitly present in preserved evidence. Absence must be
marked `LEGACY_EVIDENCE_GAP`; no value may be inferred and no Phase 3 rerun is authorized.

Addendum 02's asset model also clarifies that the portable Policy source identity is not identical to
the OpenVINO IR. The IR is a target-platform artifact whose reproducibility depends on preserved
source assets, toolchain versions and conversion records.

## Forward gate impact

This review does not start Phase 4. Before Phase 4 execution:

1. retain the existing ADR-0001 CPU-only entry scope;
2. capture DK-2500 hardware/software truth;
3. perform VM1 drift review;
4. freeze the Phase 4 protocol;
5. apply the full O M1 metadata contract to new DK-2500 evidence;
6. preserve explicit CPU FP32 identity, correctness, bounded recovery and stop behavior.

T0, R M1, RT0, ADR 01, SC0, W0, Gate PR and E1 remain assigned to their stated later phases. They
must not be pulled into Phase 3 retrospectively or treated as already passed.

## Final decision

- Accept both Addenda as binding V2.9 companion documents.
- Keep the Phase 3 engineering result `PARTIAL_PASS_CPU_FP32_ONLY`.
- Keep GPU.0 not admitted.
- Accept Phase 3 independent learning verification.
- Close Phase 3 final human acceptance.
- Keep Phase 4 not started.
