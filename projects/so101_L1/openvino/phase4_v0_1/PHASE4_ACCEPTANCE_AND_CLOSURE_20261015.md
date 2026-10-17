# Phase 4 Acceptance and Closure

Phase: `Phase 4 — DK-2500 CPU FP32 qualification`

Acceptance record ID: `P4-DK2500-ACCEPTANCE-20261015-01`

Governing specifications:

- `PHASE4_CPU_FP32_QUALIFICATION_PROTOCOL.md`
- `PHASE4_STABILITY_PROTOCOL_V0_2_20261014.md`

Repository state: worktree based on Git commit `f787d1fa657161ef72bff3ea419f9bcb65dee133`;
the Phase 4 closeout records and evidence are not yet represented by a release tag.

Decision owner: human owner

Decision date: `2026-10-15`

## Completion and gate state

- Experimental work: `COMPLETE`
- Engineering gate: `PASS — CPU FP32 OFFLINE BACKEND ONLY`
- Backend admission: `ADMITTED — FROZEN CPU FP32 OFFLINE SCOPE ONLY`
- Learning verification: `PASS`
- Final human acceptance: `ACCEPTED`

These states are separate. The experiments completed before the human admission and acceptance
decision; passing the engineering gate did not by itself authorize deployment or physical use.

## Gate matrix

| Gate | Requirement | Evidence | Result | Limitation or follow-up |
|---|---|---|---|---|
| Hardware/software truth | Record DK-2500 and runtime identity before qualification | `DK2500_HARDWARE_SOFTWARE_TRUTH_20261003.md`; `evidence/phase4_0_truth/dk2500_truth_20261003.json` | PASS | Applies only to the recorded target state |
| Artifact identity | Preserve model, reference and implementation hashes | protocol, target preflights and run evidence | PASS | Any material hash or runtime change reopens qualification |
| Compile/load and correctness | Explicit CPU FP32, no fallback, frozen output contract and tolerance | `PHASE4_ROUND1_CORRECTNESS_REVIEW_20261003.md` | PASS | Frozen reference input only |
| Short measurement | One correctness call, ten warmups and 100 measured iterations with complete evidence | `PHASE4_ROUND2_SHORT_REVIEW_20261009.md` | PASS | No performance or real-time admission |
| Thermal observation route | Investigate the counter observation without retroactively changing the Short gate | `PHASE4_THERMAL_THROTTLE_DIAGNOSIS_20261009.md` and D1/D2/D3 reviews | CLOSED FOR PHASE ENTRY | No root cause proven; diagnostic risk is carried forward |
| Stability | Complete 30 minutes with zero incorrect/non-finite outputs, missing progress, exceptions, crashes, watchdogs, hard thermal stops or evidence failures | `PHASE4_ROUND3_STABILITY_REVIEW_20261015.md`; `evidence/phase4_3_stability/independent_review.json` | PASS | Fixed-input offline synchronous repeated inference only |
| Independent learning | Explain the admission boundary, throttle evidence limits and offline/physical-safety distinction | human verification completed on `2026-10-15` | PASS | Detailed Python implementation fluency remains non-blocking learning work |
| Human decision | Separately admit the backend and accept the phase | decision quoted below | ACCEPTED | Does not authorize a new experiment or physical deployment |

## Admission

### Admitted

Only the following backend path is admitted:

- target: the recorded DK-2500 with `Intel(R) Core(TM) Ultra 5 225U`;
- runtime: OpenVINO `2026.2.1-21919-ede283a88e3-releases/2026/2` as recorded by the
  qualification evidence;
- backend: explicit `CPU`;
- precision: explicit `f32`;
- performance hint: `LATENCY`;
- model XML SHA-256:
  `54615bff5874f134521353c8240ecff6f95277e51c094b543713bc1d6c60879e`;
- model BIN SHA-256:
  `96c225f0676edcb44b641906e93222d0f52883a7ed6956725c904266c717848a`;
- input contract: `state float32[1,6]` and `wrist_image float32[1,3,480,640]`;
- output contract: normalized `action_chunk float32[1,100,6]`;
- correctness gate: frozen reference input/output with `rtol=1e-4`, `atol=1e-5`;
- execution boundary: offline synchronous, frozen-input repeated inference under the recorded
  qualification controls.

The admission is invalidated by silent backend fallback or material drift in the recorded target,
runtime, model, implementation, input/output contract or qualification controls.

### Not admitted

- NPU, GPU, `AUTO`, `HETERO`, FP16, INT8 and every other backend or precision;
- performance rank, throughput target, control frequency or real-time deadline;
- changing-input behavior or distribution shift;
- full camera/preprocess/inference/postprocess/control/actuation stability;
- another DK-2500 software or hardware state, another machine or another model;
- unattended deployment, robot task success or physical-system safety.

### Active configuration

The only admitted Phase 4 backend configuration is explicit `CPU` / `f32` / `LATENCY` under the
identity and interface constraints above. Historical Phase 3 configurations and exploratory Phase
4 diagnostic configurations are evidence, not active deployable configurations.

## Verified evidence summary

- Round 1 compiled and loaded the frozen package on explicit DK-2500 CPU FP32 and passed frozen
  correctness with maximum absolute error `2.86102294921875e-06`.
- Round 2 completed 1 correctness, 10 warmup and 100 measured full-host-pipeline iterations with
  `111/111` finite and correct results and no watchdog or recovery. Its latency remained
  diagnostic-only.
- Round 3 completed 1 correctness, 10 warmup and `11,918` measured calls over `1800.0845 s`.
  All `11,929` inference-enter events had matching returns; incorrect and non-finite counts were
  zero; maximum absolute error was `2.86102294921875e-06`; no exception, crash, watchdog, recovery,
  monitor failure, evidence failure or observed `>=100 C` sample occurred.
