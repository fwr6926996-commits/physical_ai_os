# Phase 3.3 INT8 PTQ Design Proposal

Status: `HISTORICAL_PROTOCOL__EXECUTED_AND_CLOSED_NEGATIVE_2026-09-15`

The human approved the 300-frame calibration and non-overlapping 100-frame validation design. Quantization and fidelity characterization were executed. The current basic mixed-PTQ candidate failed the fidelity gate and was closed as reproducible negative evidence without a qualified latency ranking. See `evidence/phase3_3_int8/int8_feasibility_closure_20260915.json`.

## Frozen local facts

- Dataset: `/data/datasets/so101_pick_place_cube_v1_20260803_014054`
- Dataset scope: 50 episodes, 37,009 frames, one task, 30 FPS, train split only
- Source model: `policy_package_v2_9/act_fp32.xml`
- NNCF: 3.3.0
- NNCF basic PTQ default subset size: 300
- Model contract: state `[1,6]`, wrist image `[1,3,480,640]`, normalized action chunk `[1,100,6]`

## Proposed sample policy

### Calibration: 300 frames

- Six deterministic, evenly distributed temporal positions from every episode.
- Use all 50 episodes: `50 x 6 = 300`.
- Apply the same saved LeRobot preprocessing as the FP32 reference path.
- Save the exact episode/frame/index list and its SHA-256 before quantization.
- Frozen temporal fractions per episode: 0.10, 0.25, 0.40, 0.60, 0.75, 0.90.

Purpose: estimate representative activation ranges across the whole recorded task rather than calibrating from one episode or one motion segment.

### Validation: 100 frames

- Two deterministic temporal positions from every episode.
- Use all 50 episodes: `50 x 2 = 100`.
- Indices must not overlap the calibration list.
- Compare INT8 OpenVINO output against FP32 OpenVINO output on exactly the same processed tensors.
- Frozen temporal fractions per episode: 1/3 and 2/3.

Frozen index-manifest content SHA-256: `869697c9b02514380a50e8252ce667a16afb99652c76b2d30967993cc5545e90`.

Limitation: because the dataset contains one task and no held-out split, this measures in-distribution numerical fidelity, not task generalization.

## Proposed first-experiment gates

1. Dataset/index manifest is deterministic and non-overlapping.
2. NNCF quantization completes and emits a separate INT8 artifact; FP32 artifacts remain unchanged.
3. INT8 model compiles and returns the frozen output shape with finite values.
4. Record, without inventing an admission threshold:
   - normalized full-chunk MAE, RMSE, P95 absolute error and maximum absolute error;
   - per-action-dimension MAE and P95 absolute error;
   - postprocessed action-chunk error in the saved action representation;
   - FP32 and INT8 artifact sizes.
5. Do not produce a qualified latency ranking yet.

## Human-owned admission step

After the first error distribution is visible, define a task-relevant threshold for action deviation. Only an INT8 candidate that passes that frozen threshold may enter the formal CPU/GPU/NPU latency and resource matrix.

If basic PTQ fidelity is unacceptable, preserve it as negative evidence and consider, in order:

1. verify calibration coverage and preprocessing;
2. accuracy-aware PTQ or mixed precision for sensitive operations;
3. QAT only if the project value justifies retraining.

## First Encounter boundary

Codex may prepare the deterministic index manifest, calibration loader, PTQ script and evidence schema. The human reviews the important diff and executes the first quantization command. Repeated PTQ variants may move to ASSIST or DELEGATE after the mechanism is understood.
