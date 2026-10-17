# ADR 0002 ROS Physical AI SIG Alignment

Status: `ACCEPTED_FOR_PHASE5_ALIGNMENT`

Decision date: `2026-10-12`

Decision owner: human

Research snapshot date: `2026-10-12`

Repository reference before this decision: `f787d1fa657161ef72bff3ea419f9bcb65dee133`

## Context

The frozen L1 V2.9 route places ROS 2 and the C++ Runtime in Phase 5, after the Phase 4 DK-2500
edge qualification. It already freezes the project-owned `Observation`, `PolicyOutput`,
`ControlCommand`, `SafetyState` and `RuntimeMetrics` contracts, a replaceable
`InferenceBackend`, a bounded `ActionBuffer`, complete action-age timing and an independent
STM32/Zephyr safety boundary.

The OSRA Physical AI SIG has since established a closely related upstream program. Its first
reference application uses SO-ARM101, ROS 2, LeRobot, ACT, ros2_control, Gazebo, MuJoCo and real
hardware. Its working groups cover standardized interfaces, data collection, policy execution,
reference applications and embodied agents. This makes the SIG unusually relevant to the L1
Phase 5 design and later E3/E5 extensions.

The upstream is not yet a suitable project authority or a drop-in dependency. As of the research
snapshot:

- the reference stack is explicitly work in progress;
- several working-group roadmaps and interfaces are still forming;
- the current demo environment targets ROS 2 Lyrical and Python 3.14, while L1 is frozen on
  Ubuntu 24.04 and ROS 2 Jazzy;
- the demo environment uses source pins, dependency overrides and selected forks;
- ROS-native accelerator buffers and REP-0157 are centered on newer ROS distributions and are
  not a justified Phase 5 baseline without profiling evidence;
- Rosetta and policy-execution placement remain active upstream design topics.

Phase 4 is currently resolving DK-2500 thermal-throttling evidence before Stability. Introducing
ROS integration work now would violate the single-main-milestone rule and mix edge qualification
with Phase 5 architecture work.

## Decision

Adopt a `SIG-aware, SIG-independent` strategy.

The ROS Physical AI SIG becomes an official upstream alignment source for Phase 5 and selected
post-Core extensions. It does not become a new project phase, a replacement architecture or a
required runtime dependency.

Create a bounded `SIG-A0 Upstream Alignment Review` at the Phase 4 to Phase 5 transition. Complete
the review before freezing the Phase 5A package and interface architecture. The review is defined
in `docs/protocols/SIG-A0_UPSTREAM_ALIGNMENT_REVIEW.md`.

The following authorities remain unchanged:

1. L1 V2.9 and its two approved addenda govern scope, phase order and acceptance.
2. Repository interfaces and safety semantics remain the internal system source of truth.
3. ROS 2 Jazzy remains the Core baseline unless a separate ADR authorizes a distribution change.
4. The OpenVINO backend remains the admitted Intel deployment path until later evidence admits
   another backend.
5. Linux, ROS, a policy runtime or an agent may not bypass `SafetyFilter`, MCU permission or the
   hardware emergency-stop boundary.

## Phase placement

| Upstream area | L1 placement | Initial disposition |
|---|---|---|
| `ros2_so_arm`, `feetech_ros2_driver`, ros2_control | Phase 5A | Candidate for isolated Jazzy compatibility review |
| Rosetta ROS 2 to learning-framework contract | Phase 5A | Candidate for offline contract and replay spike |
| SIG policy-execution and ros2_control inference work | Phase 5B | Architecture reference and comparison source |
| Native buffer support and REP-0157 | Phase 5B or later | Defer until measured copies or serialization are a material bottleneck |
| SIG reference demos | Phase 5 validation and E3 | Reference application; do not import as a second system truth |
| REP-0158 and cross-simulator OpenUSD assets | E3 | Watch and evaluate only when the simulation gate opens |
| Embodied Agentic AI and ROS MCP | E5 | Retain the existing low priority and safety constraints |

## Component decision rule

Each reviewed upstream component must receive exactly one disposition:

- `ADOPT_AND_PIN`: use the component at an exact reviewed commit or release;
- `ADAPT_BEHIND_BOUNDARY`: use it only through a project-owned adapter or backend;
- `REFERENCE_ONLY`: use its design or tests as a comparison without runtime dependency;
- `DEFER`: revisit only after a stated trigger;
- `REJECT`: record the incompatibility or architectural conflict.

