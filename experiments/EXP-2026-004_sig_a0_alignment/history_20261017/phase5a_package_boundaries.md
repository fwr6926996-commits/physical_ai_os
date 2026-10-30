# Phase 5A Package Boundaries

Status: `INTERFACE_CORRECTION_PROPOSED_PENDING_OWNER_REVIEW`

The package split and SIG-A0 component dispositions remain accepted. The field baseline and command
ordering are corrected against L1 V2.9 and the binding addenda before any core message definition is
implemented.

## Proposed source root

`projects/so101_L1/ros2/phase5a_ws/src/`

No source directory or package is created by this correction.

## Minimal package split

| Proposed package | Owns | Must not own |
|---|---|---|
| `physical_ai_interfaces` | Project-owned representations of the five frozen L1 contracts and Gate T0 timestamp metadata | Policy implementation, driver logic or hardware permission |
| `physical_ai_replay` | Offline `ReplayObservation`, recorded-input timing and deterministic fixtures | Live camera/device ownership or command output |
| `physical_ai_policy_adapter` | `FakePolicy` first; later replaceable `InferenceBackend` adapter | Command execution, safety permission or unbounded queues |
| `physical_ai_runtime` | Capacity-one `ActionBuffer`, freshness, internal `CommandCandidate` preparation and `RuntimeMetrics` | Servo access, MCU reset or direct executable-command bypass |
| `physical_ai_safety_bridge` | Project `SafetyState`, MCU acknowledgement mapping and `SafetyFilter` input | Replacing STM32/Zephyr authority or enabling real hardware in Phase 5A |

## Intended offline Phase 5A flow

`ReplayObservation -> FakePolicy -> capacity-one ActionBuffer -> Execution consumer
-> internal CommandCandidate -> SafetyFilter -> ControlCommand
-> mock execution -> RuntimeMetrics`

Even mock execution uses the same fail-closed permission boundary. No package may publish an
executable `ControlCommand` before `SafetyFilter` accepts a fresh candidate and state.

## Ownership constraints

- Project contracts remain the source of truth; upstream messages require adapters.
- `SafetyState` uses the frozen six-state V2.9 vocabulary.
- Every logical time field follows Addendum 01 Gate T0.
- Stale or expired observations, policy outputs and candidates fail closed.
- ROS 2 Jazzy remains the baseline.
- Tests set `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` explicitly; no global host setting changes.
- The initial `ActionBuffer` has capacity one and latest-valid-value replacement semantics.
- Package names and layout are unchanged by the correction.

## Preserved SIG-A0 decisions

Rosetta, `ros2_so_arm` and `feetech_ros2_driver` remain deferred. The policy-execution prototype and
captured demos remain reference-only. No upstream component enters the Core dependency set. The
optional Jazzy mock-only `ros2_so_arm` spike still requires a separate decision.
