# SIG-A0 Interface Review Baseline

Status: `OWNER_ACCEPTED_PENDING_PR_5_MERGE`

The five contract names and their project ownership are frozen. Fixed upstream sources have been
compared, and the human Owner accepted the Phase 5A field and ownership baseline on `2026-10-17`.
This is an architecture contract only; it does not authorize implementation, build or hardware use.

| Contract | Fixed-source finding | Required L1 mapping | Open item before freeze |
|---|---|---|---|
| `Observation` | Rosetta declares topic/type/QoS, header/receive timeline and `hold`/`asof`/`drop`; `hold` has no age limit and missing streams are zero-filled | Project adapter adds schema version, units, frame/joint identity, clock domain and validity; safety-relevant missing data fails closed | Accepted below |
| `PolicyOutput` | Rosetta/LeRobot exposes chunk size, queue threshold and aggregation, but live use collapses to one numeric observation key and one action key; action values become `float32` | Project type carries units, joint order, chunk semantics, `generated_at_ns` and `valid_until_ns`; never direct actuator authority | Accepted below |
| `ControlCommand` | SO-ARM uses position interfaces at 50 Hz; forward controller orders five arm joints while the hardware description also contains a gripper; Feetech write has no L1 clamp/freshness check | `physical_ai_runtime` owns ordering, conversion, clamp, deadline and fail-closed command preparation | Accepted below |
| `SafetyState` | Rosetta watchdog fires after two frame periods but allows `hold`, `zeros` or `none`; Feetech deactivation disables torque, while initialization may enable it | `physical_ai_safety_bridge` maps project state to MCU permission; Linux cannot reset or bypass STM32/Zephyr and hardware E-stop authority | Accepted below |
| `RuntimeMetrics` | Rosetta reports queue depth and published actions; reviewed candidates do not provide complete L1 end-to-end timing | `physical_ai_runtime` owns one clock policy plus capture, inference, queue, action age, jitter, drop and deadline counters | Accepted below |
| `InferenceBackend` | Rosetta has a separable framework adapter; the policy-execution prototype couples all stages to `Ort::Value` | `physical_ai_policy_adapter` preserves a backend-neutral boundary; OpenVINO remains the admitted Intel path | Accepted ownership; detailed API remains a Phase 5A design item |
| bounded `ActionBuffer` | LeRobot owns an internal action queue and reports depth; reviewed wrapper does not prove project capacity, overflow or stale-action rejection | `physical_ai_runtime` owns capacity, producer/consumer handoff, overwrite, expiry and stale-action rejection | Accepted below |

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
inherited by L1. The Owner selected `rmw_fastrtps_cpp` for Phase 5A. It must be set explicitly by
the future launch/test environment; this decision does not mutate the host globally or prevent a
later evidence-backed RMW decision.

## Owner-approved Phase 5A field baseline

All `*_ns` values use unsigned nanoseconds in the named `clock_domain`. Phase 5A uses one
host-local monotonic clock domain for capture, policy, buffer, command and metrics comparisons.
Values from different clock domains are rejected rather than compared. Array lengths must match,
joint names are ordered identifiers, position values are radians, and every numeric value must be
finite.

### `Observation` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `string clock_domain`
- `uint64 captured_at_ns`
- `uint64 received_at_ns`
- `uint64 valid_until_ns`
- `string frame_id`
- `string[] joint_names`
- `float64[] joint_positions_rad`
- `bool valid`

The consumer requires `captured_at_ns <= received_at_ns <= valid_until_ns`, a known frame and joint
order, matching array lengths and finite positions. Missing or invalid safety-relevant input fails
closed; it is not converted to valid zero data.

### `PolicyOutput` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `uint64 source_observation_sequence_id`
- `string clock_domain`
- `uint64 generated_at_ns`
- `uint64 valid_until_ns`
- `string[] joint_names`
- `float64[] target_positions_rad`
- `uint32 chunk_index`
- `uint32 chunk_size`
- `bool valid`

Phase 5A fixes `chunk_index = 0` and `chunk_size = 1`. A `PolicyOutput` carries no actuator or
safety permission.

### `ControlCommand` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `uint64 source_policy_sequence_id`
- `string clock_domain`
- `uint64 generated_at_ns`
- `uint64 valid_until_ns`
- `string[] joint_names`
- `float64[] target_positions_rad`
- `bool clamp_applied`
- `bool valid`

`physical_ai_runtime` validates order, converts units, applies limits and rejects expired commands
before mock execution. This message does not grant Linux or hardware execution permission.

### `SafetyState` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `string clock_domain`
- `uint64 updated_at_ns`
- `uint8 state`: `0 DISABLED`, `1 READY`, `2 PERMITTED`, `3 FAULT`, `4 ESTOP`
- `bool permission_granted`
- `bool fault_latched`
- `uint32 fault_code`
- `string reason`
- `uint64 mcu_ack_sequence`

Linux may request a transition but cannot grant permission, clear a latched MCU fault or override
the hardware E-stop. `permission_granted` is usable only with a current MCU acknowledgement and
`state = PERMITTED`; Phase 5A exercises this rule only against mock execution.

### `RuntimeMetrics` version 1

- `uint16 schema_version` = `1`
- `string run_id`
- `uint64 sequence_id`
- `string clock_domain`
- `uint64 sampled_at_ns`
- `uint64 observation_sequence_id`, `policy_sequence_id`, `command_sequence_id`
- `uint64 observation_age_ns`, `inference_latency_ns`, `queue_delay_ns`, `action_age_ns`
- `uint64 end_to_end_latency_ns`
- `int64 execution_jitter_ns`
- `uint32 queue_depth`, `queue_capacity`
- `uint64 dropped_total`, `overwritten_total`, `expired_total`, `deadline_miss_total`

Counters are monotonic within one `run_id`. Reset/restart boundaries require a new `run_id` rather
than silently joining two process lifetimes.

## Owner-approved bounded `ActionBuffer` semantics

- Phase 5A capacity is exactly one pending `PolicyOutput`.
- Capacity is fixed at startup; the buffer never grows dynamically and never blocks indefinitely.
- Schema version, clock domain, validity interval, joint order, array lengths and finite values are
  validated before insertion.
- A new valid item atomically replaces an unconsumed item and increments `overwritten_total`.
- Consumption rechecks time validity. An expired item is cleared, increments `expired_total` and
  cannot become a `ControlCommand`.
- Later multi-action/chunk buffering requires a separate reviewed extension; upstream queues do not
  silently change this contract.

See `SOURCE_REVIEW_20261017.md` for fixed source links and detailed evidence.
