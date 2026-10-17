# Engineering Workflow

Workflow version: `0.3`

Status: `TRIAL`

Effective date: `2026-09-23`

Compatible policy: `AGENT.md` policy version `0.2`

## Purpose

This workflow translates the repository policy into a repeatable path for engineering tasks, experiments, debugging and phase transitions. It is intended to reduce ambiguous decisions and agent action space while preserving useful engineering judgment.

The workflow does not replace the governing execution book, architecture decisions, safety requirements or human acceptance.

## Context refresh levels

### Task refresh

Use for a small, local and low-risk change.

Confirm the related files, entry point, relevant tests, current diff and protected behavior. A full repository reread and external research are normally unnecessary.

### Feature refresh

Use for an important feature, performance investigation or non-trivial bug.

Confirm the relevant modules, interfaces, call chain, configuration, tests, recent changes and evidence. Establish an official external baseline when current framework or platform behavior affects the design.

### Phase re-grounding

Use before a phase transition, architecture review, formal closeout or major redesign.

Reconcile the governing specification, repository map, Git state, active configuration, artifacts, evidence, open risks, waivers and entry conditions for the next phase. Historical conversations and reports are inputs to review, not sources of current truth.

## Learning depth and fast path

For work with meaningful learning value, declare the required human learning depth before the
first learning check. Use the lowest level that preserves independent engineering ownership:

* **Evidence literacy** — distinguish observed fact, supported inference, open hypothesis and
  unsupported claim using the supplied evidence.
* **Operator** — additionally identify the relevant interface, choose or review a control and next
  discriminating check, and explain stop, recovery and decision boundaries.
* **Implementer** — additionally modify and debug the instrumentation, harness or implementation.

Core L1 diagnosis defaults to `Operator`. Do not require `Implementer` depth unless building or
modifying the diagnostic tooling is itself an explicit learning objective. Routine or already
understood work may use `ASSIST` or `DELEGATE` without a new learning contract.

Learning checks are open-evidence engineering reviews, not closed-book recall tests. Before asking
the user to interpret a first-encounter mechanism:

1. explain the mechanism and why it matters to the current decision;
2. provide a source pack of normally one to three exact files, sections or evidence artifacts and
   state what question each source helps answer;
3. distinguish the transferable principle from incident-specific names, fields and syntax; and
4. ask only questions that can be answered from the explanation and supplied sources.

Place learning checkpoints at material decision boundaries, normally before target/system access,
when evidence selects the next experiment, and before a diagnosis, admission or phase disposition.
Do not repeat a full learning check after every mock, preflight or evidence-packaging substep.
Normally ask one to three decision-relevant questions per checkpoint. If the user cannot answer,
teach the missing concept and then use at most one transfer question; do not turn uncertainty into
a chain of reworded quizzes.

When the user requests faster progress, use the **Fast Path**:

* preserve engineering, evidence, authorization, recovery and safety gates;
* batch related low-risk substeps and their reviews;
* delegate tool implementation, parsers, mocks, hashes and repetitive evidence handling unless
  they are explicit learning objectives;
* keep human ownership of the question, evidence meaning, risk boundary and final decision; and
* record remaining Mystery Debt as blocking or non-blocking instead of expanding the current task
  without a decision need.

Learning is sufficient when the user can use the supplied sources to explain the supported claim,
its limit, the next bounded check or disposition, and the relevant stop/recovery boundary. Detailed
code or component internals remain optional unless required by the declared learning depth.

## Five gates

### Gate 1 Grounding

Before meaningful work, identify:

* the objective and scope;
* the current source of truth;
* the relevant code, configuration and evidence;
* the Git state and artifact identities;
* historical material that must not be treated as active;
* external official guidance that materially affects the decision;
* and facts that remain unknown.

### Gate 2 Protocol freeze

Use `templates/EXPERIMENT_PROTOCOL.md` before a qualification experiment.

Freeze the experimental classification, inputs, environment, single changed variable, measurement boundaries, metrics, thresholds, maximum runs, stop rules, evidence outputs and prohibited claims before execution.

