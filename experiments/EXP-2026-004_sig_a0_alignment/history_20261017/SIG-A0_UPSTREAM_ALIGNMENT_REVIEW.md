# SIG A0 Upstream Alignment Review

Review ID: `SIG-A0`

Version: `0.2`

Status: `PASS_ARCHITECTURE_REVIEW_ONLY`

Classification: `ARCHITECTURE_REVIEW`

Owner: human

Governing decision: `docs/decisions/ADR-0002-ros-physical-ai-sig-alignment.md`

## Question and output decision

Determine which ROS Physical AI SIG interfaces, packages and reference patterns should influence or
enter L1 Phase 5 without changing the frozen Core interfaces, ROS 2 Jazzy baseline or independent
safety boundary.

This review produces component dispositions and Phase 5 design constraints. It is not a runtime
qualification, a ROS distribution migration, a robot-motion authorization or evidence that an
upstream demo is production ready.

## Activation trigger

Do not activate `SIG-A0` during the current Phase 4 thermal diagnosis or Stability decision.

Activation requires one of:

1. Phase 4 closeout accepts entry into Phase 5; or
2. a human-owned waiver explicitly permits read-only Phase 5 architecture preparation while
   preserving the Phase 4 main milestone.

The review must finish before the Phase 5A package and interface architecture is frozen.

## Activation record

- Activation date: `2026-10-17`
- Human authorization: minimal `SIG-A0` activation package approved
- Repository baseline: `bc95e2b9b2674f2e14d837fe2498b6b91637dfa2`
- Evidence root: `experiments/EXP-2026-004_sig_a0_alignment/`
- Active scope: official-source refresh, exact upstream identity capture, interface mapping and
  component disposition review
- Compatibility spike: `NOT_AUTHORIZED`
- Dependency installation, build, simulation, hardware access and robot motion: `NOT_AUTHORIZED`

At activation, the bounded architecture review was permitted to begin; activation itself was not a
`SIG-A0` pass decision and admitted no upstream component into the Phase 5 runtime.

## Closure record

- Owner decision date: `2026-10-17`
- Repository effectivity: PR #5 merged as `bb5f8712a1e30b7df23608f8bd1794fc7043ad98`
- Phase 5A RMW: explicit `rmw_fastrtps_cpp`
- Timing/buffer owner: `physical_ai_runtime`
- Linux-to-MCU permission boundary: `physical_ai_safety_bridge`
- Optional compatibility spike: not required and not authorized
- Upstream runtime admission: none; dispositions remain reference or defer

This PASS closes the bounded architecture review only. It does not authorize dependency
installation, Phase 5A implementation, build, simulation, hardware access, firmware change, robot
motion, deployment, real-time qualification or physical-safety qualification.

## Time and execution bounds

- Maximum review budget: two effective execution days.
- Maximum active compatibility spike: one candidate stack at a time.
- Default environment: isolated workspace; no installation into the active Phase 4 environment.
- Default execution: source inspection, configuration comparison, offline data, mock hardware or
  simulation.
- No robot motion, servo enable, firmware change, driver replacement or system-wide dependency
  mutation is authorized by this review.
- Network downloads, dependency installation and hardware access require a separately stated
  execution step with rollback and evidence paths.

If the timebox expires, unresolved components receive `DEFER` with a trigger. They do not block
Technical Core.

## Entry conditions

- [x] Phase 4 transition or explicit bounded waiver is recorded.
- [x] Active L1 execution book and both binding addenda match their recorded SHA-256 values.
- [x] Current repository commit and dirty-worktree state are captured.
- [x] Ubuntu, ROS distribution, RMW, compiler, Python and relevant LeRobot baselines are captured.
- [x] Phase 5 package boundaries and the five frozen L1 interfaces are available for review.
- [x] Upstream repositories, documents and REPs are refreshed from official sources.
- [x] Every source-code candidate has an exact commit or release identity before build or use.
- [x] Compatibility-spike plan is not applicable because no spike was required or authorized.

Recorded governing document identities at protocol creation:

| Document | SHA-256 |
|---|---|
| L1 V2.9 execution book | `95cd404a72f0c03435b0728aa0bd169f78a6b782f9063a4b6659cbc953bec5ef` |
| Architecture Audit Addendum 01 | `eb34eedec544d8f327a321b9e4188055ffcd54aee4a44b7672cb5955e95e8091` |
| Portability Addendum 02 | `e3b4aea1b8cdcf425762fa980d4bc6189e109f726d9238bea6f1c146dc7551b6` |

These identities are creation-time references. Activation must verify them again rather than assume
they remain current.

## Protected project boundaries

The review may map or wrap these contracts but may not silently redefine them:

- `Observation`
- `PolicyOutput`
- `ControlCommand`
- `SafetyState`
- `RuntimeMetrics`
- `InferenceBackend`
- bounded `ActionBuffer` and its stale/expired-action policy
- Linux `SafetyFilter` to STM32/Zephyr permission and emergency-stop boundary

Any material semantic change stops the review path for that component and requires an ADR.

## Work packages

### A0.1 Upstream truth snapshot

Capture:

- SIG charter, current working-group pages and latest official status report;
- exact commits, branches, licenses and dependency manifests for source candidates;
- ROS distribution, Python, LeRobot, simulator, RMW and compiler assumptions;
- release status, CI coverage and known hardware requirements;
- open design dependencies such as REP-0157, REP-0158 and native buffer support.

