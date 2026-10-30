# SIG-A0 Interface Review Baseline

Status: `CORRECTION_PROPOSED_PENDING_OWNER_REVIEW`

The SIG-A0 fixed-source research, component dispositions and ownership decisions remain valid.
This correction restores the field baseline to the frozen L1 V2.9 execution book and its two
binding addenda. It does not modify the frozen governing documents, admit an upstream component or
authorize implementation, build, dependency installation or hardware use.

## Governing baseline

| Document | SHA-256 |
|---|---|
| L1 V2.9 execution book | `95cd404a72f0c03435b0728aa0bd169f78a6b782f9063a4b6659cbc953bec5ef` |
| Architecture Audit Addendum 01 | `eb34eedec544d8f327a321b9e4188055ffcd54aee4a44b7672cb5955e95e8091` |
| Portability Addendum 02 | `e3b4aea1b8cdcf425762fa980d4bc6189e109f726d9238bea6f1c146dc7551b6` |

## Corrected consistency result

| Contract | Frozen-baseline requirement | Correction |
|---|---|---|
| `Observation` | Capture, state and assembly time; RGB input; ordered joint and gripper state; task context; frame, units, validity and data version | Restore the omitted state/assembly, sensor, task, gripper, health and data-version semantics |
| `PolicyOutput` | `generated_at`, `valid_until`, `sequence_id`, `model_version`, action chunk/trajectory with `dt`, status and optional confidence | Restore the omitted model, step, status and confidence semantics |
| `ControlCommand` | Generic command after `SafetyFilter` processing | Make it a post-filter command; the pre-filter value is an internal `CommandCandidate` |
| `SafetyState` | `DISARMED / ARMED / RUNNING / DEGRADED / FAULT / SAFE` shared by ROS 2 and MCU | Replace the non-baseline `DISABLED / READY / PERMITTED / FAULT / ESTOP` enum |
| `RuntimeMetrics` | Full nine-point time chain, derived Age/latency/jitter, queue counters, percentiles and fault/resource/reproduction evidence | Restore the raw time points and define event versus run-summary evidence |
| Gate T0 | Every time field records timestamp, clock domain, source, measurement point and synchronization status; benchmark output carries the clock contract version | Replace message-wide clock metadata with metadata attached to every time field |

These are non-intentional consistency corrections. No change to the formal architecture or new ADR
is proposed.

## Protected ownership and upstream findings

- `physical_ai_interfaces` owns project schemas and versions only.
- `physical_ai_replay` owns deterministic offline replay and fixtures.
- `physical_ai_policy_adapter` owns `FakePolicy` and the replaceable `InferenceBackend` mapping.
- `physical_ai_runtime` owns the host-local monotonic clock policy, action age, capacity-one
  `ActionBuffer`, pre-filter command preparation and `RuntimeMetrics`.
- `physical_ai_safety_bridge` supplies the project `SafetyState` and MCU acknowledgement to
  `SafetyFilter`. It cannot replace STM32/Zephyr or the hardware E-stop.
- Upstream queues, drivers, controllers and message types remain behind adapters and cannot become
  a second source of truth.

The SIG-A0 component dispositions, exact upstream identities and source-review conclusions are
unchanged. `rmw_fastrtps_cpp` remains the explicit Phase 5A test RMW and must be selected per launch
or test, never as a global host mutation.

## Gate T0 timestamp contract version 1

Every logical time field is a `ClockedTimestamp` record with:

- `uint64 timestamp_ns`
- `string clock_domain`
- `string source`
- `string measurement_point`
- `string synchronization_status`
- `uint16 clock_contract_version` = `1`
- `bool present`

Phase 5A interval, age, jitter, deadline and timeout calculations use one host-local monotonic or
steady clock domain. ROS time or system time may be recorded for human-readable or rosbag
correlation, but it is never subtracted from a monotonic value. Values from different clock domains
are rejected unless an explicit mapping records offset, method, error and sampling window.
`unknown` synchronization status is preserved rather than guessed.

## Corrected Phase 5A logical field baseline

This is a logical contract for the message-definition Review. Standard ROS message composition may
be selected later, but it must preserve every semantic below.

### `Observation` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `string data_version`
- `ClockedTimestamp capture_time`
- `ClockedTimestamp state_time`
- `ClockedTimestamp assembled_time`
- `ClockedTimestamp valid_until_time`
- `image_front_rgb` with explicit encoding, shape and frame identity
- `string frame_id`
- `string[] joint_names`
- `float64[] joint_positions_rad`
- `string gripper_state_name`
- `float64 gripper_state_value`
- `string gripper_state_unit`
- `uint32 hardware_health_flags`
- `string task_id`
- `string task_phase`
- optional `string language_text`
- `bool valid`

Joint order is the array order and cannot be inferred from a device ID. Array lengths must match
and numeric values must be finite. The gripper unit and mapping are explicit. Missing or invalid
safety-relevant input fails closed and is never converted into valid zero data.

