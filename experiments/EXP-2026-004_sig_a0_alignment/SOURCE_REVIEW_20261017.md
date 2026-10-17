# SIG-A0 Fixed-Source Review — 2026-10-17

Status: `SOURCE_REVIEW_COMPLETE_OWNER_DECISION_PENDING`

Scope: read-only inspection of the exact commits recorded in `upstream_snapshot.json` and the
direct Rosetta identities pinned by the captured demo manifest. No clone, installation, build,
simulation, hardware access or robot motion occurred.

## Compatibility facts

| Candidate | Fixed evidence | Finding |
|---|---|---|
| ROS Physical AI demos | [`pixi.toml`](https://github.com/ros-physical-ai/demos/blob/ea931a9fc58de19d9c9bea0fc7dc99da1f30274b/pixi.toml), [`Dockerfile`](https://github.com/ros-physical-ai/demos/blob/ea931a9fc58de19d9c9bea0fc7dc99da1f30274b/docker/Dockerfile), [`pai.repos`](https://github.com/ros-physical-ai/demos/blob/ea931a9fc58de19d9c9bea0fc7dc99da1f30274b/pai.repos) | The runnable environment is ROS 2 Lyrical, Python 3.14 and `rmw_zenoh_cpp`. It is not the L1 Jazzy environment. The manifest pins a different `ros2_so_arm` and Rosetta commit than the standalone SIG-A0 candidates. |
| `ros2_so_arm` | [`build_and_test.yaml`](https://github.com/ros-physical-ai/ros2_so_arm/blob/e166df9d51f43b24da9b99047c6c51c306bda74f/.github/workflows/build_and_test.yaml), [`so_arm101.ros2_control.xacro`](https://github.com/ros-physical-ai/ros2_so_arm/blob/e166df9d51f43b24da9b99047c6c51c306bda74f/so_arm101_description/control/so_arm101.ros2_control.xacro) | CI declares Jazzy, Kilted and Rolling. The description exposes an explicit `mock_components` boundary and a separate real Feetech plugin path. This is source-level compatibility evidence, not a local build result. |
| `feetech_ros2_driver` | [`build_and_test.yaml`](https://github.com/ros-physical-ai/feetech_ros2_driver/blob/18aed7fb26d3e2b4c0b47762f39d8698b7032422/.github/workflows/build_and_test.yaml), [`feetech_ros2_driver.cpp`](https://github.com/ros-physical-ai/feetech_ros2_driver/blob/18aed7fb26d3e2b4c0b47762f39d8698b7032422/src/feetech_ros2_driver.cpp) | CI declares Jazzy. Initialization opens the serial transport, writes configuration and enables torque for commanded joints; deactivation disables torque. `on_activate()` ignores the return value of its initial read, and `write()` does not provide the project clamp, freshness or MCU-permission semantics. |
| Rosetta | [`ci.yml`](https://github.com/iblnkn/rosetta/blob/294136dc435a040d608d9efd773d70ae0b421d00/.github/workflows/ci.yml), [`package.xml`](https://github.com/iblnkn/rosetta/blob/294136dc435a040d608d9efd773d70ae0b421d00/package.xml) | CI declares ROS 2 Jazzy. The core ROS package does not require LeRobot, but it requires the separately versioned `rosetta_interfaces` package. LeRobot execution additionally requires two adapters and Python/PyTorch dependencies not installed in the active environment. |
| Policy-execution prototype | [`package.xml`](https://github.com/saikishor/ros2_policy_execution_pipeline/blob/9e3478a948be4ea327d43e375a51e9b535c02b0c/ros2_policy_execution_core/package.xml), [`policy_execution_pipeline.cpp`](https://github.com/saikishor/ros2_policy_execution_pipeline/blob/9e3478a948be4ea327d43e375a51e9b535c02b0c/ros2_policy_execution_pipeline/src/policy_execution_pipeline.cpp) | No CI workflow was present at the fixed commit. All stages depend on `onnxruntime_vendor` and exchange `Ort::Value`; the timer is a wall timer, and per-cycle failures are logged and skipped. This does not implement L1 action freshness or independent safety ownership. |

The exact fixed demo manifest also records these direct identities:

- `rosetta_interfaces` `17d06b639960b8a4de0d1970b4c42d306951d567`
- `lerobot-rosetta` `1ea49d620fb344360e4982b9d59031c09efd4564`
- `lerobot-robot-rosetta` `cd9b4c140ee5b6b02f3e57f76dfeb1a737646d86`

They close identity discovery for the captured demo manifest, but not full transitive dependency
closure. The adapter CI installs unpinned current `lerobot[dataset]`, `torch`, `protobuf` and
`grpcio`, so a reproducible L1 dependency set is still absent.

## Interface and ownership findings

### Observation

Rosetta declares topic type, QoS, contract FPS, header/receive timeline and `hold`, `asof` or
`drop` resampling. Its buffer is constant-memory, but `hold` has no age limit. Missing streams are
zero-filled, and the live LeRobot adapter continues after a five-second warm-up timeout. These are
useful mapping mechanisms but cannot define L1 freshness or fail-closed behavior.

Decision constraint: Rosetta may supply an offline/topic adapter only. The project-owned
`Observation` schema must carry explicit units, joint order, frame identity, clock domain and
freshness validity; safety-relevant missing input must not silently become valid zero data.

### PolicyOutput and ActionBuffer

The Rosetta/LeRobot path exposes configurable `actions_per_chunk`, queue threshold and aggregation,
and reports queue depth. The live adapter supports only one numeric observation key and one action
key, converts actions to `float32`, and publishes through the topic bridge. The reviewed wrapper
does not establish project-owned queue capacity, overflow behavior, `generated_at`, `valid_until`
or action-age rejection.

Decision constraint: the bounded L1 `ActionBuffer` remains in `physical_ai_runtime`; upstream
queues are implementation details behind the adapter and cannot replace its capacity, overwrite,
expiry and stale-action rules.

### ControlCommand and SafetyState

The reviewed SO-ARM controller config uses position interfaces at 50 Hz. Its forward position
controller lists five arm joints while the hardware description also has a gripper joint. Rosetta
pre-validates finite values and has a two-frame-period watchdog, but contract safety may be
`hold`, `zeros` or `none`; `hold` explicitly republishes the last action. The Feetech driver can
enable torque during initialization and has no project MCU-permission handshake.

Decision constraint: upstream code may not construct the final executable `ControlCommand` or own
`SafetyState`. Project conversion, joint ordering, clamp, deadline and fail-closed checks precede
the `physical_ai_safety_bridge`; the STM32/Zephyr permission and hardware E-stop remain final.

### RuntimeMetrics and InferenceBackend

Rosetta exposes queue depth and published-action count but not the complete capture, inference,
queue, action-age, jitter, drop and deadline metrics required by L1. Its framework adapter boundary
is useful. The policy-execution prototype is less suitable as a backend boundary because
`Ort::Value` is the compile-time interchange type for every stage.

Decision constraint: `physical_ai_runtime` owns clock selection, action-age computation and
`RuntimeMetrics`; `physical_ai_policy_adapter` owns the replaceable `InferenceBackend` boundary.

## License review

| Scope | Result |
|---|---|
| demos | Root Apache-2.0 license present |
| `ros2_so_arm` | Root BSD-3-Clause; mesh directories carry Apache-2.0 license files |
| `feetech_ros2_driver` | Root BSD-3-Clause license present |
| Rosetta and `rosetta_interfaces` | Root Apache-2.0 licenses present |
| policy-execution prototype | No root license, but both ROS package directories contain Apache-2.0 LICENSE files and package manifests declare Apache-2.0 |
| LeRobot Rosetta adapters | Package manifests and source headers declare Apache-2.0, but no root LICENSE file was present at the fixed commits |

The original policy-execution finding is therefore narrowed from “license unresolved” to
“package-scoped Apache-2.0; repository-root scope absent.” The two LeRobot adapters retain a
license-hygiene gap before adoption or redistribution.

## Recommended dispositions for Owner review

| Candidate | Recommendation | Reason |
|---|---|---|
| demos | `REFERENCE_ONLY` | Lyrical/Python 3.14/Zenoh environment differs from Core |
| `ros2_so_arm` | keep `DEFER` | Best candidate for a later isolated Jazzy mock-only build |
| `feetech_ros2_driver` | keep `DEFER` | Hardware initialization and safety ownership require a separate hardware gate |
| Rosetta | keep `DEFER` | Candidate for offline adapter spike only after L1 schemas and RMW are selected |
| policy-execution prototype | change to `REFERENCE_ONLY` | Useful stage comparison; ORT datatype coupling and execution semantics conflict with Core ownership |
| `rosetta_interfaces` | `REFERENCE_ONLY` | Useful action lifecycle reference; not the L1 contract source of truth |
| LeRobot Rosetta adapters | `DEFER` | Dependency pins and root license scope remain incomplete |
| REP-0157/native buffers | keep `DEFER` | No measured transport bottleneck |
| REP-0158/OpenUSD | keep `DEFER` | Belongs to E3 |

## Remaining Gate decisions

SIG-A0 remains `ACTIVE_NOT_YET_PASSED`. Before PASS, the human Owner must approve:

1. the project field-level definitions for `Observation`, `PolicyOutput`, `ControlCommand`,
   `SafetyState` and `RuntimeMetrics`;
2. `physical_ai_runtime` as owner of clock selection, action age and the bounded buffer;
3. `physical_ai_safety_bridge` as the only Linux-to-MCU permission boundary;
4. one explicit RMW for reproducible Phase 5A tests; and
5. whether the only compatibility spike worth authorizing now is a Jazzy, mock-only,
   no-LeRobot `ros2_so_arm` build.

No source finding requires the full SIG demo, Rosetta, the Feetech driver or the policy-execution
prototype to enter Phase 5A. Therefore unresolved upstream adoption does not need to block the
offline `ReplayObservation -> FakePolicy -> bounded ActionBuffer -> mock execution` Core path.
