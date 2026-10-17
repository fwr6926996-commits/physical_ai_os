# SIG-A0 Interface Review Baseline

Status: `OPEN_MAPPING`

The five contract names and their project ownership are frozen. Field-level definitions are not
invented here. Unknown semantics remain explicit review gaps.

| Contract | Project role | Upstream comparison | Open items before freeze | Protected boundary |
|---|---|---|---|---|
| `Observation` | Input presented to policy processing | Rosetta topic/type/QoS, timestamp source, alignment, hold and missing-frame behavior | Field schema, units, frame IDs, joint order, capture/receive clock | Upstream mapping must use an adapter |
| `PolicyOutput` | Policy result before execution filtering | Rosetta action contract and policy-execution chunk behavior | Shape, units, joint order, chunk semantics, generation/validity metadata | No direct actuator authority |
| `ControlCommand` | Command after project-owned conversion and checks | ros2_control interfaces, rate, interpolation, clamp and failure behavior | Command representation, deadline and fail-closed behavior | Only project runtime may produce it for execution |
| `SafetyState` | Enable, fault, safe-state and reset authority | Driver/controller lifecycle and error propagation | State model, reset authority and MCU acknowledgement | Linux cannot bypass MCU permission or hardware E-stop |
| `RuntimeMetrics` | Evidence for timing, drops and deadlines | Upstream timestamps, tracing and counters | Clock domain, observation/inference/queue/action ages, jitter and misses | Metrics cannot be substituted for safety qualification |
| `InferenceBackend` | Replaceable policy-runtime boundary | Rosetta/LeRobot and standalone versus controller-embedded execution | Model/runtime ownership, device placement, errors and shutdown | Upstream runtime remains replaceable behind the project boundary |
| bounded `ActionBuffer` | Bounded producer/consumer handoff before execution | Upstream chunk queues and ros2_control update behavior | Capacity, backpressure, overwrite, expiry and stale-action policy | Upstream code may not introduce an unbounded or bypass queue |

Additional protected abstractions:

- independent `SafetyFilter -> STM32/Zephyr` permission and emergency-stop boundary.

An upstream type name, successful demo or build result cannot close an open item by itself.
