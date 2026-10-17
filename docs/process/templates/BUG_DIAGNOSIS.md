# Bug Diagnosis Template

Template version: `0.2`

Status: `TRIAL`

Compatible workflow: `0.3`

## Identity and impact

- Diagnosis ID:
- Owner:
- Affected version, commit or run:
- User or system impact:
- Reproduction status:

## Learning contract

Complete this section only when the diagnosis has meaningful learning value. Otherwise record
`NOT_REQUIRED` and use `ASSIST` or `DELEGATE` as appropriate.

- Required human depth: `EVIDENCE_LITERACY` / `OPERATOR` / `IMPLEMENTER` / `NOT_REQUIRED`
- Why this capability matters to the current or future L1 path:
- Source pack, normally one to three exact files, sections or evidence artifacts:
- Transferable principles the human must explain:
- Incident-specific syntax or implementation details that may be delegated:
- Decision checkpoints where understanding must be verified:
- Fast Path eligibility and work that may be batched:
- Learning exit condition:
- Remaining Mystery Debt: `NONE` / `NON_BLOCKING` / `BLOCKING`, with reason

Teach first, then verify with normally one to three open-evidence questions at each material
decision checkpoint. Do not require closed-book recall or repeat a full check after every mock,
preflight or evidence-packaging substep.

## Observed facts

- Symptom:
- Last confirmed-good event:
- First failed or missing event:
- Timestamp or iteration:
- Process, thread or device state:
- Exact evidence references:

## Execution chain

```text
Input -> entry point -> state change -> interface -> failure boundary -> observed consequence
```

## Fault boundary

- Narrowest boundary supported by evidence:
- Components inside the boundary:
- Components not yet implicated:
- What the current evidence cannot prove:

## Hypothesis matrix

| Hypothesis | Supporting evidence | Contradicting evidence | Status | Next discriminating check |
|---|---|---|---|---|
| | | | OPEN / REJECTED / CONFIRMED | |

## Diagnostic plan

- Highest-information next check:
- Single changed variable:
- Evidence to capture before recovery:
- Maximum attempts and stop rule:
- Risk and recovery path:

## Conclusion

- Confirmed root cause, if proven:
- Otherwise current classification:
- Fix or bounded disposition:
- Regression verification:
- Remaining uncertainty:

Use `root cause` only when targeted evidence confirms the causal mechanism. Otherwise use `fault boundary`, `supported inference` or `open hypothesis`.

## Changelog

### 0.2 2026-10-15

Added the learning contract, required-depth declaration, source pack, decision checkpoints, Fast
Path and explicit Mystery Debt disposition.

### 0.1 2026-09-23

Initial trial template.
