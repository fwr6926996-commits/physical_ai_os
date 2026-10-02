# Phase 3 Review–Route–Feedback Addendum

Addendum ID: `P3-V2.9-RRF-ADDENDUM-20261001`

Date: `2026-10-01`

Evidence added after the original closeout: `EXP-2026-003 GPU Hang Diagnostic`

Post-review status update: independent learning verification passed and received human acceptance
on `2026-10-01`. The two approved L1 V2.9 Addenda were also reconciled in
`PHASE3_L1_ADDENDA_APPLICABILITY_REVIEW_20261001.md`. The route table below is retained as the review
record; its formal-learning item is now closed.

## 1. Status and scope

This addendum extends the Phase 3 review with evidence collected after the original
`2026-09-23` closeout. It does not rewrite the historical reports or reopen the Phase 3
qualification sequence.

- Phase 3: `PARTIAL PASS — CPU FP32 ONLY`
- CPU FP32: remains the only admitted backend
- GPU.0 FP32: remains `CLOSED_NOT_ADMITTED`
- INT8 mixed PTQ: remains closed negative feasibility evidence
- Phase 4: not started by this addendum
- Robot safety: not evaluated by this addendum

## 2. Verified evidence added after closeout

The bounded EXP-2026-003 investigation established the following evidence chain:

1. A parent/worker mock proved bounded loss-of-progress detection and recovery behavior.
2. Stage 1 proved that a non-reproduction does not invalidate the two historical stability
   failures.
3. Stage 2A reproduced the historical failure path under a frozen baseline.
4. Stage 2B confirmed `infer_entered_not_returned` with low-perturbation shared state.
5. Stage 2C captured a bounded process/thread snapshot without claiming a kernel cause.
6. Stage 2D captured a native GDB stack from the hung worker and safely detached.
7. Stage 2E-A reproduced the hang once, saved the module mappings and converted the main-thread
   PC to stable `libigdrcl.so` offset `0x4008c6` for Build ID
   `58ccca242c62c0629c06940ee3d7b8a40b298e35`.
8. The top nine Stage 2D and Stage 2E `libigdrcl.so` frames differ only by one constant ASLR
   delta, supporting the same internal call chain in both captures.
9. The Stage 2E top PC is immediately after `tpause` in a loop containing `pause`, predicate
   checks, time checks and `sched_yield`; this is strongly consistent with a user-space
   completion-style wait implementation.

The Stage 2E evidence and interpretation are recorded in:

- `../../../../experiments/EXP-2026-003_gpu_hang_diagnostic/STAGE2E_ROUND1_REVIEW.md`
- `../../../../experiments/EXP-2026-003_gpu_hang_diagnostic/STAGE2E_CLOSURE.md`
- `../../../../experiments/EXP-2026-003_gpu_hang_diagnostic/STAGE2E_SOURCE_RESEARCH.md`
- Intel compute-runtime issue `#1012`

## 3. Design–Reality Gap update

### Gap narrowed

The original closeout could only state that the synchronous inference call stopped returning and
that native root cause was unknown. The new evidence narrows the observed location to the same
native `libigdrcl.so` call chain and a user-space completion-style wait loop.

### Gap still open

The evidence still does not identify why the waited condition remained unsatisfied. It cannot
distinguish among an uncompleted GPU task, completion/tag publication failure, kernel/driver
behavior, runtime state error or an earlier component creating bad state. A waiting location is not
proof that the component containing the wait created the fault.

The installed binary is stripped. The instruction sequence is a strong semantic source match, not
a symbolized function-name proof.

### Admission impact

None. The new diagnostic evidence explains the failure boundary more precisely; it does not provide
stability qualification or a verified fix. GPU.0 therefore remains not admitted.

## 4. Engineering learnings

### Implementation detail

- Record `infer_enter`, `infer_return`, heartbeat and watchdog events separately.
- Prefer low-perturbation shared counters for call-boundary state; use verbose IPC only when its
  additional information is needed.
- Native evidence must preserve the target PID, selected main LWP, raw GDB output, module mappings,
  Build ID, file hash and recovery result.
- A debugger helper requires its own timeout, evidence-quality classification and safe-detach check.
- ASLR addresses are not portable evidence until converted to module-relative offsets.

### Phase rule

- Correctness and short-run speed do not satisfy a stability gate.
- A diagnostic run cannot be promoted to qualification evidence.
- Each diagnostic stage must freeze one discriminating question, one evidence contract and a stop
  rule before execution.
- A non-reproduction does not erase a prior valid failure; it only describes that bounded run.
- Stop after the frozen question has been answered. Additional runs require a new question and new
  approval.

### Candidate L1 architecture rule

- Backend selection is an explicit, fail-closed contract. A faster backend is optional until it
  independently passes correctness and stability on the target platform.
- The runtime boundary must support explicit backend identity, bounded loss-of-progress detection,
  recovery outside the blocked inference process and a qualified fallback.
- Offline inference qualification, real-time control qualification and physical robot safety are
  separate gates with separate evidence.

These are feedback proposals only. This addendum does not modify the L1 execution book or the
Architecture Rules.

### Candidate Project OS rule

- Every evidence item must state both the strongest supported conclusion and the tempting stronger
  conclusion it cannot support.
- Preserve historical reports under their original workflow version; add a dated review or
  migration note when later evidence changes understanding.
- Route an unresolved external-component boundary to an upstream issue with reproducible identities
  and stable offsets; do not keep spending local runs without a new discriminating question.

