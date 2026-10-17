# Phase 4 CPU FP32 Stability No-Target Implementation Review

Review date: `2026-10-14`

Protocol: `P4-DK2500-CPU-FP32-STABILITY-002`, version `0.2`

Template basis: `EXPERIMENT_REVIEW.md` version `0.1` (`TRIAL`)

Review status: `PASS — NO-TARGET IMPLEMENTATION ONLY`

Target readiness: `NOT READY — DEPLOYMENT AND NO-MODEL PREFLIGHT PENDING`

Execution status: `NOT AUTHORIZED`

Owner: human

## Decision

The local Stability implementation is sufficiently consistent with the accepted and frozen design
to proceed to a separately authorized **target deployment and no-model preflight**. This review does
not authorize DK-2500 access, file transfer, model access, inference, Stability execution, retry,
deployment admission, real-time or physical-safety claims.

The production Worker and its measured synchronous inference path were not changed. The Stability
changes are confined to the external Supervisor, monitor, configuration, authorization contract,
no-model preflight and artificial validator.

## Implemented controls

- The target hostname is fixed to `hepintelpc` before stage execution.
- A 30-second, seven-sample pre-observation runs before Worker creation or model access.
- Entry checks enforce average aggregate CPU busy `<=10%`, no exact-path throttle-field increase,
  package temperature `<=60 C`, maximum readable sensor `<=65 C`, and valid interfaces/timebase.
- The run-specific authorization must match the protocol identity and hash plus exact Supervisor,
  Worker, monitor, monitor dependency, frozen configuration and pre/post hashes.
- Structured monitor events retain monotonic time, schedule lag, interface-read duration,
  temperatures, exact-path throttle fields, frequencies, CPU state and memory/process state.
- The Supervisor enforces the frozen 15-second progress watchdog, 2100-second overall limit,
  evidence-first bounded recovery and no-retry rule.
- The no-model preflight checks deployed identities, implementation hashes and target interfaces
  without loading or compiling the model and without inference.

## Artificial validation

Evidence:
`evidence/phase4_0_harness/stability_no_target_mock_20261014_02.json`

Result: `PASS_STABILITY_NO_TARGET_MOCK`

Artificial cases passed:

1. valid pre-observation accepted;
2. excessive average CPU busy rejected;
3. throttle-field increment rejected;
4. excessive entry package temperature rejected;
5. excessive entry maximum sensor temperature rejected;
6. interface/read failure classified;
7. counter decrease classified;
8. exact authorization match accepted;
9. authorization mismatch rejected.

The evidence records `target_accessed=false` and `execution_authorized=false`. It therefore proves
only that these local classification rules behaved as designed for artificial inputs. It does not
prove the DK-2500 interfaces are currently readable, that the target starting condition will pass,
or that Stability will pass.

## Regression and static checks

- Existing Phase 4 harness tests: `7/7 PASS`.
- Existing Phase 4 pre/post tests: `3/3 PASS`.
- Combined regression: `10/10 PASS`.
- Modified and new Python files compile with `py_compile`.
- Frozen configuration and authorization template parse as JSON.
- Repository whitespace check passes for the reviewed changes.

The first root-level unittest invocation produced one import error because
`test_phase4_prepost.py` imports `phase4_prepost` from its own directory. Re-running the exact same
tests from `phase4_v0_1` produced `10/10 PASS`; this was a test-launch-path error, not a production
or test-logic failure.

## Frozen local identities

| Artifact | SHA-256 |
|---|---|
| Stability protocol | `0fd26e7056e19877291ff2bbac3ff23426401ef7cee9c0caec06d2164beba66f` |
| Supervisor | `3079a134aaba9e279889e10f72afd5b9ae92cead4504f0c24806180cb33b536b` |
| Worker | `8795710589a5474387fc181162e4fc6fe6e8614ff5ce1042ef5f834cd403f47e` |
| Stability monitor | `3f7ee1e22c3530cc3ff44fbb4f0e0d8cb4ede1450365db39a892059e5867ca26` |
| Monitor dependency | `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe` |
| Frozen configuration | `700cb888b3571a2cc4199939140692192dd4eaa18ca8f7966ee1aa3f54655c89` |
| Pre/post implementation | `d7b702f3d7bb5d4ee78268278fb5e685a743c71716c90108098d60882e44a2eb` |
| No-model preflight | `18677d9338aa9806794cc3b51bf40f6b7f675ba57ca5ca559cc32abe518f0a38` |
| Artificial validator | `03410381c9b91cd49c0fa27f3d5a8fdafd6dbdffbd85b5b4245e1e94bdc05b36` |
| Artificial evidence | `898be592aa0a7ae94790c0469aa5567c9740c8221e4a3b3c0249409eabcd3f00` |

Any change to a hash-bound artifact invalidates these identities and requires another local review
before target deployment or execution.

## Evidence and claim boundaries

This review supports:

- local implementation of the frozen external controls;
- preservation of the existing Worker inference path;
- artificial exercise of the nine listed classification branches;
- readiness to request one bounded deployment/no-model-preflight authorization.

This review does not support:

- current DK-2500 interface or thermal readiness;
- correctness, performance or stability of OpenVINO inference;
- root-cause claims about thermal-throttle counters;
- admission of the Stability stage or CPU backend for physical deployment;
- real-time or robot-safety conclusions.

## Learning review

The human owner previously demonstrated the two meanings needed for this implementation decision:

1. hash binding proves that the executed files are identical to the reviewed files, not that the
   implementation logic is correct;
2. a throttle-count increase below the frozen `100 C` stop remains diagnostic evidence and does
   not automatically fail a run that otherwise satisfies every precommitted Stability gate.

Learning status for the no-target implementation decision: `PASS`.

This does not replace the later evidence-interpretation check after target preflight or Stability.

## Next gate

The next and only proposed action is:

1. separately authorize transfer of the frozen protocol/configuration and required implementation
   files to the existing DK-2500 Phase 4 package directory;
2. run one no-model target preflight;
3. preserve and review its evidence;
4. stop without loading/compiling a model or running inference.

Only a passing target preflight and a subsequent readiness review may lead to a proposed named
Stability run. Stability still requires a new, explicit human authorization and permits no
automatic retry.
