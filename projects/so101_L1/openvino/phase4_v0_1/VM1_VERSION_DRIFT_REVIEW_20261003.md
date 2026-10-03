# VM1 Version Drift Review — DK-2500 Entry

Review ID: `P4-VM1-20261003-01`

Date: `2026-10-03`

Status: `MATERIAL_DRIFT_FOUND — DECISION REQUIRED BEFORE PROTOCOL FREEZE`

## Compared baselines

- Historical Phase 3 source: ThinkBook 255H evidence and
  `../phase3_v2_9/active_runtime_config.yaml`.
- Phase 4 target source:
  `evidence/phase4_0_truth/dk2500_truth_20261003.json`.

The Phase 3 baseline is historical comparison evidence. It is not a DK-2500 pass threshold and its
backend admission does not transfer to the new target.

## Drift matrix

| Dimension | Phase 3 — ThinkBook 255H | Phase 4 target — DK-2500 | Assessment |
|---|---|---|---|
| CPU | Core Ultra 7 255H | Core Ultra 5 225U | Expected target-platform change |
| Memory | 32 GiB observed | approximately 8 GB OS-visible | Material capacity change |
| OS/kernel | Linux `7.0.0-31-generic` in final GPU diagnostic identity | Ubuntu 24.04.4, `6.17.0-35-generic` | Material platform drift |
| OpenVINO | `2026.3.1-22476-759c5a6ab8c-releases/2026/3` | `2026.2.1-21919-ede283a88e3-releases/2026/2` | Material runtime/plugin drift |
| Available devices | CPU, GPU.0, GPU.1, NPU | CPU, NPU | Capability drift; GPU userspace runtime absent |
| CPU identity | Intel Core Ultra 7 255H | Intel Core Ultra 5 225U | Requires a new exact identity guard |
| Policy Package | Frozen V2.9 hashes | Not yet copied or verified | Entry blocker |

## What the drift means

OpenVINO 2026.2.1 on the DK-2500 is a real target fact, not automatically an error. However, using
it without an explicit decision would change both hardware and runtime relative to Phase 3. That
would weaken attribution of any output or latency difference.

Conversely, upgrading immediately to 2026.3.1 would mutate the vendor-installed target baseline
before it has been preserved and could introduce package or driver compatibility changes. The
presence of newer packages elsewhere is not sufficient reason to upgrade.

## Decision options

### Option A — preserve and qualify the observed 2026.2.1 stack

- Benefit: evaluates the actual current DK-2500 environment and avoids an entry-time system change.
- Cost: hardware and runtime both differ from Phase 3, so comparison is platform-level rather than
  a controlled hardware-only comparison.
- Requirement: verify the frozen IR and reference outputs are compatible and record the runtime
  drift as part of the admitted configuration.

### Option B — align DK-2500 to OpenVINO 2026.3.1 before qualification

- Benefit: improves direct comparability with Phase 3 and narrows the runtime variable.
- Cost: requires a separately reviewed system-package change, rollback plan and renewed software
  truth capture; the target may have platform-specific package constraints.
- Requirement: research package provenance and compatibility before any installation or removal.

## Recommendation

Preserve the current 2026.2.1 target baseline while entry preparation continues. Do not upgrade or
install GPU compute packages yet. First copy and hash-verify the Phase 3 Policy Package, then perform
a bounded CPU-only compatibility preflight design review. Select Option A or B through an explicit
human-owned decision before the qualification protocol becomes `FROZEN_APPROVED`.

This recommendation does not authorize model execution. It preserves rollback-free evidence while
keeping both decisions open.

## GPU and NPU treatment

- GPU is not visible because the current Intel GPU userspace compute runtime boundary is incomplete.
- NPU is visible but remains outside the CPU-only Phase 4 qualification scope.
- Neither result changes Phase 3 admission or grants a Phase 4 accelerator path.
- Any GPU driver installation or NPU inference requires a separate decision and evidence contract.

## VM1 result

- Drift detected: `YES`.
- Architecture reset required: `NO`.
- Protocol freeze blocked: `YES`, until the OpenVINO baseline option is selected and Policy Package
  identity is verified.
- Phase 4 execution authorized: `NO`.
