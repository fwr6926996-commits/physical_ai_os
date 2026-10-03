# Phase 4 Round 1 Correctness Review

Review ID: `P4-DK2500-R1-CORRECTNESS-REVIEW-20261003-01`

Run ID: `phase4_r1_correctness_20261003_01`

Frozen protocol snapshot: `fb18053`

Authorization commit: `ecfb32e`

Decision: `PASS — CORRECTNESS STAGE ONLY`

## Decision boundary

The frozen V2.9 policy package compiled on the explicitly selected DK-2500 CPU FP32 path and
matched the frozen reference output for this one authorized correctness attempt. This closes only
the Round 1 compile/load and frozen-input correctness gate.

It does not authorize or qualify the short measurement, 30-minute stability, real-time control,
robot task behavior, collision safety, E-stop behavior, GPU/NPU execution or another software and
hardware identity.

## Verified evidence

- The one-attempt authorization matched protocol `P4-DK2500-CPU-FP32-001`, snapshot `fb18053`,
  the run ID and the `correctness` stage. Automatic retry was false.
- Runtime identity matched OpenVINO
  `2026.2.1-21919-ede283a88e3-releases/2026/2` and
  `Intel(R) Core(TM) Ultra 5 225U`; the selected runtime device was explicit `CPU`.
- Model XML/BIN and reference input/output SHA-256 values matched the frozen configuration and the
  source Policy Package.
- The Worker enforces input shapes `state [1,6]` and `wrist_image [1,3,480,640]`, compiles with
  explicit `CPU`, FP32 inference precision and `LATENCY`, and rejects output shape or dtype drift.
- Both the correctness inference and the single measurement inference returned finite, correct
  FP32 output. Their latencies were `95.601567 ms` and `92.493105 ms`.
- Independently inspected raw evidence reports maximum absolute error
  `2.86102294921875e-06`, below the frozen `rtol=1e-4`, `atol=1e-5` comparison gate.
- Worker exit code was `0`; supervisor recovery, watchdog diagnosis and stderr were absent.
- The supervisor classified the run `STAGE_PASS_REVIEW_PENDING`; this review converts that pending
  status to `PASS_CORRECTNESS_ONLY`.

The complete evidence and the machine-readable independent review are under
`evidence/phase4_1_correctness/phase4_r1_correctness_20261003_01/`.

## Diagnostic observation requiring follow-up

Throttle counters increased during the approximately 2.1-second supervised stage. The single
telemetry row recorded `45°C` package and `46°C` maximum sensor temperature near the beginning of
the run. A separate two-second idle observation after the run showed zero counter increments.

This is not a correctness failure under the frozen protocol, and the evidence does not prove
overheating or identify a cause. However, the five-second telemetry interval was longer than this
stage, so the run does not characterize the thermal/frequency trajectory. Before a short-stage
authorization decision, the short harness must provide sufficiently dense telemetry and preserve
the counter deltas for review. Any performance or thermal conclusion remains open.

## Next gate

The `short` stage remains blocked. Before it can be presented for separate human authorization:

1. implement the frozen segmented preprocess/inference/postprocess measurement boundary;
2. add and mock-test telemetry coverage appropriate to the short stage duration;
3. independently review the implementation and the throttle-counter observation;
4. freeze a new run ID and create a separate one-attempt authorization only after human approval.

The `stability` stage remains blocked behind a passed and reviewed short stage.