Exploratory work must be labeled as exploratory. It may inform a later protocol but cannot be silently promoted into qualification evidence.

### Gate 3 Controlled execution

Execute only within the frozen scope. Preserve raw output, record deviations and stop when a hard stop rule triggers.

If a material variable or acceptance rule changes, stop the qualification run. Create a protocol amendment or a new protocol version before continuing. Do not rewrite the original protocol after seeing the result.

### Gate 4 Trace and verification

Use `templates/BUG_DIAGNOSIS.md` for important failures or unexpected performance behavior.

Separate observed facts, supported inferences, open hypotheses and proven root cause. A diagnosis must identify the last confirmed-good event, first failed or missing event, fault boundary and supporting evidence.

Verification must be proportional to risk and should include independent recomputation, regression checks or reproduction where appropriate. A fluent explanation is not evidence.

### Gate 5 Phase acceptance

Use `templates/PHASE_ACCEPTANCE.md` at phase closeout.

Record experimental completion, gate results, admitted and rejected artifacts, unresolved problems, waivers, learning verification, active configuration, next-phase entry conditions and the human-owned final decision separately.

## Required relationships

Each qualification result should reference its protocol ID and version. Each important diagnosis should reference the affected run or evidence. Each phase acceptance should reference the evidence and decisions that support admission.

The intended chain is:

```text
Protocol -> raw evidence -> diagnosis or review -> decision -> phase acceptance
```

## Notion status projection

Use `NOTION_SYNC.md` after a reviewed event changes a stage decision, phase state, execution block,
waiver, diagnosis disposition or next gate. Git and preserved evidence remain authoritative;
Notion is a traceable human-facing projection.

Each required projection must identify its source paths and revision, preserve supported and
prohibited claims, and be read back before it is marked `SYNCED` in the local, ignored
`notion_sync_registry.json`. Use `notion_sync_registry.example.json` as the public configuration
template and run `python3 scripts/check_notion_sync.py` to detect source drift. Notion freshness is
not an engineering gate, and a failed sync does not rewrite the underlying decision.

## Waivers

A waiver is not a pass. It permits a bounded next action despite an unmet or changed gate.

A waiver must state:

* the unmet requirement;
* the evidence supporting the bounded exception;
* the admitted and prohibited scope;
* the risks carried forward;
* the owner;
* the expiry or reopening condition;
* and the next phase action it permits.

## Versioning and change control

`AGENT.md` contains durable principles and changes rarely. This workflow contains operational rules. Templates are the most frequently adjusted layer.

Use these version changes:

* patch: clarification with no changed requirement;
* minor: a new field, gate or compatible behavior;
* major: an incompatible gate, responsibility or evidence contract.

Existing evidence retains the workflow and template version under which it was created. Do not rewrite historical records to appear compliant with a later version. Add a retrospective or migration note instead.

Review workflow friction at phase closeout. Modify a template first, promote a repeated rule into this workflow only after trial, and modify `AGENT.md` only when the rule is durable across phases.

## Template lifecycle

Templates use `DRAFT`, `TRIAL`, `ACTIVE`, `DEPRECATED` and `ARCHIVED` states.

A new template is justified only when the same high-risk work has recurred, lack of structure caused a concrete problem, and an existing template cannot absorb the need with a small section. Register active and trial templates in `TEMPLATE_REGISTRY.md`.

## Changelog

### 0.3 2026-10-15

Added explicit learning-depth levels, open-evidence source packs, decision-boundary checkpoints and
a Fast Path that reduces learning ceremony without removing engineering or safety gates.

### 0.2 2026-10-12

Added the repository-to-Notion projection contract, event triggers, read-back verification and
hash-based freshness check. Repository evidence remains the source of truth. The real page mapping
is local configuration; only its redacted template belongs in the public repository.

### 0.1 2026-09-23

Initial trial release with context refresh levels, five gates, waiver rules, versioning and the experiment, diagnosis and phase-acceptance templates. Phase 3 is reviewed retrospectively; Phase 4 is the first phase expected to use the workflow prospectively.
