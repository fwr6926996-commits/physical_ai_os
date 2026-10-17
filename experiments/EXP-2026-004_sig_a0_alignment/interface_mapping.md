# SIG-A0 Interface Review Baseline

Status: `SOURCE_REVIEWED_PROJECT_SCHEMA_PENDING_OWNER`

The five contract names and their project ownership are frozen. Fixed upstream sources have now
been compared, but field-level project definitions are not invented here. Unknown semantics remain
explicit Owner-review gaps.

| Contract | Fixed-source finding | Required L1 mapping | Open item before freeze |
|---|---|---|---|
| `Observation` | Rosetta declares topic/type/QoS, header/receive timeline and `hold`/`asof`/`drop`; `hold` has no age limit and missing streams are zero-filled | Project adapter adds schema version, units, frame/joint identity, clock domain and validity; safety-relevant missing data fails closed | Owner accepts exact fields and freshness rule |
| `PolicyOutput` | Rosetta/LeRobot exposes chunk size, queue threshold and aggregation, but live use collapses to one numeric observation key and one action key; action values become `float32` | Project type carries shape, units, joint order, chunk index, `generated_at` and `valid_until`; never direct actuator authority | Owner accepts fields and chunk semantics |
| `ControlCommand` | SO-ARM uses position interfaces at 50 Hz; forward controller orders five arm joints while the hardware description also contains a gripper; Feetech write has no L1 clamp/freshness check | `physical_ai_runtime` owns ordering, conversion, clamp, deadline and fail-closed command preparation | Owner accepts representation and deadline |
| `SafetyState` | Rosetta watchdog fires after two frame periods but allows `hold`, `zeros` or `none`; Feetech deactivation disables torque, while initialization may enable it | `physical_ai_safety_bridge` maps project state to MCU permission; Linux cannot reset or bypass STM32/Zephyr and hardware E-stop authority | Owner accepts state machine, reset authority and acknowledgement |
| `RuntimeMetrics` | Rosetta reports queue depth and published actions; reviewed candidates do not provide complete L1 end-to-end timing | `physical_ai_runtime` owns one clock policy plus capture, inference, queue, action age, jitter, drop and deadline counters | Owner selects clock and exact metric fields |
| `InferenceBackend` | Rosetta has a separable framework adapter; the policy-execution prototype couples all stages to `Ort::Value` | `physical_ai_policy_adapter` preserves a backend-neutral boundary; OpenVINO remains the admitted Intel path | Owner accepts error/shutdown contract and device ownership |
| bounded `ActionBuffer` | LeRobot owns an internal action queue and reports depth; reviewed wrapper does not prove project capacity, overflow or stale-action rejection | `physical_ai_runtime` owns capacity, producer/consumer handoff, overwrite/backpressure, expiry and stale-action rejection | Owner accepts capacity and expiry policy |

Additional protected abstractions:

- independent `SafetyFilter -> STM32/Zephyr` permission and emergency-stop boundary.

An upstream type name, successful demo or build result cannot close an open item by itself.

## Source-review ownership recommendation

- `physical_ai_interfaces`: field definitions and schema versions only.
- `physical_ai_replay`: recorded input and deterministic offline replay.
- `physical_ai_policy_adapter`: `FakePolicy` and replaceable `InferenceBackend` mapping.
- `physical_ai_runtime`: clock selection, action age, bounded `ActionBuffer`, command preparation and
  `RuntimeMetrics`.
- `physical_ai_safety_bridge`: the only Linux boundary to STM32/Zephyr permission state.

The upstream demo's `rmw_zenoh_cpp` choice belongs to its Lyrical reference environment and is not
inherited by L1. Phase 5A must select one explicit Jazzy RMW before reproducible tests are frozen.
See `SOURCE_REVIEW_20261017.md` for fixed source links and detailed evidence.
