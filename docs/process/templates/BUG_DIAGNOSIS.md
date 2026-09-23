# Bug Diagnosis Template

Template version: `0.1`

Status: `TRIAL`

Compatible workflow: `0.1`

## Identity and impact

- Diagnosis ID:
- Owner:
- Affected version, commit or run:
- User or system impact:
- Reproduction status:

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
