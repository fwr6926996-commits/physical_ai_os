# Repository to Notion Sync

Policy version: `0.2`

Status: `TRIAL`

Effective date: `2026-10-17`

## Purpose

Project engineering truth remains in Git, source files, configuration, raw evidence and reviewed
decision records. Notion is a human-facing projection for navigation, current status and review
handoff. This policy makes that projection traceable without allowing Notion to silently redefine
the repository state.

## Authority boundary

- Repository records are authoritative for implementation, evidence, admission and acceptance.
- Notion may summarize reviewed repository facts, but it must link the exact source records and
  preserve their scope limits.
- A Notion edit never changes an engineering gate, authorizes an experiment or accepts a phase.
- Raw evidence stays in the repository or its content-addressed artifact store; Notion receives a
  bounded summary rather than a second copy.
- Credentials, access tokens, connector secrets, real page IDs and real page URLs must not be
  committed to the public repository.

## Local registry and public template

The real mapping is local configuration:

`docs/process/notion_sync_registry.json`

This path is ignored by Git. It may contain real Notion page IDs, URLs, source hashes and sync
history. Preserve and back it up as local project state; do not replace it with the public example.

The tracked public template is:

`docs/process/notion_sync_registry.example.json`

For a new local checkout, copy the example to the ignored local path and replace only the
placeholders needed for that workspace. Never put real mappings into the example file.

## Required sync triggers

Create or refresh a Notion projection after any of these repository events:

1. a stage review records a human decision or changes the next authorized gate;
2. a phase acceptance, partial pass, rejection or waiver is recorded;
3. a diagnosis changes an execution block, risk classification or reopening condition;
4. an ADR changes the active route or phase-entry conditions; or
5. a previously synchronized source changes materially.

Routine implementation commits, raw evidence additions and exploratory notes do not require a
Notion update unless they change one of the states above.

## Projection contract

Every synchronized status page must state:

- current phase and bounded status;
- the decision or gate that changed;
- strongest supported conclusion;
- important conclusion that is not supported;
- open risks or blockers;
- next permitted action and prohibited actions;
- exact source paths, source revision and sync timestamp; and
- a stable Notion page ID recorded only in the local `notion_sync_registry.json`.

Use an existing phase page when it still represents the same review object. Create a new child page
when the event is a new stage decision, diagnosis or phase closure. Do not overwrite a historical
entry review to make it appear as though it originally contained a later decision.

## Sync state

The local registry uses these states:

- `PENDING`: an eligible reviewed source has not been projected;
- `SYNCED`: the registered source hashes match the content used for the verified Notion page;
- `STALE`: one or more registered source files changed after synchronization;
- `FAILED`: a write or read-back verification failed;
- `BLOCKED`: the destination or connector is unavailable and requires human action;
- `NOT_REQUIRED`: the event does not meet a required trigger.

`SYNCED` describes projection freshness only. It is not an engineering pass or human acceptance.

## Execution procedure

1. Confirm that the source is a review, decision, acceptance or diagnosis record and identify its
   exact Git/worktree state.
2. Fetch the destination page before editing it. Preserve historical content and child pages.
3. Create or update the smallest complete Notion projection using the projection contract above.
4. Fetch the written page and verify its title, status, boundaries, source links and next gate.
5. Record the page ID, URL, source hashes, source revision and timestamp in the ignored local
   `docs/process/notion_sync_registry.json`.
6. Run `python3 scripts/check_notion_sync.py`. A non-zero result means the local projection cannot
   be represented as current.

Use `python3 scripts/check_notion_sync.py --registry
docs/process/notion_sync_registry.example.json` only to validate the public template structure.

If a synced source later changes, the checker reports `STALE`. Review the semantic change before
updating Notion; do not blindly copy a diff. After verified write-back, replace the registered
hashes and timestamp in the local registry without copying its real mappings into Git.

## Initial routing

| Repository record | Notion destination | Operation |
|---|---|---|
| Stage review or bounded diagnosis | `P1 / L2 / Phase Execution & Stage Reviews` | Create a dated child page |
| Phase acceptance or closure | `P1 / L2 / Phase Execution & Stage Reviews` | Create or update the phase closure page |
| Current main-line status | `Runtime / Current Priorities` | Update only the affected project paragraph |
| Research question created by a review | Existing Research route | Create only after the question and owner are concrete |

## Review and ownership

Codex may prepare, write, verify and register a synchronization when the underlying engineering
decision already exists. The human owner retains approval of architecture, risk, admission,
waivers, experiment authorization and final phase acceptance.

## Changelog

### 0.2 2026-10-17

Kept real Notion page mappings in an ignored local registry and added a redacted tracked example for
the public repository. The authority and sync semantics are unchanged.

### 0.1 2026-10-12

Established the repository-to-Notion projection contract and hash-based drift check.