Do not use a floating `main` branch as evidence after the snapshot is created.

### A0.2 Interface and execution mapping

Produce one comparison matrix covering at least:

| L1 concern | Required upstream comparison |
|---|---|
| Observation synchronization | Rosetta contract timing, topic type, QoS, missing-frame and hold policy |
| PolicyOutput | action shape, units, joint order, chunk semantics, generation time and validity |
| ControlCommand | ros2_control command interface, rate, interpolation, clamp and failure behavior |
| RuntimeMetrics | capture, inference, queue, action and end-to-end timestamps; drop and deadline counters |
| InferenceBackend | runtime ownership, model format, device placement, error and shutdown path |
| ActionBuffer | queue capacity, producer/consumer ownership, backpressure, overwrite and stale policy |
| SafetyState | enable, fault, safe state, reset authority and hardware permission boundary |

Unknown or absent semantics must be recorded as gaps, not filled by assumption.

### A0.3 Candidate review

Review candidates in this order:

1. `ros2_so_arm` and `feetech_ros2_driver` as a possible SO-101 ros2_control hardware boundary.
2. Rosetta as a possible ROS topic to learning-contract and offline replay boundary.
3. SIG demos as a reference for bringup, Gazebo/MuJoCo parity and end-to-end composition.
4. Policy-execution work as a comparison for standalone versus controller-embedded inference.
5. Native buffers and REP-0157 only as a performance watch item unless profiling has already
   shown a material copy or serialization bottleneck.
6. REP-0158 only as an E3 simulation-asset watch item.
7. Agentic interfaces only as an E5 watch item.

### A0.4 Optional isolated compatibility spike

Run a spike only where source review cannot answer a Phase 5 architecture question.

Minimum spike sequence:

1. create an isolated source/build/install/log boundary;
2. pin exact upstream identities;
3. build for the active Jazzy baseline without altering the Phase 4 environment;
4. use mock hardware, offline data or simulation first;
5. exercise startup, normal shutdown and one controlled failure path;
6. preserve commands, configuration, output and cleanup result;
7. stop before real hardware if a separate motion and safety protocol does not exist.

One successful build does not admit a component. It only resolves compatibility questions named in
advance.

### A0.5 Disposition and handoff

Assign each component one of:

- `ADOPT_AND_PIN`
- `ADAPT_BEHIND_BOUNDARY`
- `REFERENCE_ONLY`
- `DEFER`
- `REJECT`

For `DEFER`, state the trigger. For `REJECT`, state the violated constraint. For adoption or
adaptation, state the exact version, owner, adapter boundary, tests, rollback and learning evidence.

## Acceptance criteria

`SIG-A0` passes only when:

- [x] all reviewed source candidates have exact identities;
- [x] Jazzy versus Lyrical and Python/dependency differences are explicit;
- [x] the interface and execution matrix contains no unmarked assumptions;
- [x] every candidate has exactly one disposition;
- [x] adopted or adapted candidate evidence is not applicable because none were admitted;
- [x] Phase 5 package ownership, timing ownership and safety ownership remain unambiguous;
- [x] no upstream component becomes a second source of truth for project interfaces or datasets;
- [x] deferred work has a trigger and cannot silently enter the Core backlog;
- [x] the human owner approved the selected architecture and Phase 5 handoff.

## Stop rules

Stop the affected candidate review and assign `DEFER` or `REJECT` when:

- it requires changing the Core ROS distribution without a separate ADR;
- it requires a frozen interface or safety semantic change;
- dependency resolution would contaminate the active Phase 4 environment;
- a driver or controller cannot be evaluated without unauthorized robot motion;
- upstream identity or license cannot be established;
- the two-day review budget is exhausted;
- or the work begins displacing the current Core milestone.

## Required outputs

At activation, create a dated evidence directory and preserve:

- `upstream_snapshot.json`
- `environment_snapshot.txt`
- `interface_mapping.md`
- `component_dispositions.md`
- build/test logs for any compatibility spike
- `SIG_A0_REVIEW.md` with the human-owned Phase 5 handoff decision

Suggested evidence location:

`experiments/EXP-YYYY-NNN_sig_a0_alignment/`

No output should claim runtime, real-time, task-success or safety qualification unless a separate
frozen protocol provides that authority.

## Follow-up routing

- Accepted driver or ros2_control integration -> Phase 5A implementation plan and tests.
- Accepted Rosetta boundary -> Phase 5A offline replay and contract test plan.
- Policy-execution comparison -> Phase 5B concurrency and timing design review.
- Measured transport bottleneck -> separate native-buffer/REP-0157 feasibility protocol.
- Simulation asset question -> E3 ADR after Technical Core and Employment Gate.
- Agentic question -> E5 ADR after Technical Core and Employment Gate.
- Generalizable evidence or bug -> candidate upstream contribution, requiring human review before
  publication.

## Post-closure field consistency correction

A targeted V2.9 and Addendum review found non-intentional drift in the initial field draft. The
correction is isolated in `experiments/EXP-2026-004_sig_a0_alignment/` and preserves this review's
fixed-source research, component dispositions and ownership conclusions. Phase 5A interface freeze
waits for Owner Review of that correction; no upstream research is reopened.