### `PolicyOutput` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `uint64 source_observation_sequence_id`
- `ClockedTimestamp generated_time`
- `ClockedTimestamp valid_until_time`
- `string model_version`
- `string[] joint_names`
- `float64[] target_positions_rad`
- `uint64 action_dt_ns`
- `uint32 chunk_index`
- `uint32 chunk_size`
- `string status`
- optional `float64 confidence` with an explicit presence flag
- `bool valid`

Phase 5A fixes `chunk_index = 0` and `chunk_size = 1`. A `PolicyOutput` carries neither actuator
authority nor safety permission.

### `SafetyState` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `ClockedTimestamp updated_time`
- `uint8 state` with project constants in frozen order:
  `0 DISARMED`, `1 ARMED`, `2 RUNNING`, `3 DEGRADED`, `4 FAULT`, `5 SAFE`
- `bool permission_granted`
- `bool fault_latched`
- `uint64 fault_flags`
- `uint32 fault_code`
- `string reason`
- `uint64 mcu_ack_sequence`

`permission_granted` is false in `DISARMED`, `ARMED`, `FAULT` and `SAFE`. It may be true in
`RUNNING` only with a current MCU acknowledgement. V2.9 permits restricted execution in
`DEGRADED`, but Phase 5A defines no restricted hardware profile, so mock execution treats it as no
permission. A reset never transitions directly from `FAULT` or `SAFE` to `RUNNING`; recovery returns
through `DISARMED` and requires the project state machine and human-owned conditions.

### `ControlCommand` version 1

- `uint16 schema_version` = `1`
- `uint64 sequence_id`
- `uint64 source_policy_sequence_id`
- `uint64 safety_state_sequence_id`
- `uint64 mcu_ack_sequence`
- `ClockedTimestamp generated_time`
- `ClockedTimestamp valid_until_time`
- `string[] joint_names`
- `float64[] target_positions_rad`
- `bool clamp_applied`
- `bool valid`

`ControlCommand` exists only after `SafetyFilter` accepts an internal `CommandCandidate` against a
current `SafetyState`. It is therefore not the name of the pre-filter candidate. A false or stale
permission result produces no executable command. Phase 5A sends accepted commands only to the mock
executor.

### `RuntimeMetrics` version 1

The event record contains:

- `uint16 schema_version` = `1`
- `string run_id`
- `uint64 sequence_id`
- `ClockedTimestamp sampled_time`
- `uint64 observation_sequence_id`, `policy_sequence_id`, `command_sequence_id`
- `ClockedTimestamp t_capture`, `t_state`, `t_observation_ready`
- `ClockedTimestamp t_infer_start`, `t_infer_end`, `t_action_generated`
- `ClockedTimestamp t_enqueue`, `t_dequeue`, `t_execute`
- `uint64 observation_age_ns`, `inference_latency_ns`, `queue_delay_ns`
- `uint64 action_age_ns`, `end_to_end_age_ns`
- `int64 execution_jitter_ns`
- `uint32 queue_depth`, `queue_capacity`
- `uint64 dropped_total`, `overwritten_total`, `expired_total`,
  `deadline_miss_total` and `stale_drop_total`
- `uint32 active_fault_code`

Derived values are emitted only when their source timestamps have compatible clock contracts.
Counters are monotonic within one `run_id`; restart creates a new `run_id`.

The run-summary JSON or CSV, rather than every event message, reports P50/P95/P99 and maximum,
task result and failure class, resource and thermal observations when applicable, fault
detection/stop/recovery evidence, and Git/data/model/config/runtime identities. It carries
`clock_contract_version = 1`.

## SafetyFilter processing order

The only permitted Phase 5A path is:

`ReplayObservation -> FakePolicy -> capacity-one ActionBuffer -> Execution consumer
-> internal CommandCandidate -> SafetyFilter(CommandCandidate, SafetyState)
-> ControlCommand -> mock execution -> RuntimeMetrics`

The execution consumer validates schema, timestamp contract, order, units, finite values, freshness
and limits while preparing the internal candidate. `SafetyFilter` then checks current permission,
fault latch and acknowledgement. No candidate-to-executor bypass exists. Later Adapter, driver or
hardware work requires a separate gate and cannot reorder this boundary.

## Bounded `ActionBuffer` semantics

- Capacity is exactly one pending `PolicyOutput` and is fixed at startup.
- The buffer never grows dynamically and never blocks indefinitely.
- Schema, timestamp contract, validity, order, lengths and finite values are checked before insert.
- A newer valid item atomically replaces an unconsumed item and increments `overwritten_total`.
- Consumption rechecks validity and freshness. Expired or stale items are cleared and counted and
  cannot become a `CommandCandidate`.
- Multi-action buffering requires a separately reviewed extension.

See `PHASE5A_INTERFACE_CONSISTENCY_REVIEW_20261017.md` for the audit trail and
`PHASE5A_MINIMAL_OFFLINE_IMPLEMENTATION_PLAN.md` for the bounded implementation proposal.
