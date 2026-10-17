# Phase 4 CPU FP32 Stability Execution Readiness Review

Review date: `2026-10-14`

Protocol: `P4-DK2500-CPU-FP32-STABILITY-002`, version `0.2`

Proposed run ID: `phase4_r3_stability_20261014_01`

Result: `READY_FOR_HUMAN_AUTHORIZATION — EXECUTION NOT AUTHORIZED`

Owner: human

## Readiness decision

The frozen Stability implementation, local artificial validation, existing regressions, exact
target deployment and target no-model preflight have passed their respective bounded reviews. One
named Stability attempt may now be presented to the human owner for a separate decision.

This review does not create an authorization file and does not start the Supervisor, Worker, model
read/compile or inference.

## Frozen attempt

- run ID: `phase4_r3_stability_20261014_01`;
- target: `hepintelpc` over strict no-touch SSH;
- target harness:
  `/home/hepintel/physical_ai_os_artifacts/phase4_entry/harness_stability_0_2_20261014`;
- target model package:
  `/home/hepintel/physical_ai_os_artifacts/phase4_entry/policy_package_v2_9`;
- evidence root: `/home/hepintel/physical_ai_os_artifacts/phase4_entry/evidence`;
- device / precision / hint: explicit `CPU` / `f32` / `LATENCY`;
- pre-observation: 30 seconds, seven samples at five-second spacing;
- entry gates: average CPU busy `<=10%`, no throttle-field increase, package `<=60 C`, maximum
  sensor `<=65 C`;
- initial correctness: one call;
- warmup: ten calls;
- formal duration: at least 1800 seconds;
- correctness: every inference, frozen `rtol=1e-4`, `atol=1e-5`;
- progress watchdog: 15 seconds;
- monitor interval: five seconds;
- thermal hard stop: any readable sensor `>=100 C`;
- overall timeout: 2100 seconds;
- attempts: one; automatic retry/reconnect prohibited.

## Evidence entering readiness

1. `PHASE4_STABILITY_DESIGN_PROPOSAL_20261014.md`: human accepted the bounded design and claim
   limits.
2. `PHASE4_STABILITY_PROTOCOL_V0_2_20261014.md`: qualification rules frozen before target
   execution.
3. `PHASE4_STABILITY_IMPLEMENTATION_REVIEW_20261014.md`: local external-control implementation
   passed nine artificial cases and the existing `10/10` regression suite without changing the
   Worker inference path.
4. `PHASE4_STABILITY_TARGET_PREFLIGHT_REVIEW_20261014.md`: exact deployment hashes, target/runtime,
   artifacts and required monitor interfaces passed without model access or inference.
5. `evidence/phase4_0_harness/no_model_preflight_stability_20261014_01.json`: raw preflight
   evidence, SHA-256
   `beeddcc10e4daa480026f5ca5ea59360fad88d3dafcbabdea435c6653cd95355`.

## Hash-bound authorization values

Any one-attempt authorization must contain exactly:

| Field | Value |
|---|---|
| `protocol_id` | `P4-DK2500-CPU-FP32-001` |
| `protocol_snapshot` | `fb18053` |
| `stage_protocol_id` | `P4-DK2500-CPU-FP32-STABILITY-002` |
| `stage_protocol_version` | `0.2` |
| `run_id` | `phase4_r3_stability_20261014_01` |
| `stage` | `stability` |
| `status` | `AUTHORIZED_FOR_ONE_ATTEMPT` |
| `automatic_retry` | `false` |
| `target_hostname` | `hepintelpc` |
| `package_dir` | `/home/hepintel/physical_ai_os_artifacts/phase4_entry/policy_package_v2_9` |
| `pre_observation_seconds` | `30` |
| `duration_seconds` | `1800` |
| `watchdog_seconds` | `15` |
| `telemetry_seconds` | `5` |
| `overall_timeout_seconds` | `2100` |
| `stage_protocol_sha256` | `0fd26e7056e19877291ff2bbac3ff23426401ef7cee9c0caec06d2164beba66f` |
| `supervisor_sha256` | `3079a134aaba9e279889e10f72afd5b9ae92cead4504f0c24806180cb33b536b` |
| `worker_sha256` | `8795710589a5474387fc181162e4fc6fe6e8614ff5ce1042ef5f834cd403f47e` |
| `monitor_sha256` | `3f7ee1e22c3530cc3ff44fbb4f0e0d8cb4ede1450365db39a892059e5867ca26` |
| `thermal_sampler_sha256` | `923a82f754a137a58b973c39a915fd9a76fd5a30d3d8522299ece543e6d2c0fe` |
| `config_sha256` | `700cb888b3571a2cc4199939140692192dd4eaa18ca8f7966ee1aa3f54655c89` |
| `prepost_sha256` | `d7b702f3d7bb5d4ee78268278fb5e685a743c71716c90108098d60882e44a2eb` |

The authorization file itself must be created only after the human decision, copied into the target
`authorizations` directory and preserved by hash in the Supervisor result.

## Temperature readiness risk

The no-model preflight observed a maximum sensor value of `76 C`. That passed the bounded preflight
but would not satisfy the Stability entry requirement if it remained present at the final
pre-observation sample.

The entry decision must not be guessed from this earlier instantaneous value. The authorized
Supervisor must perform the frozen 30-second pre-observation before Worker creation. A rejection:

- creates no Worker;
- performs no model read, compile or inference;
- preserves the seven samples and decision;
- consumes the named attempt;
- permits no automatic retry.

This behavior is intentional: entry comparability is part of the qualification protocol, not a
reason to adjust thresholds after seeing the target.

## Execution command after authorization

The exact target-side command is:

```bash
cd /home/hepintel/physical_ai_os_artifacts/phase4_entry/harness_stability_0_2_20261014
/usr/bin/python3 phase4_cpu_supervisor.py \
  --run-id phase4_r3_stability_20261014_01 \
  --stage stability \
  --package-dir /home/hepintel/physical_ai_os_artifacts/phase4_entry/policy_package_v2_9 \
  --evidence-root /home/hepintel/physical_ai_os_artifacts/phase4_entry/evidence \
  --authorization-file /home/hepintel/physical_ai_os_artifacts/phase4_entry/authorizations/phase4_r3_stability_20261014_01.json
```

It must be invoked once only after verifying that the result directory does not already exist and
the copied authorization hash/content match the reviewed values.

## Claim boundary

Even a passing result can qualify only the frozen-input offline repeated-inference path on this
recorded DK-2500 software/hardware identity. It cannot establish changing-input behavior, complete
preprocess/control/postprocess behavior, robot task success, real-time control, E-stop behavior,
collision safety, another target or another backend.

## Human decision required

Before authorization, the human owner must explicitly accept both:

1. the attempt may stop before Worker/model access if the 30-second entry gate fails, and that still
   consumes the run ID;
2. the run may not be retried automatically regardless of precondition rejection, failure or
   incomplete evidence.

Only then may a run-specific authorization be created and transferred.

