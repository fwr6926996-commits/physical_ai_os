# INT8 Architecture Decision Worksheet

Status: `HUMAN_DECISION_ACCEPTED`

Decision owner: human

## Decision statement

Decide whether to close the current INT8 feasibility branch as reproducible negative evidence or invest in a bounded accuracy-recovery experiment. A justified evidence-gathering deferral is also valid if a critical unknown prevents a responsible choice.

## Frozen facts

- Basic mixed PTQ pipeline completed using 300 calibration frames.
- Paired fidelity validation used 100 non-overlapping frames from the same one-task training dataset.
- FP32 artifact remained unchanged.
- INT8 artifact size is 26.25% of FP32, a 73.75% reduction.
- INT8 strict reference correctness failed.
- Material errors are concentrated in `elbow_flex.pos`, with rare large `gripper.pos` spikes.
- First-action error is also material.
- Qualified INT8 latency ranking has not been performed.
- Phase 3 still has GPU tail-latency profiling and stability/resource evidence work.
- L1 V2.9 permits reproducible INT8 negative evidence when deployment feasibility is not established.

## Unknowns

- Physical unit and task-tolerable deviation for each action dimension.
- Whether current offline action deviation causes a task-success or safety regression on the robot.
- Which quantized operations are responsible for the fidelity loss.
- How many operations accuracy-aware PTQ would revert to floating point.
- Remaining size, latency and power benefit after accuracy recovery.
- Generalization beyond the one-task training distribution.
- The human's intended Phase 3 time/effort budget and strategic value assigned to INT8/NPU deployment.

## Option A — Close current INT8 feasibility

Benefits:

- Converts the experiment into complete, reproducible negative evidence.
- Preserves gate discipline and prevents speed claims for an incorrect candidate.
- Frees Phase 3 effort for GPU tail profiling, stability and resource evidence.
- Is reversible: artifacts and exact indices remain available for a later recovery branch.

Costs:

- No admitted INT8 package or qualified INT8 latency result.
- No current route to an NPU backend, because NPU FP16 also failed strict correctness.
- Less information about layer sensitivity and recoverability.

Risks:

- A recoverable candidate may be abandoned too early.
- The project may miss useful deployment/research learning if INT8 is strategically important.

Workload: low. Finalize the negative-result report, retain artifacts/hashes, and continue remaining Phase 3 gates.

## Option B — Run bounded accuracy recovery

Benefits:

- May recover fidelity by retaining sensitive operations in floating point.
- Could preserve part of the 74% size reduction and open CPU/GPU/NPU INT8 evaluation.
- Produces deeper evidence about layer sensitivity and accuracy/performance trade-offs.

Costs:

- Requires a validation metric, direction, allowed degradation and stop condition before execution.
- Accuracy-aware PTQ performs repeated validation and may require several experiments.
- Reverted floating-point operations can reduce size and performance benefits.
- A task-level or physical-tolerance claim may require additional robot validation.

Risks:

- Optimizing against the current one-task training-derived validation set may overfit the evidence set.
- A poorly chosen scalar metric can hide a dangerous joint-specific or first-action spike.
- Recovery may fail or produce a model that is accurate but not meaningfully faster.
- Extra work can delay still-open mandatory Phase 3 evidence.

Workload: medium to high. Define a safety-sensitive scalar validation metric; implement and verify the validation function; run accuracy-aware PTQ; inspect reverted operations; repeat fidelity gates; only then benchmark admitted candidates.

## Human criteria

Fill these before choosing:

1. Primary Phase 3 objective:
2. Hard constraints that cannot be traded for speed or size:
3. Strategic importance of an admitted INT8/NPU path:
4. Maximum justified recovery effort before stopping:
5. Most decision-critical missing evidence:
6. Chosen option or justified evidence-gathering deferral:
7. Reasoning, including opportunity cost and stop condition:

## Review rule

Codex reviews whether the reasoning follows from evidence, exposes assumptions, respects hard constraints, considers opportunity cost and defines a stop condition. Codex does not replace the human choice with its own preference.

## Frozen human decision — 2026-09-15

- Choice: **Option A — close the current INT8 feasibility branch as reproducible negative evidence.**
- Primary objective: finish correctness-gated OpenVINO pre-deployment evidence before advancing toward deployment.
- Hard constraints: task quality and avoidance of dangerous actions cannot be traded for speed or model size.
- Strategic importance: medium; this is a result for the current INT8 candidate, task evidence and available NPU path, not a general rejection of INT8 or NPU.
- Accepted opportunity cost: the current branch gives up the chance to recover this INT8 candidate now, while preserving time for the remaining Phase 3 stability, resource and bottleneck evidence.
- Recovery budget under this decision: zero rounds. A future recovery branch would require a new human-owned decision; the stated upper bound for such a branch is two rounds.
- Safety interpretation: offline correctness failure can reject a candidate, while offline correctness success only grants eligibility for later robot/system validation. Collision behavior, joint motion and E-stop effectiveness require separate validation.
- Review result: architecture-decision learning **PASS**; final decision remains human-owned.