These are feedback proposals only. This addendum does not modify Project OS or
`docs/process/ENGINEERING_WORKFLOW.md`.

### Personal Engineering Model learning

The reusable reasoning model is:

```text
observation -> supported boundary -> competing explanations -> next discriminating evidence
```

In particular, “the thread was observed waiting in component X” is not equivalent to “component X
caused the original defect.”

## 5. Route

| Open item | Route | Why no conclusion yet | Required next evidence | New Notion item recommended |
|---|---|---|---|---|
| Exact `libigdrcl.so` function and waited completion/tag condition | Research / upstream | Binary is stripped and local evidence has no matching symbols | Intel mapping for Build ID and offsets, or matching debug symbols | Yes: link/update the existing GPU diagnostic Research item |
| Origin of the unsatisfied condition | Deep Research | A stopped-time host stack shows location, not causal history | Upstream-directed bounded GPU/kernel evidence that distinguishes submission, execution and completion publication | Only after upstream supplies a concrete question |
| Candidate runtime/driver fix | Experiment | No verified causal change exists yet | One frozen A/B variable, restored reproduction baseline, correctness and stability protocol | Yes, only when a specific candidate fix exists |
| GPU backend re-admission | Implementation + qualification | Diagnostics are not deployment evidence | Verified fix followed by fresh correctness and stability qualification | No implementation task until the fix hypothesis exists |
| Formal learning acceptance | Learning — CLOSED | A standalone verification was required before guided conversation could count as final acceptance | `PHASE3_INDEPENDENT_LEARNING_VERIFICATION.md` records six passed capabilities and human acceptance on `2026-10-01` | Update the existing Phase 3 Learning/Acceptance item as complete |

No new GPU experiment is authorized by this route. Stage 2E-A consumed its one approved attempt and
is closed. The upstream follow-up was submitted to
`https://github.com/intel/compute-runtime/issues/1012`.

## 6. Feedback destinations

| Destination | Original understanding | New evidence | Proposed change | Operation |
|---|---|---|---|---|
| Phase 3 documentation | Loss of progress localized to synchronous infer; native location unknown | Repeated same native chain and stable wait-loop offset | Link this addendum and retain the original gate decision | Extend |
| L1 project book | Accelerator path was part of the intended backend route | GPU may pass correctness and speed yet fail bounded stability | State accelerator as optional, independently qualified, fail-closed; preserve CPU path and explicit identity | Extend |
| Architecture Rules | Backend abstraction mainly selects execution target | A blocked backend requires out-of-process detection and recovery | Add backend health/recovery and evidence-separated admission boundaries | Extend |
| Project OS | Evidence/diagnosis separation exists at a high level | The staged investigation demonstrates evidence-level ceilings and perturbation control | Add an evidence-claim matrix and one-question diagnostic-stage rule after trial review | Extend |
| Personal Engineering Model | Debugging seeks a cause | Progressive localization often produces bounded knowledge before root cause | Adopt the observation/boundary/alternatives/next-evidence loop | Add |
| Independent Decision/Review | Original GPU closure explains non-admission | Source-level boundary is materially sharper but admission unchanged | Keep EXP-2026-003 closure as the independent diagnostic record | Keep |

## 7. Effect on subsequent L1 understanding

Final conclusion: **需要局部修订**.

- Phase order: keep the current main-line order; do not block CPU-only work on open-ended GPU root
  cause research.
- Technology stack: no mandatory replacement is proven.
- Software layers and interface boundaries: explicitly model backend health, watchdog and recovery
  outside the potentially blocked inference worker.
- Backend/hardware abstraction: treat accelerator support as independently admitted capability, not
  an assumed property of the model runtime.
- Runtime and real-time: offline synchronous latency and stability remain insufficient for real-time
  control claims.
- Safety: unchanged; physical safety requires separate real-world verification.
- Tests and acceptance: add bounded loss-of-progress, recovery and artifact-identity evidence to
  backend qualification.
- Cross-platform migration: repeat hardware/software truth and admission on each target; the 255H
  result does not transfer to DK-2500.
- Optional upgrades: GPU, NPU and reduced precision remain optional upgrade routes behind fresh
  decisions and qualification.

This is not an architecture-level route reset because the CPU FP32 path remains valid and the
backend boundary already permits a fail-closed optional accelerator. The new evidence strengthens
that boundary and its acceptance contract.

## 8. Notion update plan

Recommended placement, without writing to Notion in this repository step:

1. Add a Phase 3 child page named `Phase 3 Review–Route–Feedback Addendum — 2026-10-01`.
2. Link the existing Phase 3 Closure, GPU diagnostic Experiment and Intel issue `#1012`.
3. Route the exact function/completion-condition question into the existing Research database.
4. Add the five feedback proposals as review candidates, not as already-approved rules.
5. Keep L1, Architecture Rules and Project OS unchanged until the human approves each promotion.

## 9. Next phase gate

This addendum does not start Phase 4. The existing ADR-0001 entry conditions remain controlling:
DK-2500 hardware/software truth, frozen protocol, explicit CPU FP32 identity and correctness,
bounded recovery, and no robot-motion or safety claim.

Formal Phase 3 human acceptance changed from pending to accepted only after the standalone
`PHASE3_INDEPENDENT_LEARNING_VERIFICATION.md` record passed all six capabilities and the human
explicitly accepted the result on `2026-10-01`. Conversation participation was retained as learning
evidence and was not silently converted into the final gate.
