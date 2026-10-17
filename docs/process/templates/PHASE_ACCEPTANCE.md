# Phase Acceptance Template

Template version: `0.2`

Status: `TRIAL`

Compatible workflow: `0.3`

## Identity

- Phase:
- Acceptance record ID:
- Governing specification:
- Git commit or release tag:
- Decision owner:
- Decision date:

## Completion and gate state

- Experimental work: `NOT_STARTED` / `IN_PROGRESS` / `COMPLETE`
- Engineering gate: `PASS` / `PARTIAL_PASS` / `FAIL`
- Learning verification: `PASS` / `PENDING` / `FAIL`
- Final human acceptance: `ACCEPTED` / `CONDITIONAL` / `PENDING` / `REJECTED`

## Gate matrix

| Gate | Requirement | Evidence | Result | Limitation or follow-up |
|---|---|---|---|---|
| | | | | |

## Admission

### Admitted

List each admitted artifact, backend or configuration and its exact scope.

### Not admitted

List rejected, unsupported, excluded and untested candidates separately.

### Active configuration

Identify the only current configuration and explicitly mark historical configurations as non-deployable.

## Unresolved work and waivers

- Unresolved problems:
- Problems closed without root cause:
- Accepted waivers or ADRs:
- Risks carried forward:
- Reopening conditions:

## Scope boundary

- What this phase proves:
- What this phase does not prove:
- Safety and physical-system boundary:

## Next-phase decision

- Next phase entry: `ALLOWED` / `ALLOWED_WITH_WAIVER` / `BLOCKED`
- Permitted scope:
- Prohibited scope:
- Entry conditions:
- Required first protocol:

## Independent verification

- [ ] The operator can explain the admission decision.
- [ ] Critical files, interfaces and evidence can be identified.
- [ ] The path can be reproduced or independently recomputed.
- [ ] Debugging boundaries and remaining uncertainty can be explained.
- [ ] Offline qualification is not confused with physical-system safety.

## Decision

Record the human decision and reasoning. Experimental completion, gate result, waiver and learning acceptance must remain separate states.

## Notion projection

- Sync requirement: `REQUIRED` / `NOT_REQUIRED`
- Sync state: `PENDING` / `SYNCED` / `STALE` / `FAILED` / `BLOCKED`
- Notion page:
- Source revision:
- Registry sync ID:

The projection is complete only after read-back verification and local registry update. Sync state
does not change the engineering or acceptance decision. Do not copy real Notion page IDs or URLs
into the public example registry.
