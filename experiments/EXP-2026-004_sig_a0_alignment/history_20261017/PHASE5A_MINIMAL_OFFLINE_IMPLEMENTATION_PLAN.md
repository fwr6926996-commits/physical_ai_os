# Phase 5A Minimal Offline Implementation Plan

Status: `FINAL_PROPOSAL_PENDING_INTERFACE_CORRECTION_REVIEW`

This plan becomes executable only after the interface-correction PR is approved and merged and the
Owner separately authorizes Phase 5A implementation. It permits offline replay, deterministic fake
policy output, mock safety and mock execution only.

## Goal

Implement the smallest reproducible path that proves project-owned contracts, Gate T0 timing,
capacity-one buffer behavior and the non-bypassable SafetyFilter boundary:

`ReplayObservation -> FakePolicy -> capacity-one ActionBuffer -> Execution consumer
-> internal CommandCandidate -> SafetyFilter -> ControlCommand
-> mock execution -> RuntimeMetrics`

It does not qualify deployment, real-time behavior, physical safety or robot task success.

## Environment and dependency boundary

- Use a new isolated workspace under `projects/so101_L1/ros2/phase5a_ws/` with separate
  `build/`, `install/` and `log/` directories.
- Do not modify or source the Phase 4 OpenVINO environment.
- Do not install system packages, Python packages, upstream repositories or drivers during the
  first implementation step.
- First inventory the existing Ubuntu 24.04 and ROS 2 Jazzy installation read-only, including
  `ros2`, `colcon`, `ament_cmake`, standard message packages and `rmw_fastrtps_cpp`.
- If any required dependency is absent, stop and present an exact installation and rollback proposal
  for separate approval.
- Build only the five project packages in this workspace. Do not build or clone Rosetta,
  `ros2_so_arm`, `feetech_ros2_driver` or the policy-execution prototype.
- Select `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` per launch/test command. Do not export it globally.

## Minimal implementation slices

1. `physical_ai_interfaces`
   - Define `ClockedTimestamp` and the corrected version 1 logical contracts.
   - Add schema constants and validation helpers or tests.
2. `physical_ai_replay`
   - Publish a small deterministic fixture with RGB metadata, ordered state and all Observation
     timestamps.
   - No camera, serial device or hardware discovery.
3. `physical_ai_policy_adapter`
   - Implement `FakePolicy` with deterministic one-action output.
   - Preserve source observation identity, model version, action step and validity.
4. `physical_ai_runtime`
   - Implement a capacity-one buffer with replacement, expiry and stale counters.
   - Prepare only an internal `CommandCandidate`.
   - Compute metrics only from compatible Gate T0 timestamps.
5. `physical_ai_safety_bridge` and mock executor
   - Publish a mock six-state `SafetyState`.
   - Run `SafetyFilter` before producing `ControlCommand`.
   - Accept commands only in fresh mock `RUNNING` state with a matching acknowledgement.
   - Never load a robot driver or open a serial device.

## Required tests

- Schema/version, array-length, ordering, unit, finite-value and validity checks.
- Gate T0 same-domain arithmetic and cross-domain rejection.
- Wall-clock jump or simulated-time negative test while monotonic intervals remain valid.
- Deterministic replay identity and timing propagation.
- Capacity-one replacement, empty read, expiry, stale drop and counter monotonicity.
- `PolicyOutput` cannot reach mock execution without command preparation and `SafetyFilter`.
- All non-permitted safety states reject execution; `FAULT`/`SAFE` cannot reset directly to
  `RUNNING`; `DEGRADED` is non-permitted in Phase 5A.
- Clean startup, normal shutdown and one controlled node-failure path.
- `RuntimeMetrics` raw time points agree with derived values; run summaries report
  P50/P95/P99/max and clock-contract identity.
- Static scan confirms no driver package, serial path, firmware command or hardware topic is used.

## Evidence

Preserve in a new dated Phase 5A experiment directory:

- read-only environment snapshot;
- exact package and file allowlist;
- dependency inventory and build command;
- unit and integration test output;
- launch parameters including explicit RMW;
- deterministic fixture identity;
- metrics event log and run summary;
- negative-test evidence for cross-clock, expiry and permission rejection;
- Git commit and clean isolated-workspace status.

## Stop conditions

Stop before implementation or build if the correction PR is not merged, a required dependency is
missing, the workspace would source or modify Phase 4, a test needs upstream code, or any path would
touch a camera, serial device, firmware, actuator or robot. A required change to the frozen states,
protected ownership or SafetyFilter order requires a separate ADR and Owner approval.

## Acceptance for the minimal offline slice

- All five project contracts compile and validate against the corrected baseline.
- Deterministic replay reaches mock execution only through the capacity-one buffer and
  `SafetyFilter`.
- Expired, stale, cross-clock or unpermitted inputs produce no `ControlCommand` accepted by the mock
  executor.
- Gate T0 metadata and the complete nine-point time chain are present and internally consistent.
- Tests and evidence are reproducible without Phase 4 mutation or hardware access.
- The conclusion is limited to `PHASE5A_MINIMAL_OFFLINE_FUNCTIONAL_PATH_PASS`.
