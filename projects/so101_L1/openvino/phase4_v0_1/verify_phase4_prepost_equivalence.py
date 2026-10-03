#!/usr/bin/env python3
"""Verify the portable Phase 4 pre/post transform against frozen LeRobot processors."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors

from phase4_prepost import postprocess_action, preprocess_observation


HERE = Path(__file__).resolve().parent


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def comparison(left: np.ndarray, right: np.ndarray) -> dict[str, float | bool]:
    difference = np.abs(left.astype(np.float32) - right.astype(np.float32))
    return {
        "exact": bool(np.array_equal(left, right)),
        "maximum_abs_difference": float(difference.max()),
        "mean_abs_difference": float(difference.mean()),
    }


def main() -> int:
    args = arguments()
    config = json.loads((HERE / "phase4_frozen_config.json").read_text(encoding="utf-8"))
    raw = torch.load(args.package_dir / "reference_raw_observation.pt", weights_only=False)
    model_input = torch.load(args.package_dir / "reference_model_input.pt", weights_only=False)
    normalized = torch.load(
        args.package_dir / "reference_output_normalized.pt", weights_only=False
    )["action_chunk"]
    expected_action = torch.load(
        args.package_dir / "reference_output_action_chunk.pt", weights_only=False
    )["action_chunk"]

    policy = ACTPolicy.from_pretrained(args.checkpoint).eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(args.checkpoint),
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )
    cloned = {key: value.clone() if isinstance(value, torch.Tensor) else value for key, value in raw.items()}
    lerobot_inputs = preprocessor(cloned)
    lerobot_action = postprocessor(normalized.clone())

    raw_numpy = {
        "observation.state": raw["observation.state"].numpy(),
        "observation.images.wrist": raw["observation.images.wrist"].numpy(),
    }
    portable_inputs = preprocess_observation(raw_numpy, config["prepost"])
    portable_action = postprocess_action(normalized.numpy(), config["prepost"])

    comparisons = {
        "portable_state_vs_lerobot": comparison(
            portable_inputs["state"], lerobot_inputs["observation.state"].numpy()
        ),
        "portable_image_vs_lerobot": comparison(
            portable_inputs["wrist_image"], lerobot_inputs["observation.images.wrist"].numpy()
        ),
        "portable_action_vs_lerobot": comparison(portable_action, lerobot_action.numpy()),
        "portable_state_vs_frozen_reference": comparison(
            portable_inputs["state"], model_input["observation.state"].numpy()
        ),
        "portable_image_vs_frozen_reference": comparison(
            portable_inputs["wrist_image"], model_input["observation.images.wrist"].numpy()
        ),
        "portable_action_vs_frozen_reference": comparison(
            portable_action, expected_action.numpy()
        ),
    }
    passed = all(item["exact"] for item in comparisons.values())
    processor_files = (
        "policy_preprocessor.json",
        "policy_preprocessor_step_3_normalizer_processor.safetensors",
        "policy_postprocessor.json",
        "policy_postprocessor_step_0_unnormalizer_processor.safetensors",
    )
    result = {
        "schema_version": 1,
        "evidence_id": "P4-DK2500-PREPOST-EQUIVALENCE-20261003-01",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_EXACT_PREPOST_EQUIVALENCE" if passed else "FAIL_PREPOST_EQUIVALENCE",
        "scope": "Development-host processor equivalence only; no DK-2500 model inference or qualification.",
        "protocol_id": config["protocol_id"],
        "protocol_snapshot": config["protocol_snapshot"],
        "comparisons": comparisons,
        "source_processor_sha256": {
            name: sha256(args.checkpoint / name) for name in processor_files
        },
        "portable_implementation_sha256": sha256(HERE / "phase4_prepost.py"),
        "config_sha256": sha256(HERE / "phase4_frozen_config.json"),
        "interpretation_limits": [
            "Exact equality validates the portable transform for the frozen reference tensors and processor state only.",
            "It does not qualify DK-2500 inference, latency, stability, real-time behavior or robot safety.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
