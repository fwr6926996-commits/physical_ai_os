import torch

from lerobot.datasets.lerobot_dataset import LeRobotDataset


repo_id = "lucasly527/so101_pick_place_cube_v1_20260803_014054"
root = "/data/datasets/so101_pick_place_cube_v1_20260803_014054"


dataset = LeRobotDataset(
    repo_id=repo_id,
    root=root,
)

sample = dataset[0]


print("=== SAMPLE KEYS ===")

for key, value in sample.items():

    if isinstance(value, torch.Tensor):
        print(
            key,
            "shape =",
            tuple(value.shape),
            "dtype =",
            value.dtype,
        )

    else:
        print(
            key,
            "type =",
            type(value).__name__,
        )
