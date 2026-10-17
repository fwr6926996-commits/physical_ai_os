# Phase 4 Thermal D2-IDLE Mock Round 2 Review

Protocol: `P4-DK2500-THERMAL-D2-IDLE-MOCK-001` version `0.2`

Evidence: `evidence/phase4_0_harness/thermal_d2_idle_mock_validation_20261014_02.json`

Result: `PARTIAL PASS — COMPLETE-LINE STREAM AND WATCHDOG PASSED, PARTIAL-LINE SAFETY OPEN`

Target access: `NONE`

## Passed evidence

- all version `0.1` classifier and guard cases remained passing;
- a complete 127-sample child stream completed with no timeout or recovery;
- a child that stopped after initial complete-line progress triggered
  `PROGRESS_WATCHDOG_TIMEOUT`;
- the Supervisor recovered that child with `SIGTERM`, classified the partial run as
  `SUPERVISOR_OR_TRANSPORT_FAILURE`, and did not retry;
- target access and execution authorization remained false.

## Review gap

The stream reader used text `readline()`. If a child writes only part of a JSON line and remains
alive, `readline()` may wait for the missing newline inside the read call, preventing the outer
watchdog loop from regaining control. In addition, a JSON parse error occurred before creation of
the evidence directory, so a partial or damaged stream was not guaranteed to be preserved.

Round 2 therefore validates complete-line streaming and no-message recovery, but not partial-line
watchdog safety or raw damaged-stream preservation.

## Disposition

- preserve `_02` with its narrower claims;
- create protocol version `0.3` before changing the stream reader and validation matrix;
- use selector-driven byte reads that never wait for a newline;
- treat only complete newline-terminated records as progress events;
- preserve raw partial bytes and parse errors before classification;
- add one artificial partial-line stall case and write `_03` without overwrite;
- keep target execution hard-disabled.

This review authorizes no target access or D2-IDLE execution.
