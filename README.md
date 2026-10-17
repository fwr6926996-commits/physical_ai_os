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

## Planning and governance

- Governing L1 documents: `docs/reference/l1/README.md`
- Phase 4 CPU-only entry decision: `docs/decisions/ADR-0001-phase4-cpu-only-entry.md`
- ROS Physical AI SIG alignment decision:
  `docs/decisions/ADR-0002-ros-physical-ai-sig-alignment.md`
- Planned Phase 4 to Phase 5 upstream review:
  `docs/protocols/SIG-A0_UPSTREAM_ALIGNMENT_REVIEW.md`

The SIG alignment track becomes a bounded Phase 5 entry review; it is not a new phase and was not
a dependency of Phase 4 completion.
