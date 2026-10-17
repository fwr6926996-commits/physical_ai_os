# Phase 5A Package Boundaries

Status: `OWNER_ACCEPTED_PENDING_PR_5_MERGE`

The human Owner accepted these package boundaries on `2026-10-17`. They become the Phase 5A
architecture baseline when PR #5 is merged. This creates no runtime or hardware authorization.

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
- Phase 5A uses explicit `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`; no global host setting is changed.
- The initial bounded `ActionBuffer` has capacity one and latest-valid-value replacement semantics.
- Package names and directory layout are accepted for the initial offline Phase 5A Core path.

## Closed `SIG-A0` questions

1. Rosetta remains deferred and may later appear only behind a project-owned adapter.
2. `ros2_so_arm` and `feetech_ros2_driver` remain deferred behind the execution/safety boundary.
3. `physical_ai_runtime` owns clock selection, action age and the bounded buffer.
4. Reproducible Phase 5A tests use explicit `rmw_fastrtps_cpp`.
5. `interface_mapping.md` records the Owner-approved version 1 field baseline.

The optional Jazzy, mock-only `ros2_so_arm` compatibility spike is not required for this handoff.
Its trigger is a future, separately authorized ros2_control/mock-hardware integration decision.
