# EXP-2026-003 Stage 2D Closure

## Status

`CLOSED AFTER ROUND 1 — MAIN THREAD OBSERVED INSIDE INTEL OPENCL COMPUTE RUNTIME`

## Result

Stage 2D reproduced the intermittent failure in its first bounded attempt. The infer boundary remained stable: `H=12396`, `R=12396`, `E=12397`.

GDB completed an all-thread stack in approximately 1.05 seconds, detached normally, and saved the raw output. The target returned to running state and the original SIGTERM recovery succeeded.

The main thread stack crossed Python, `_pyopenvino`, OpenVINO Runtime, Intel GPU Plugin, and then nine unresolved top frames in Intel OpenCL Compute Runtime `libigdrcl.so`. The remaining 36 threads were observed in futex waits at frame 0.

## Learning

The investigation boundary has progressed as follows:

```text
heartbeat stopped
→ one synchronous infer entered but did not return
→ process remained CPU-active
→ main thread was running, not sleeping at a named kernel wait
→ main thread stack was inside the GPU Plugin → Intel OpenCL Runtime path
→ top nine stopped-time frames were in stripped libigdrcl.so
```

This is meaningful localization, not root-cause proof.

The observed implementation path also corrected an earlier assumption: this event exposed Intel OpenCL Compute Runtime rather than Level Zero as the immediate runtime beneath the OpenVINO GPU Plugin.

## Stop decision

The protocol success condition was met: a consistent `HANG_INFER_ENTERED_NOT_RETURNED` event and a complete, main-thread-identified native stack were obtained together. Stage 2D Rounds 2 and 3 are prohibited.

## Route

Do not immediately rerun GPU or change the driver/runtime.

First route to Research:

1. identify matching source, release metadata and any available debug-symbol package for `intel-opencl-icd 25.18.33578.77-1146~24.04`, Build ID `58ccca242c62c0629c06940ee3d7b8a40b298e35`;
2. determine whether the captured binary can be symbolized without another GPU run;
3. inspect authoritative Intel/OpenVINO release notes and issue trackers for matching hang/high-CPU behavior on this runtime, device and kernel combination;
4. only after that research, decide whether a new bounded experiment should capture shared-library mappings/module offsets, add matched debug symbols, compare one runtime configuration, or stop investigation.

Each future experiment must choose one of those questions, not combine them.

## Unchanged engineering decision

- GPU.0 remains `CLOSED_NOT_ADMITTED`.
- CPU FP32 remains the only admitted backend.
- Phase 3 remains `PARTIAL PASS — CPU FP32 ONLY`.
- Phase 4 remains not started.
