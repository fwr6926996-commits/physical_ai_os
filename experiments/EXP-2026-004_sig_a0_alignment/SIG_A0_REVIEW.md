# SIG-A0 Review Record

Review status: `PASS_ARCHITECTURE_REVIEW_ONLY`

Activation date: `2026-10-17`

Owner: human

Evidence root: `experiments/EXP-2026-004_sig_a0_alignment/`

Repository effectivity: PR #5 merged as `bb5f8712a1e30b7df23608f8bd1794fc7043ad98`

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
| Phase 5A package boundaries accepted | PASS | `phase5a_package_boundaries.md` |
| Five protected interface names and ownership available | PASS | `interface_mapping.md` |
| Official upstream sources refreshed and reviewed | PASS | `upstream_snapshot.json`, `SOURCE_REVIEW_20261017.md` |
| Exact identities captured before build/use | PASS | five repository HEAD identities captured; no build/use occurred |
| Compatibility-spike output and cleanup plan | NOT APPLICABLE | no spike is authorized |

## Current limits and risks

- Fixed manifests and direct demo source pins are reviewed, but full transitive dependency closure
  is incomplete. The LeRobot adapters install unpinned current Python packages in CI.
- `rmw_fastrtps_cpp` is selected but has not been exercised by this source-only review.
- LeRobot is not installed in the active Python environment.
- The policy-execution repository has no root `LICENSE`, but both ROS package directories contain
  Apache-2.0 license files and their manifests declare Apache-2.0. The two LeRobot Rosetta adapter
  repositories declare Apache-2.0 in package metadata and source headers but have no root LICENSE.
- A post-closure consistency review found non-intentional field drift against V2.9 and Gate T0.
  The upstream research PASS remains valid, but the Phase 5A field freeze waits for the correction
  in `PHASE5A_INTERFACE_CONSISTENCY_REVIEW_20261017.md`.
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

## Owner architecture decision

On `2026-10-17`, the human Owner approved the following for the Phase 5A handoff:

- the initial version 1 project field and validity baseline in `interface_mapping.md`, later
  reopened only for the V2.9 and Gate T0 consistency correction;
- `physical_ai_runtime` ownership of the host-local monotonic clock policy, action age and the
  capacity-one bounded `ActionBuffer`;
- `physical_ai_safety_bridge` as the sole Linux-to-MCU permission boundary;
- explicit `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` for future Phase 5A launch/test evidence; and
- no compatibility spike now; `ros2_so_arm` remains `DEFER` until a separately authorized
  ros2_control/mock-hardware integration decision.

This decision does not authorize dependency installation, implementation, build, simulation,
hardware access, firmware change or robot motion.

## Pass decision

`PASS — ARCHITECTURE REVIEW ONLY`

All protocol acceptance criteria for fixed-source research, component dispositions and ownership
were satisfied, and PR #5 made that result repository-effective. A mock-only compatibility spike
is not required for the offline Phase 5A Core path and remains unauthorized. The later field-level
consistency correction does not reopen upstream research, but it must be reviewed before the Phase
5A interface freeze. Phase 5A implementation still requires a separate start decision.

## Post-closure interface consistency review

Review against the frozen V2.9 execution book and both binding addenda found that the initial
field draft used a non-baseline five-state safety vocabulary, omitted required logical fields and
did not attach all Gate T0 metadata to every time field. The correction is documented in
`PHASE5A_INTERFACE_CONSISTENCY_REVIEW_20261017.md` and changes neither upstream identities nor
component dispositions. No new ADR is required unless Owner Review chooses to preserve a deviation
from the frozen baseline.
