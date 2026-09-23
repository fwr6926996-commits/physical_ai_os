"""Export the frozen ACT tensor contract from the LeRobot environment.

The output is a PyTorch ExportedProgram, not an OpenVINO model. Keeping this
step in the training environment avoids making the deployment environment
depend on LeRobot's Python implementation.
"""

from pathlib import Path

import torch

from lerobot.policies.act.modeling_act import ACTPolicy


CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")
PACKAGE_DIR = Path(__file__).parent / "policy_package_v1"


class ACTTensorWrapper(torch.nn.Module):
    """Expose ACT as (state, wrist_image) -> normalized action_chunk."""

    def __init__(self, policy: ACTPolicy) -> None:
        super().__init__()
        self.policy = policy

    def forward(self, state: torch.Tensor, wrist_image: torch.Tensor) -> torch.Tensor:
        batch = {
            "observation.state": state,
            "observation.images.wrist": wrist_image,
        }
        return self.policy.predict_action_chunk(batch)


def main() -> None:
    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    state = model_input["observation.state"]
    wrist_image = model_input["observation.images.wrist"]

    policy = ACTPolicy.from_pretrained(CHECKPOINT)
    policy.eval()
    wrapper = ACTTensorWrapper(policy).eval()

    with torch.inference_mode():
        expected = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"]
        actual = wrapper(state, wrist_image)
    torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    exported_program = torch.export.export(wrapper, (state, wrist_image), strict=True)
    output_path = PACKAGE_DIR / "act_tensor_wrapper.pt2"
    torch.export.save(exported_program, output_path)

    print(f"Saved: {output_path}")
    print("inputs:", tuple(state.shape), tuple(wrist_image.shape))
    print("output:", tuple(actual.shape))


if __name__ == "__main__":
    main()
