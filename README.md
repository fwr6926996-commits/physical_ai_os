# Physical AI Runtime Lab

## Current L1 Project

SO-101 Physical AI × Robot Runtime × Real-Time Safety

## Core execution chain

SO-101 real-world data
→ RTX 5060 ACT training
→ Intel Core Ultra OpenVINO
→ ROS 2 / C++ Runtime
→ STM32 + Zephyr Safety Runtime
→ Fault injection and reproducible evaluation

## Frozen runtime interfaces

- Observation
- PolicyOutput
- ControlCommand
- SafetyState
- RuntimeMetrics

## Current phase

Phase 4 is closed as `PASS — CPU FP32 OFFLINE BACKEND ONLY`. Only the exact frozen DK-2500 CPU FP32
offline synchronous backend is admitted. Changing-input behavior, real-time control, the complete
control chain and physical safety remain outside this admission and are routed forward.

Current operational record:
`projects/so101_L1/openvino/phase4_v0_1/PHASE4_ACCEPTANCE_AND_CLOSURE_20261015.md`

SIG-A0 architecture alignment and the Phase 5 design handoff were accepted by the human owner on
`2026-10-27`, with no new upstream runtime dependency. A subsequent bounded T0-L 0.2 authorization
covered local synthetic logic, mock evidence checks and one formal suite after development and
freeze. That suite matched all 34 expected outcomes: `T0_L_LOGIC_AND_MOCK_EVIDENCE_PASS`.
The human owner accepted this bounded offline Mock result on `2026-10-27`.
Full Gate T0, ROS integration, model integration and
physical execution remain outside this result; the formal run has been used once.

Current Phase 5 decision:
`experiments/EXP-2026-004_sig_a0_alignment/SIG_A0_ACCEPTANCE_20261027.md`

Current T0-L implementation and evidence review:
`experiments/EXP-2026-004_sig_a0_alignment/t0_implementation_20261027/REVIEW.md`

Current T0-L human acceptance:
`experiments/EXP-2026-004_sig_a0_alignment/t0_acceptance_20261027/ACCEPTANCE.md`

T0-H 0.1 subsequently verified native Linux clock binding and local producer/executor pipes under
its own bounded authorization. The single frozen formal suite matched all 12 expected outcomes:
`T0_H_NATIVE_CLOCK_AND_LOCAL_PIPE_MOCK_PASS`. Human result acceptance is pending; full Gate T0
and ROS/model/hardware integration remain outside this result.

Current T0-H evidence review:
`experiments/EXP-2026-004_sig_a0_alignment/t0_host_implementation_20261027/REVIEW.md`

## Planning and governance

- Governing L1 documents: `docs/reference/l1/README.md`
- Phase 4 CPU-only entry decision: `docs/decisions/ADR-0001-phase4-cpu-only-entry.md`
- ROS Physical AI SIG alignment decision:
  `docs/decisions/ADR-0002-ros-physical-ai-sig-alignment.md`
- Phase 4 to Phase 5 upstream review protocol:
  `docs/protocols/SIG-A0_UPSTREAM_ALIGNMENT_REVIEW.md`

The SIG alignment track becomes a bounded Phase 5 entry review; it is not a new phase and was not
a dependency of Phase 4 completion.
