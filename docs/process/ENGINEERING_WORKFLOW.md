# Engineering Workflow

Workflow version: `0.1`

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

### 0.1 2026-09-23

Initial trial release with context refresh levels, five gates, waiver rules, versioning and the experiment, diagnosis and phase-acceptance templates. Phase 3 is reviewed retrospectively; Phase 4 is the first phase expected to use the workflow prospectively.
