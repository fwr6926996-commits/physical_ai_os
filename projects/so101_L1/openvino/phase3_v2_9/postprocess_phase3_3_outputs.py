"""Apply the saved LeRobot action postprocessor to paired FP32/INT8 outputs."""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

import numpy as np
import torch
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors


CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    values = np.load(args.input)
    with contextlib.redirect_stdout(sys.stderr):
        policy = ACTPolicy.from_pretrained(CHECKPOINT).eval()
        _, postprocessor = make_pre_post_processors(
            policy_cfg=policy.config,
            pretrained_path=str(CHECKPOINT),
            preprocessor_overrides={"device_processor": {"device": "cpu"}},
        )
    with torch.inference_mode():
        fp32 = postprocessor(torch.from_numpy(values["fp32"]))
        int8 = postprocessor(torch.from_numpy(values["int8"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, fp32=fp32.cpu().numpy(), int8=int8.cpu().numpy())


if __name__ == "__main__":
    main()