An `ADOPT_AND_PIN` or `ADAPT_BEHIND_BOUNDARY` decision requires evidence for:

- ROS 2 Jazzy and Ubuntu 24.04 compatibility;
- interface, units, joint ordering, timestamp and QoS semantics;
- build and test reproducibility from an exact upstream identity;
- failure, shutdown and recovery behavior;
- non-bypass of project timing and safety boundaries;
- maintenance cost and rollback;
- and independent human explanation of the adopted mechanism.

Popularity, organizational membership or similarity to the project is not acceptance evidence.

## Permitted scope

- read-only monitoring of official SIG documents, REPs, meeting reports and repositories;
- exact upstream source and dependency snapshots at `SIG-A0` activation;
- interface and architecture mapping against the five frozen L1 contracts;
- isolated Jazzy builds, mock hardware, offline bags and simulation when separately activated;
- small compatibility spikes with preserved commands, diffs, tests and exit conditions;
- upstream issue reports or contributions after local evidence exists and the human owner approves
  the publication scope.

## Prohibited scope

- changing the current Phase 4 protocol, evidence path or thermal diagnosis;
- starting Phase 5 implementation before its entry conditions are accepted;
- upgrading the Core ROS distribution from Jazzy to Lyrical merely to follow the demo stack;
- replacing the five frozen project contracts with an upstream draft without a new ADR;
- importing the complete SIG demo environment into the Core repository as a second architecture;
- adopting native buffers, zero-copy transport or controller-embedded inference before a measured
  need and a bounded protocol exist;
- robot motion, hardware-driver replacement or physical-system claims based only on an upstream
  quick start;
- advancing agentic control ahead of E5 or allowing an agent direct actuator authority.

## Consequences

The project gains a formal path to reuse relevant upstream work without coupling Technical Core
completion to a moving reference stack. Phase 5 design must now show that it considered current
SIG interfaces and implementations, but it may legitimately reject or defer them.

The project also gains a plausible upstream contribution route. Its distinctive future evidence is
expected to be Intel/OpenVINO edge deployment, action freshness and queue behavior, and the
Linux-to-MCU safety boundary rather than another unqualified SO-101 demonstration.

The alignment review adds at most two effective execution days to the Phase 4 to Phase 5
transition. If that timebox is exhausted, unresolved items become explicit `DEFER` decisions and
must not block the Core route.

## Reopening conditions

Create a new ADR or amend this decision if any of the following becomes true:

- an upstream standard requires changing a frozen L1 interface or SafetyState meaning;
- Lyrical or a later ROS distribution is proposed as the Core baseline;
- an upstream component becomes a required production runtime dependency;
- controller-embedded inference would replace the current `InferenceBackend` and `ActionBuffer`
  boundary;
- REP-0157/native buffers become necessary to meet a frozen performance threshold;
- or SIG participation creates a sustained project commitment beyond bounded monitoring and
  evidence-backed contributions.

## Official sources reviewed

- Physical AI SIG documentation: <https://physical-ai.ros.org/>
- OSRA SIG charter dated 2025-06-26:
  <https://osralliance.org/wp-content/uploads/2025/09/tgc-sig-pai-charter.pdf>
- OSRA roadmap and status article dated 2026-08-18:
  <https://osralliance.org/2026/08/ros-keeps-evolving-via-physical-ai-sig/>
- Working groups: <https://physical-ai.ros.org/working-groups/>
- Reference stack: <https://github.com/ros-physical-ai/demos>
- SO-ARM ROS packages: <https://github.com/ros-physical-ai/ros2_so_arm>
- Feetech ros2_control driver: <https://github.com/ros-physical-ai/feetech_ros2_driver>
- Rosetta: <https://github.com/iblnkn/rosetta>
- Policy execution prototype: <https://github.com/saikishor/ros2_policy_execution_pipeline>
- REP-0157: <https://reps.openrobotics.org/rep-0157-2026/>
- REP-0158: <https://reps.openrobotics.org/rep-0158-2006/>
- ROS PMC Physical AI update dated 2026-09-08:
  <https://discourse.openrobotics.org/t/ros-pmc-minutes-for-september-8-2026/57957>
