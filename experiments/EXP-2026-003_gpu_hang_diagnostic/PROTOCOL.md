# EXP-2026-003 GPU Hang Diagnostic — Stage 0 Protocol

Protocol ID: `EXP-2026-003-STAGE0-MOCK-HARNESS-V1`

Status: `FROZEN_FOR_FIRST_LEARNING_RUN`

Classification: `EXPLORATORY_LEARNING`

Owner: human

Implementation assistant: Codex

## Question and decision

- Question: Can the supervisor distinguish normal completion, a worker exception and loss of progress inside a bounded work call?
- Decision supported: Whether this parent/worker event model is trustworthy enough to use as the starting point for a later GPU diagnostic protocol.
- Claims not supported: This experiment cannot identify, reproduce or exclude an OpenVINO, Intel GPU plugin, kernel, driver or hardware fault.

## Frozen design

- No OpenVINO import.
- No GPU access.
- The parent supervisor owns evidence writing and timeout recovery.
- The worker emits `worker_ready`, `work_enter`, `work_return`, `heartbeat` and a final event.
- The mock hang occurs after `work_enter` and before `work_return`.
- The watchdog terminates only the exact child process created by the experiment.

## Scenarios

| Scenario | Expected evidence | Harness interpretation |
|---|---|---|
| `normal` | Matching enter/return events, heartbeats, clean completion | Supervisor observes normal progress |
| `hang` | Final `work_enter` without matching `work_return`; heartbeat stops; watchdog terminates child | Loss of progress detected and bounded |
| `exception` | Worker exception is returned as a structured event | Failure is reported without being confused with a hang |

## First learning run

The human runs the `hang` scenario after reviewing the code and predicts the expected evidence before execution.

Frozen parameters:

- duration: 4 seconds
- mock work: 0.1 seconds per iteration
- hang after entering iteration 3
- watchdog: 1 second without a message
- startup timeout: 5 seconds
- maximum attempts: 1 first learning run

## PASS conditions

- The result status is `PASS_HANG_DETECTED_AND_RECOVERED`.
- The last entered iteration is 3.
- The last returned iteration is 2.
- The last completed heartbeat is iteration 2.
- The final event is a watchdog timeout in the work stage.
- The child is recovered with `SIGTERM` or, only if required, `SIGKILL_AFTER_SIGTERM_TIMEOUT`.

## Stop policy

- Do not repeat the first run merely to obtain a preferred result.
- If the observed evidence differs from the frozen prediction, stop and review the harness before any GPU experiment.
- Real GPU execution requires a separate Stage 1 protocol and explicit human approval.

## Evidence contract

Each run writes:

- `events.jsonl`: ordered messages observed by the supervisor;
- `result.json`: configuration, last-good/first-missing boundary, final event and recovery;
- console summary for immediate inspection.

## Safety boundary

This experiment creates and terminates only its own mock child process. It does not change drivers, kernel, firmware, device configuration or repository Phase 3 admission state.
