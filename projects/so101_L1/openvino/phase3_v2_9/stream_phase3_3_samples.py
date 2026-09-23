"""LeRobot-environment worker that streams exact preprocessed tensors via pickle."""

from __future__ import annotations

import argparse
import contextlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors


HERE = Path(__file__).resolve().parent
INDEX_MANIFEST = HERE / "evidence" / "phase3_3_int8" / "index_manifest.json"
DATASET_ROOT = Path("/data/datasets/so101_pick_place_cube_v1_20260803_014054")
REPO_ID = "lucasly527/so101_pick_place_cube_v1_20260803_014054"
CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", required=True, choices=("calibration", "validation"))
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test limit; omit for the frozen full subset.")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    manifest = json.loads(INDEX_MANIFEST.read_text(encoding="utf-8"))
    # Dataset and checkpoint loaders may print informational text. Keep stdout
    # exclusively binary so the OpenVINO-side pickle stream cannot be corrupted.
    with contextlib.redirect_stdout(sys.stderr):
        dataset = LeRobotDataset(repo_id=REPO_ID, root=DATASET_ROOT)
        policy = ACTPolicy.from_pretrained(CHECKPOINT).eval()
        preprocessor, _ = make_pre_post_processors(
            policy_cfg=policy.config,
            pretrained_path=str(CHECKPOINT),
            preprocessor_overrides={"device_processor": {"device": "cpu"}},
        )

    output = sys.stdout.buffer
    selected_samples = manifest[args.subset]
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be >= 1")
        selected_samples = selected_samples[: args.limit]
    for selected in selected_samples:
        sample = dataset[selected["dataset_index"]]
        if int(sample["episode_index"]) != selected["episode_index"] or int(sample["frame_index"]) != selected["frame_index"]:
            raise RuntimeError(f"Dataset index contract changed: {selected}")
        raw = {
            "observation.state": sample["observation.state"].clone(),
            "observation.images.wrist": sample["observation.images.wrist"].clone(),
        }
        with torch.inference_mode():
            processed = preprocessor(raw)
        state = np.ascontiguousarray(processed["observation.state"].cpu().numpy(), dtype=np.float32)
        wrist_image = np.ascontiguousarray(processed["observation.images.wrist"].cpu().numpy(), dtype=np.float32)
        if state.shape != (1, 6) or wrist_image.shape != (1, 3, 480, 640):
            raise RuntimeError(f"Preprocessed contract changed: state={state.shape}, wrist={wrist_image.shape}")
        pickle.dump({
            "state": state,
            "wrist_image": wrist_image,
            "episode_index": selected["episode_index"],
            "frame_index": selected["frame_index"],
            "dataset_index": selected["dataset_index"],
        }, output, protocol=5)
        output.flush()


if __name__ == "__main__":
    main()
