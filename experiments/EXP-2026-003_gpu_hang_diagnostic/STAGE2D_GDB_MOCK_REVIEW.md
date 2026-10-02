# EXP-2026-003 Stage 2D GDB Mock Review

## Verdict

`PASS_GDB_STACK_AND_BOUNDED_DETACH_MOCK`

No OpenVINO or GPU was initialized. The target was a Python process calling an unstripped native busy-loop library compiled only for this mock.

## Controlled permission result

- Host Yama policy remained `ptrace_scope=1`.
- Unauthorized GDB attach was rejected.
- The authorized target called `PR_SET_PTRACER` with its supervisor PID only.
- GDB, launched as a supervisor descendant, attached successfully.
- No global ptrace policy or capability was changed.

## Stack quality result

GDB completed in `0.133822 s` and recovered the expected chain:

```text
mock_native_layer_three
mock_native_layer_two
mock_native_layer_one
mock_infer_busy_loop
libffi
_ctypes
Python evaluation frames
```

All four expected native mock symbols and their source lines were present.

This proves that the host can unwind a Python → ctypes → native call chain when symbols and frame information are available. It does not predict the symbol detail available from stripped OpenVINO and Intel GPU libraries.

## Detach and recovery result

### Normal GDB completion

- GDB detached normally.
- Target remained alive and `R (running)`.
- Original recovery completed with SIGTERM and exit code `-15`.

### Forced helper timeout

- GDB attached and was intentionally held inside its own Python command.
- The parent enforced a 1-second timeout and terminated GDB.
- The target remained alive and returned to `R (running)` after tracer death.
- Original recovery completed with SIGTERM and exit code `-15`.

## Frozen mock artifact hashes

- ptrace permission probe: `197c172a954981486d9ca72f52543f69d51ca8674010e78c15b3a693c42e3dd8`
- native mock source: `9592343d2ee9a1c99804f1fed88eb73ba4272f72d668c137a3e92483e288985c`
- GDB stack mock: `38d60722c1856364e56570327d0a603f0097917689d083b274272f65acaf2df5`

## Evidence boundary

- A backtrace shows where threads were observed when GDB stopped them.
- It does not prove why the observed frame failed to make progress.
- A top frame inside a library does not by itself prove that library caused the original failure.
- A clean mock with unstripped symbols does not guarantee a readable production stack.
- Attaching GDB stops the target briefly and therefore changes recovery timing and process scheduling.

## Decision

The bounded GDB observation mechanism is feasible enough to draft, but not yet execute, a Stage 2D GPU protocol. Real execution requires a reviewed worker authorization diff, bounded helper implementation, no-GPU integration mock, frozen hashes, and separate human approval.
