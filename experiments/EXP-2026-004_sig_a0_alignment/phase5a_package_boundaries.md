# Phase 5A Package Boundaries — Review Draft

Status: `DRAFT_FOR_SIG_A0_REVIEW`

This document supplies package boundaries for comparison during `SIG-A0`. It does not freeze the
Phase 5A architecture and creates no runtime or hardware authorization.

## Proposed source root

`projects/so101_L1/ros2/phase5a_ws/src/`

No source directory or package is created by the activation package.

## Minimal package split

| Proposed package | Owns | Must not own |
|---|---|---|
| `physical_ai_interfaces` | Project-owned representations of the five frozen L1 contracts | Policy implementation, driver logic or hardware permission |
| `physical_ai_replay` | Offline `ReplayObservation`, recorded-input timing and deterministic replay fixtures | Live camera/device ownership or command output |
| `physical_ai_policy_adapter` | `FakePolicy` first; later replaceable `InferenceBackend` adapter | Command execution, safety permission or unbounded queues |
| `physical_ai_runtime` | Bounded `ActionBuffer`, expiry handling, command preparation and `RuntimeMetrics` | Servo access, emergency-stop reset or model-specific message truth |
| `physical_ai_safety_bridge` | Project boundary between Linux `SafetyFilter` decisions and MCU permission state | Replacing STM32/Zephyr authority or enabling real hardware in Phase 5A |

## Intended offline Phase 5A flow

`ReplayObservation -> FakePolicy -> bounded ActionBuffer -> mock execution -> RuntimeMetrics`

`SafetyState` gates mock execution through the same project-owned boundary expected for later
hardware work. The activation package does not implement that path.

## Ownership constraints

- Project contracts remain the source of truth; upstream messages require adapters.
- Upstream drivers may not own policy timing, action freshness or safety permission.
- The queue is bounded and stale or expired actions must fail closed.
- Phase 5A starts with offline replay and mock execution.
- ROS 2 Jazzy remains the baseline; a distribution change requires a separate ADR.
- Package names and directory layout remain reviewable until `SIG-A0` is accepted.

## Questions `SIG-A0` must close

1. Can Rosetta map topics, timestamps, QoS and missing-frame behavior without redefining
   `Observation` or `PolicyOutput`?
2. Can `ros2_so_arm` and `feetech_ros2_driver` remain behind the execution/safety boundary?
3. Which package owns clock selection and action-age computation?
4. Which RMW is selected for reproducible Phase 5A tests?
5. What exact field-level schemas implement the five already frozen contract names?
