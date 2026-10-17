# SIG-A0 Review Record

Review status: `ACTIVE_NOT_YET_PASSED`

Activation date: `2026-10-17`

Owner: human

Evidence root: `experiments/EXP-2026-004_sig_a0_alignment/`

## Activation decision

The human owner approved the minimal activation package after Phase 4 closure and Gate A2d-1
merge. `SIG-A0` may now perform bounded official-source and architecture review.

This decision does not authorize dependency installation, source cloning, a compatibility build,
simulation, driver execution, hardware access, firmware changes or robot motion.

## Entry check

| Condition | Result | Evidence |
|---|---|---|
| Phase 4 permits Phase 5 entry | PASS | Phase 4 closure records `Next phase entry: ALLOWED` |
| Governing document hashes match | PASS | `environment_snapshot.txt` |
| Repository and worktree baseline captured | PASS | `environment_snapshot.txt` |
| Host toolchain baseline captured | PASS | `environment_snapshot.txt` |
| Draft Phase 5A package boundaries available | PASS FOR REVIEW | `phase5a_package_boundaries.md` |
| Five protected interfaces available for comparison | PASS FOR REVIEW | `interface_mapping.md` |
| Official upstream sources refreshed | PASS FOR ACTIVATION | `upstream_snapshot.json` |
| Exact identities captured before build/use | PASS | five repository HEAD identities captured; no build/use occurred |
| Compatibility-spike output and cleanup plan | NOT APPLICABLE | no spike is authorized |

## Current limits and risks

- Fixed manifests and direct demo source pins are reviewed, but full transitive dependency closure
  is incomplete. The LeRobot adapters install unpinned current Python packages in CI.
- `RMW_IMPLEMENTATION` is not explicitly selected.
- LeRobot is not installed in the active Python environment.
- The policy-execution repository has no root `LICENSE`, but both ROS package directories contain
  Apache-2.0 license files and their manifests declare Apache-2.0. The two LeRobot Rosetta adapter
  repositories declare Apache-2.0 in package metadata and source headers but have no root LICENSE.
- Field-level definitions for the five frozen contracts still require human review.
- Upstream `HEAD` values are dated evidence only and must never be treated as floating pins.

## Fixed-source review checkpoint

Read-only source review is complete for the five recorded candidates and the direct Rosetta
identities pinned by the captured demo manifest. Evidence and exact source links are recorded in
`SOURCE_REVIEW_20261017.md`.

Source review supports these conclusions:

- the full demo remains `REFERENCE_ONLY` because its executable environment is Lyrical,
  Python 3.14 and Zenoh rather than the L1 Jazzy baseline;
- `ros2_so_arm` remains the only current candidate worth a later isolated Jazzy mock-only build;
- the Feetech driver remains deferred because initialization can configure hardware and enable
  torque, and it does not own the project safety boundary;
- Rosetta remains deferred to a project-owned offline adapter because upstream `hold`, zero-fill,
  direct publishing and queue semantics do not define L1 freshness or fail-closed behavior;
- the policy-execution prototype is recommended as `REFERENCE_ONLY`, not a Core dependency,
  because every stage is coupled to the ONNX Runtime value type and its executor does not implement
  L1 action-age or safety ownership; and
- no upstream adoption is needed to start the offline replay/FakePolicy Phase 5A Core path after
  SIG-A0 receives its human architecture decision.

No compatibility spike was executed or implicitly authorized by this checkpoint.

## Pass decision

`PENDING_OWNER_ARCHITECTURE_REVIEW`

The review can pass only after the human Owner accepts the project field schemas, timing/buffer and
safety ownership, selects an explicit Phase 5A RMW, and accepts the component dispositions. A
mock-only compatibility spike is optional: source findings do not make upstream adoption a
prerequisite for the offline Phase 5A Core path. Until the Owner decision, Phase 5A architecture
must not be frozen.
