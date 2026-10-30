# SIG-A0 Initial Component Dispositions

Status: `OWNER_ACCEPTED_PENDING_PR_5_MERGE`

The human Owner accepted these conservative dispositions on `2026-10-17`. No item is admitted as a
runtime dependency by this architecture review.

| Candidate | Snapshot identity | Disposition | Evidence or trigger |
|---|---|---|---|
| `ros-physical-ai/demos` | `ea931a9fc58de19d9c9bea0fc7dc99da1f30274b` | `REFERENCE_ONLY` | Lyrical/Python 3.14/Zenoh reference environment; never import it as a second architecture |
| `ros2_so_arm` | `e166df9d51f43b24da9b99047c6c51c306bda74f` | `DEFER` | Jazzy CI and mock boundary are source-positive; reconsider only through a separately approved mock-only build |
| `feetech_ros2_driver` | `18aed7fb26d3e2b4c0b47762f39d8698b7032422` | `DEFER` | Initialization can configure hardware and enable torque; requires a later hardware/safety gate |
| `iblnkn/rosetta` | `294136dc435a040d608d9efd773d70ae0b421d00` | `DEFER` | Useful adapter candidate, but unbounded-age hold, zero-fill and direct publish semantics require a project wrapper |
| `ros2_policy_execution_pipeline` | `9e3478a948be4ea327d43e375a51e9b535c02b0c` | `REFERENCE_ONLY` | Package-level Apache-2.0 is resolved; ORT interchange coupling and direct executor ownership conflict with Core boundaries |
| `rosetta_interfaces` | `17d06b639960b8a4de0d1970b4c42d306951d567` | `REFERENCE_ONLY` | Action lifecycle is a useful comparison, but project contracts remain the source of truth |
| `lerobot-rosetta` | `1ea49d620fb344360e4982b9d59031c09efd4564` | `DEFER` | Transitive Python dependency set is not reproducibly pinned and root license scope is absent |
| `lerobot-robot-rosetta` | `cd9b4c140ee5b6b02f3e57f76dfeb1a737646d86` | `DEFER` | Live adapter has one-numeric-key/one-action-key constraints; dependency and license closure remain open |
| REP-0157/native buffers | dated official REP page | `DEFER` | Trigger only after a measured copy or serialization bottleneck exists |
| REP-0158/OpenUSD conventions | official page observed as `DRAFT` | `DEFER` | Route to the later E3 simulation-asset review |

No component is `ADOPT_AND_PIN` or `ADAPT_BEHIND_BOUNDARY`. The optional `ros2_so_arm` compatibility
spike is not required now; its trigger is a separately authorized ros2_control/mock-hardware
integration decision.

Detailed fixed-source evidence and the accepted Owner decision are in `SOURCE_REVIEW_20261017.md`.
