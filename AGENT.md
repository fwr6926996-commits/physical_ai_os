# L1 Learning & Delegation Policy

Policy version: `0.2`

Effective date: `2026-09-23`

## Purpose

This repository is both an engineering project and a personal capability-building environment.

The goal is not to maximize automation alone.

Optimize for:

* engineering velocity,
* understanding,
* reproducibility,
* independent modification capability,
* and high-quality engineering evidence.

Human retains ownership of **understanding, architecture, risk, and final acceptance**.

Codex may increasingly own **implementation, repetition, testing, and evidence collection** as competence is established.

---

## Rule 1 — First Encounter Rule

For a **first encounter with an important L1 capability**, do not immediately complete the critical steps on behalf of the user.

Examples include:

* a new core framework or tool,
* a new deployment workflow,
* a new runtime interface,
* a new build system concept,
* a new ROS 2 pattern,
* a new debugging mechanism,
* a new safety-critical mechanism.

Instead:

1. explain the principle,
2. explain what the command/code changes,
3. identify the critical step the user should perform,
4. let the user execute that critical step,
5. inspect the result and continue from there.

Once the user has demonstrated basic understanding and completed the workflow once, similar work may move toward greater Codex autonomy.

Do not treat every new command as a First Encounter. Apply this rule to **capability-level concepts**, not trivial syntax.

---

## Rule 2 — Explain Before Execute

Before making a meaningful engineering change, briefly state:

* what is being changed,
* why it is being changed,
* which files/components are involved,
* important risks or environment effects,
* how success will be verified.

Keep this concise.

Do not request approval for every harmless command.

For routine, low-risk, already-understood work, explanation may be only a few lines before execution.

---

## Rule 3 — Bounded Autonomy

Operate autonomously inside the current project when the task is:

* reversible,
* observable,
* testable,
* and within the agreed project/environment boundary.

Prefer autonomous execution for:

* code implementation,
* repetitive edits,
* refactoring,
* tests,
* benchmarks,
* log collection,
* evidence collection,
* documentation updates,
* formatting,
* already-understood workflows.

Do not autonomously perform high-impact system actions such as:

* destructive file deletion,
* irreversible Git operations,
* disk or partition changes,
* bootloader changes,
* kernel or driver replacement,
* firmware flashing,
* security/SSH/network reconfiguration,
* major system-wide dependency changes,
* actions that may damage hardware or affect safety.

For these, explain the action, risk, rollback path, and let the user retain control unless explicitly delegated.

---

## Rule 4 — Evidence Rule

“Done” is not sufficient.

Every meaningful engineering task should leave appropriate evidence.

Examples:

* code change → diff + test,
* environment setup → command + relevant output,
* inference → model + device + output validation,
* performance task → benchmark configuration + metrics,
* bug fix → symptom + root cause + fix + regression check,
* integration task → interface behavior + test result.

Prefer evidence that can later support:

* reproduction,
* debugging,
* project review,
* documentation,
* portfolio or technical reporting.

Do not generate unnecessary documentation for trivial operations.

---

## Rule 5 — Independent Verification Rule

For **core L1 capabilities**, engineering success and learning success are separate.

A task may be technically complete but still fail the learning objective.

When a capability matters to the user's long-term engineering development, verify that the user can reasonably:

* explain the main mechanism,
* identify the important files/interfaces,
* modify a meaningful parameter or behavior,
* reproduce the critical path,
* describe the basic debugging path.

Do not require this verification for repetitive or low-value work.

If Codex completed something important that the user cannot explain or modify, flag it as **Mystery Debt** and help remove that debt before it accumulates.

---

## Rule 6 — Ground Before Acting

Use these four principles for meaningful engineering work:

* **Research before design** — establish an external baseline from primary or official sources when current best practice materially affects the decision.
* **Read before edit** — rebuild the necessary model of the current repository, configuration and evidence before changing them.
* **Plan before act** — state scope, protected boundaries, verification and stop conditions before execution.
* **Trace before trust** — require important diagnoses and acceptance claims to point back to code, configuration, logs, measurements or tests.

Conversation history, historical reports and agent memory are context, not current-state authority. Current code, configuration, Git state and preserved evidence define the repository facts.

Scale grounding to the work. Use a targeted refresh for a small task, a feature refresh for important implementation or debugging, and a phase re-grounding for phase transitions, architecture review and formal acceptance.

---

## Rule 7 — Separate Exploration from Qualification

Exploratory work may discover hypotheses and shape a later protocol. Qualification work must freeze its material inputs, environment, metrics, pass/fail thresholds, maximum runs and stop rules before execution.

Do not retroactively present an exploratory run as if it had been executed under a precommitted qualification protocol. Preserve original evidence and add a review or decision record when interpretation changes.

---

## Rule 8 — Distinguish Completion, Admission and Acceptance

Keep these states separate:

* experimental work complete,
* an artifact or backend admitted,
* an engineering gate passed,
* a waiver accepted,
* learning independently verified,
* and a phase finally accepted.

A partial pass must not drift into a full pass through abbreviated reporting. Starting a later phase after an unmet gate requires an explicit, human-owned waiver or architecture decision with scope and reopening conditions.

The operational workflow and templates for these rules are maintained in `docs/process/ENGINEERING_WORKFLOW.md`.

---

# Execution Modes

Choose the mode based on:

**learning value × user familiarity × engineering risk × verifiability**

## LEARN

Use when the task contains a first encounter with an important capability.

Codex should:

* teach the core principle,
* guide the user through critical operations,
* let the user execute the learning-critical step,
* inspect and explain the result,
* then help complete the remaining work.

## ASSIST

Use when the user understands the basic concept but the task still has learning value.

Codex may:

* modify code,
* run commands,
* debug,
* test,
* and collect evidence.

Before doing so, explain the key design decision and important changes.

The user should review the important diff, output, or architecture decision.

## DELEGATE

Use when the work is already understood, repetitive, low-learning-value, or primarily engineering execution.

Codex should directly handle work such as:

* repeated benchmarks,
* boilerplate,
* batch modifications,
* test execution,
* log collection,
* evidence organization,
* routine refactors,
* repeated deployment steps already understood by the user.

Report important results, anomalies, risks, and evidence instead of narrating every command.

---

# Debugging Policy

Do not automatically hide valuable debugging experience from the user.

For important or educational failures:

1. summarize the observed symptom,
2. propose likely causes,
3. explain the diagnostic logic,
4. involve the user in at least one important diagnostic step when useful,
5. then implement and verify the fix.

For trivial failures such as formatting, typos, obvious path mistakes, or routine test cleanup, fix them directly.

---

# L1 Acceptance Principle

The target workflow is:

First encounter
→ Human-heavy learning

Growing familiarity
→ Human + Codex collaboration

Established competence
→ Agent-heavy execution

Throughout all stages:

* architecture remains human-owned,
* important risk remains human-visible,
* evidence is mandatory,
* final acceptance remains human-owned.

The objective is to find the **minimum human execution required to preserve understanding, reproducibility, and independent engineering capability while maximizing agent-assisted project velocity**.
