"""Create deterministic PyTorch reference artifacts for Phase 3.1.

This script intentionally does not invoke OpenVINO.  It freezes one real
dataset observation after the same saved LeRobot pre/post-processing used by
the rollout checkpoint, plus the corresponding ACT action chunk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors


REPO_ID = "lucasly527/so101_pick_place_cube_v1_20260803_014054"
DATASET_ROOT = Path("/data/datasets/so101_pick_place_cube_v1_20260803_014054")
CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")
OUTPUT_DIR = Path(__file__).parent / "policy_package_v1"
SAMPLE_INDEX = 0


def tensor_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, torch.Tensor):
        return {"type": type(value).__name__}
    return {
        "type": "tensor",
        "shape": list(value.shape),
        "dtype": str(value.dtype).removeprefix("torch."),
        "device": str(value.device),
    }


def cpu_copy(batch: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.detach().cpu().contiguous() if isinstance(value, torch.Tensor) else value
        for key, value in batch.items()
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset = LeRobotDataset(repo_id=REPO_ID, root=DATASET_ROOT)
    sample = dataset[SAMPLE_INDEX]

    # A dataset item also contains targets and metadata.  Freeze only the two
    # observation fields that ACT consumes during inference.
    raw_observation = {
        "observation.state": sample["observation.state"].clone(),
        "observation.images.wrist": sample["observation.images.wrist"].clone(),
    }

    policy = ACTPolicy.from_pretrained(CHECKPOINT)
    policy.eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(CHECKPOINT),
        # Phase 3 is an Intel-only comparison.  The checkpoint was trained on
        # CUDA, but this frozen reference is deliberately evaluated on CPU so
        # it is portable to the 255H correctness environment.
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )

    with torch.inference_mode():
        processed_batch = preprocessor(dict(raw_observation))
        # Processor pipelines carry generic transition metadata.  ACT's
        # exported graph contract is only the configured tensor features.
        model_input = {
            key: processed_batch[key]
            for key in policy.config.input_features
        }
        normalized_action_chunk = policy.predict_action_chunk(model_input)
        action_chunk = postprocessor(normalized_action_chunk)

    # These are deliberately separate.  OpenVINO will consume model_input,
    # while action_chunk is the end-to-end PyTorch reference after unnormalizing.
    torch.save(cpu_copy(raw_observation), OUTPUT_DIR / "reference_raw_observation.pt")
    torch.save(cpu_copy(model_input), OUTPUT_DIR / "reference_model_input.pt")
    torch.save(cpu_copy({"action_chunk": normalized_action_chunk}), OUTPUT_DIR / "reference_output_normalized.pt")
    torch.save(cpu_copy({"action_chunk": action_chunk}), OUTPUT_DIR / "reference_output_action_chunk.pt")

    checkpoint_files = [
        "config.json",
        "model.safetensors",
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    ]
    manifest = {
        "phase": "Phase 3.1 Policy Package V1 reference",
        "sample_index": SAMPLE_INDEX,
        "dataset": {"repo_id": REPO_ID, "root": str(DATASET_ROOT)},
        "checkpoint": {
            "path": str(CHECKPOINT),
            "sha256": {name: sha256(CHECKPOINT / name) for name in checkpoint_files},
        },
        "policy": {
            "class": type(policy).__name__,
            "runtime_device": str(next(policy.parameters()).device),
            "chunk_size": policy.config.chunk_size,
            "n_action_steps": policy.config.n_action_steps,
            "input_features": list(policy.config.input_features),
            "output_features": list(policy.config.output_features),
        },
        "raw_observation": {key: tensor_summary(value) for key, value in raw_observation.items()},
        "model_input": {key: tensor_summary(value) for key, value in model_input.items()},
        "normalized_action_chunk": tensor_summary(normalized_action_chunk),
        "action_chunk": tensor_summary(action_chunk),
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Saved Policy Package V1 reference artifacts to: {OUTPUT_DIR}")
    print("raw observation:", manifest["raw_observation"])
    print("model input:", manifest["model_input"])
    print("normalized action chunk:", manifest["normalized_action_chunk"])
    print("action chunk:", manifest["action_chunk"])


if __name__ == "__main__":
    main()
