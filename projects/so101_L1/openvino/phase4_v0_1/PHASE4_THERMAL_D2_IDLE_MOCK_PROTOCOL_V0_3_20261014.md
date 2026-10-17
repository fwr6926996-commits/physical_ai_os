# Phase 4 Thermal D2-IDLE Implementation and Mock Protocol v0.3

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D2-IDLE-MOCK-001`
- Protocol version: `0.3`
- Date frozen: `2026-10-14`
- Classification: `EXPLORATORY — NO-TARGET IMPLEMENTATION VALIDATION`
- Base protocol: version `0.1`, frozen SHA-256
  `143599c2f6d3167be20429810a1f3693af90cfd697fa5bc42b473701b406734c`
- Stream amendment: version `0.2`, frozen SHA-256
  `b7e1cd2180245fdabe9fbd8f0b942b59d9b5512a69831515f33e778eb129d92a`
- Round 2 review: `PHASE4_THERMAL_D2_IDLE_MOCK_ROUND2_REVIEW_20261014.md`
- Status: `FROZEN FOR LOCAL IMPLEMENTATION AND ARTIFICIAL-INPUT MOCK ROUND 3 ONLY`
- Target authorization: `NONE`

## Retained requirements

All constants, formulas, protected boundaries, classifier cases and complete-line stream/watchdog
requirements from versions `0.1` and `0.2` remain unchanged.

## Added partial-stream requirements

The Supervisor must:

- read child stdout/stderr as available bytes rather than blocking on text `readline()`;
- count progress only when at least one complete newline-terminated stdout record arrives;
- keep the watchdog active when only a partial record arrives;
- preserve all received raw bytes, including a trailing partial record;
- record JSON decode or incomplete-tail errors without discarding valid earlier records;
- create the evidence directory and raw artifacts before returning a parse-related failure;
- classify timeout after partial progress as `SUPERVISOR_OR_TRANSPORT_FAILURE`;
- terminate the stalled child with the existing bounded recovery and never retry.

## Added artificial-input case

A local child must emit at least one complete identity record, then emit only part of the next JSON
record without a newline and stall beyond the reduced artificial watchdog. Round 3 must prove:

- the Supervisor watchdog still fires;
- recovery is `SIGTERM` unless escalation is actually needed;
- the raw partial stream is nonempty and preserved;
- the incomplete-tail parse error is recorded;
- the result is `MOCK_SUPERVISOR_OR_TRANSPORT_FAILURE_REVIEW_REQUIRED`;
- target access and execution authorization remain false.

## Round 3 evidence contract

Designated evidence:
`evidence/phase4_0_harness/thermal_d2_idle_mock_validation_20261014_03.json`

Round 3 must preserve `_01` and `_02`, record exact version `0.3` hashes, retain all earlier cases,
add the partial-line case and make no target connection.

## Pre-run review

- [x] Round 2 evidence and limitation are preserved.
- [x] Partial-line behavior is specified before code validation.
- [x] Evidence preservation is required even for invalid or incomplete JSONL.
- [x] Target execution remains hard-disabled.
- [x] `_03` is a unique non-overwriting evidence path.

## Deviations

None. Round 3 has not executed.