- Round 3 inference-only latency was P50/P95/P99 `150.429/161.487/168.826 ms`; this is reported,
  not admitted as a performance or real-time guarantee.
- Round 3 observed maximum package/any-sensor temperatures `91/93 C`. Exact-path throttle count
  and duration fields increased early under load. Duplicate package paths were not summed, and the
  evidence does not establish a thermal, firmware, kernel, OpenVINO or hardware root cause.

## Design–reality conclusion

The recorded DK-2500 CPU FP32 path satisfied the Phase 4 qualification design for frozen-input
offline inference. The observed throttle fields did not violate a frozen hard gate: values below
the precommitted `100 C` stop were diagnostic-only. They remain relevant engineering evidence but
cannot be retroactively converted into a failure or a root-cause claim.

The phase also confirmed that offline backend qualification is materially narrower than the later
robot runtime. Changing observations, end-to-end control timing and physical safety require their
own protocols and evidence; their absence is not an uncompleted Phase 4 requirement.

## Unresolved work and waivers

- Unresolved problems: cause and platform-wide meaning of the observed throttle-field changes;
  changing-input behavior; end-to-end runtime timing; and physical-system safety behavior.
- Problems closed without root cause: the bounded thermal-counter diagnosis was closed only as
  sufficient to resume qualification; it did not prove a causal component.
- Accepted waivers or ADRs: Phase 4 followed the CPU-only entry decision in
  `docs/decisions/ADR-0001-phase4-cpu-only-entry.md`. This is not a waiver for physical deployment.
- Risks carried forward: backend qualification may not predict behavior under changing images,
  control-loop load, device I/O, actuation, faults or different thermal/power conditions.
- Reopening conditions: any material identity/configuration drift; any incorrect or non-finite
  output; crash, timeout or missing evidence; a new backend/precision/model; or evidence that
  contradicts the accepted offline stability result.

## Scope boundary

### What this phase proves

Under the frozen identity and qualification thresholds, the admitted DK-2500 CPU FP32 path can
compile, load, reproduce the frozen reference result and sustain 30 minutes of repeated offline
synchronous frozen-input inference without a frozen hard-gate failure or evidence gap.

### What this phase does not prove

It does not prove performance or real-time suitability, changing-input correctness, task success,
general portability, unattended deployment or a cause for the throttle observations.

### Safety and physical-system boundary

No robot was actuated by this qualification. Collision avoidance, joint range and stall behavior,
power integrity, E-stop behavior, fault recovery and safe-state enforcement remain unverified and
must be handled by the later runtime and physical-safety layers. CPU FP32 admission cannot bypass
those layers.

## Route after closure

| Open question | Route | Required evidence before any broader claim |
|---|---|---|
| Changing observations | Integration experiment | Representative changing-input source, frozen interface, correctness/oracle and bounded run protocol |
| Full host pipeline | Implementation + qualification | Camera/input through preprocess, inference, postprocess and command output with complete event evidence |
| End-to-end timing | Real-time experiment | Control-period budget, deadline/jitter gates, overload behavior and measured worst-case path |
| Physical behavior | Physical safety protocol | Joint limits, collision constraints, stall detection, power monitoring, E-stop and safe-state recovery evidence |
| NPU/GPU/quantized upgrade | Optional upgrade experiment | Separate correctness-first protocol, identity freeze, stability evidence and explicit admission decision |
| Throttle cause, if it becomes decision-relevant | Research/diagnosis | A new discriminating question and protocol; the Phase 4 observation alone is not a root cause |

These routes are planning boundaries, not authorization to execute them.

## Next-phase decision

- Next phase entry: `ALLOWED`
- Permitted scope: design and review the first bounded integration protocol using only the admitted
  CPU FP32 offline backend.
- Prohibited scope: treating the backend as deployment-ready; robot actuation; claiming real-time,
  task-success or safety qualification; switching backend or precision without a separate gate.
- Entry conditions: re-ground against the governing L1 plan and both accepted Addenda; identify
  the next phase's exact objective and safety boundary; freeze its interface, evidence contract,
  stop/recovery rules and human authorization before execution.
- Required first protocol: changing-input/full-host-pipeline integration protocol, unless the
  governing L1 sequence assigns a narrower prerequisite first.

## Independent verification

- [x] The operator can explain the admission decision.
- [x] Critical files, interfaces and evidence can be identified.
- [x] The path can be reproduced or independently recomputed.
- [x] Debugging boundaries and remaining uncertainty can be explained.
- [x] Offline qualification is not confused with physical-system safety.

The final check corrected one wording issue: throttle changes below the hard thermal stop are
`diagnostic-only`, not an independently passing qualification item. The correction does not alter
the human's demonstrated understanding or the engineering result.

## Human decision

The human owner recorded:

> 确认学习验收通过；批准 CPU FP32 仅作为冻结条件下的 DK-2500 离线后端准入；接受
> Phase 4 以 `PASS — CPU FP32 OFFLINE BACKEND ONLY` 关闭，变化输入、实时性、完整控制链路与
> 物理安全分流到后续阶段。

This decision accepts the phase and backend only within the bounds recorded above. It is not an
experiment authorization and does not authorize target execution or robot motion.

## Notion projection

- Sync requirement: `REQUIRED`
- Sync state: `SYNCED`
- Notion page:
  `https://app.notion.com/p/3fa078164aa28111bd51df42a8c88e71?pvs=204`
- Source revision: `WORKTREE_BASE:f787d1fa657161ef72bff3ea419f9bcb65dee133`
- Registry sync ID: `NSYNC-P4-CLOSURE-20261015-01`

The phase decision is effective in the repository regardless of projection freshness. The sync
state will be updated only after Notion write-back verification and registry validation.
