# Phase 4 Thermal D2-IDLE Implementation and Mock Protocol v0.2

## Identity

- Protocol ID: `P4-DK2500-THERMAL-D2-IDLE-MOCK-001`
- Protocol version: `0.2`
- Date frozen: `2026-10-14`
- Classification: `EXPLORATORY — NO-TARGET IMPLEMENTATION VALIDATION`
- Base protocol: `PHASE4_THERMAL_D2_IDLE_MOCK_PROTOCOL_20261014.md` version `0.1`
- Base protocol frozen SHA-256:
  `143599c2f6d3167be20429810a1f3693af90cfd697fa5bc42b473701b406734c`
- Round 1 review: `PHASE4_THERMAL_D2_IDLE_MOCK_ROUND1_REVIEW_20261014.md`
- Status: `FROZEN FOR LOCAL IMPLEMENTATION AND ARTIFICIAL-INPUT MOCK ROUND 2 ONLY`
- Target authorization: `NONE`

## Reason for version change

Round 1 validated the event classifier but did not exercise an actual streamed child process,
progress watchdog or bounded recovery. Version `0.2` retains every formula, constant, protected
boundary, required classifier case and prohibited claim from version `0.1`, and adds the missing
Supervisor control-path requirements before Round 2.

Round 1 evidence remains valid for its narrower classifier claims and must not be overwritten or
reported as if it were generated under version `0.2`.

## Added Supervisor requirements

The local Supervisor must:

- consume newline-delimited events from a child process without waiting for process completion;
- enforce a bounded startup timeout before the first complete line;
- enforce a progress watchdog after the first complete line;
- preserve stdout and stderr received before a timeout;
- terminate the child with `SIGTERM`, then use `SIGKILL` only if it does not exit within five
  seconds;
- emit a local `supervisor_or_transport_failure` classification after timeout;
- contain no retry or reconnect loop;
- continue to hard-disable the SSH/target path.

## Added artificial-input cases

In addition to all version `0.1` cases, Round 2 must validate:

1. a complete 127-sample JSONL sequence streamed through a local child process;
2. a local child that stops producing complete lines after initial progress;
3. progress-watchdog classification as `SUPERVISOR_OR_TRANSPORT_FAILURE`;
4. bounded `SIGTERM` recovery and preservation of partial stdout;
5. no SSH invocation, target access, target authorization or target evidence directory.

The short test watchdog may be reduced only in artificial stream mode. Frozen target candidates
remain `30 seconds` startup and `15 seconds` progress watchdog.

## Round 2 evidence contract

Designated evidence:
`evidence/phase4_0_harness/thermal_d2_idle_mock_validation_20261014_02.json`

The result must record version `0.2`, exact protocol and code hashes, both streaming cases, recovery,
all retained classifier cases, `target_accessed: false` and `execution_authorized: false`.

## Run policy

- exactly one designated Round 2 aggregate validation after implementation review;
- preserve `_01` and write `_02` without overwrite;
- stop if any artificial case fails;
- no target access under any outcome;
- no result authorizes an executable target protocol.

## Pre-run review

- [x] Round 1 evidence and gap are preserved.
- [x] Version change precedes Round 2 execution.
- [x] Added control-path requirements and cases are frozen.
- [x] Target mode remains hard-disabled.
- [x] Round 2 evidence path is unique and non-overwriting.

## Deviations

None. Round 2 has not executed.
