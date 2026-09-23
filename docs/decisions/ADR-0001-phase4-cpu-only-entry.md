# ADR 0001 Phase 4 CPU Only Entry

Status: `ACCEPTED_FOR_BOUNDED_PHASE4_ENTRY`

Decision date: `2026-09-23`

Decision owner: human

## Context

The L1 V2.9 Phase 3 gate expected stable Intel CPU and iGPU pre-deployment evidence. CPU FP32 passed correctness and the human-selected 30-minute stability gate. GPU.0 FP32 passed frozen-input correctness but failed repeated monolithic and isolated-worker stability runs. NPU and reduced-precision candidates were not admitted.

The Phase 3 engineering result is therefore a partial pass, not a full Gate P pass. Repeating the same GPU stability run is prohibited by the existing two-consecutive-failure stop rule and would provide little additional information.

## Decision

Allow Phase 4 planning and a bounded CPU FP32 qualification path on DK-2500 despite the unmet Phase 3 iGPU stability requirement.

This is a waiver, not a conversion of Phase 3 into a full pass. It permits Phase 4 execution only after:

1. DK-2500 hardware and software truth is captured and reviewed;
2. the same V2.9 policy package hashes are available or any change is explicitly reviewed;
3. a Phase 4 qualification protocol is frozen under Engineering Workflow 0.1;
4. explicit CPU identity, FP32 precision and correctness gates are configured;
5. recovery and stop behavior is bounded;
6. no robot motion or safety claim is included.

## Permitted scope

- DK-2500 inventory and environment capture;
- explicit CPU FP32 compile, load and correctness;
- CPU-only latency, RAM, temperature, power/thermal proxy and 30–60 minute stability qualification;
- preservation of negative or performance-insufficient results.

## Prohibited scope

- treating Phase 3 as a full pass;
- deploying GPU.0, NPU, AUTO, HETERO, FP16 or INT8 based on Phase 3 evidence;
- repeating Phase 3 GPU stability Round 3;
- assuming the 255H CPU result proves DK-2500 compatibility or performance;
- robot motion, task-success or physical-safety claims;
- changing kernel, driver, firmware or system power configuration without a separate reviewed plan.

## Carried risks

- Phase 4 initially has no admitted accelerator path.
- CPU performance on DK-2500 may be insufficient even if correctness and stability pass.
- GPU.0 root cause remains open and could reflect a runtime, plugin, driver, scheduling or harness issue relevant to another platform.
- The CPU-only path may require a later model-compression or accelerator decision.

## Reopening conditions

GPU or reduced-precision work requires a new architecture decision and protocol. Reopen GPU diagnostics only when accelerator capability is strategically required and the protocol captures inference enter/return events, native stacks, kernel/runtime diagnostics, device telemetry and single-variable A/B evidence.

Reopen INT8 only after task-relevant physical-unit metrics and acceptance thresholds are frozen.

## Consequences

Phase 4 may advance without open-ended GPU debugging blocking the main line. A CPU result that is correct but too slow is an acceptable negative engineering result; it must not be rewritten as deployment success.
