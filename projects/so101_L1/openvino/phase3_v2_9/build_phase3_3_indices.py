"""Freeze deterministic, non-overlapping PTQ calibration and validation indices."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lerobot.datasets.lerobot_dataset import LeRobotDataset


DATASET_ROOT = Path("/data/datasets/so101_pick_place_cube_v1_20260803_014054")
REPO_ID = "lucasly527/so101_pick_place_cube_v1_20260803_014054"
OUTPUT = Path(__file__).resolve().parent / "evidence" / "phase3_3_int8" / "index_manifest.json"
CALIBRATION_FRACTIONS = (0.10, 0.25, 0.40, 0.60, 0.75, 0.90)
VALIDATION_FRACTIONS = (1 / 3, 2 / 3)


def sample_entry(episode: dict, fraction: float) -> dict:
    length = int(episode["length"])
    frame_index = round(fraction * (length - 1))
    return {
        "episode_index": int(episode["episode_index"]),
        "frame_index": frame_index,
        "dataset_index": int(episode["dataset_from_index"]) + frame_index,
        "target_fraction": fraction,
    }


def main() -> None:
    dataset = LeRobotDataset(repo_id=REPO_ID, root=DATASET_ROOT)
    calibration = []
    validation = []
    episode_bounds = []
    for episode_index in range(dataset.num_episodes):
        episode = dataset.meta.episodes[episode_index]
        episode_bounds.append({
            "episode_index": int(episode["episode_index"]),
            "length": int(episode["length"]),
            "dataset_from_index": int(episode["dataset_from_index"]),
            "dataset_to_index_exclusive": int(episode["dataset_to_index"]),
        })
        calibration.extend(sample_entry(episode, fraction) for fraction in CALIBRATION_FRACTIONS)
        validation.extend(sample_entry(episode, fraction) for fraction in VALIDATION_FRACTIONS)

    calibration_indices = {item["dataset_index"] for item in calibration}
    validation_indices = {item["dataset_index"] for item in validation}
    if len(calibration) != 300 or len(calibration_indices) != 300:
        raise RuntimeError("Calibration selection is not 300 unique frames")
    if len(validation) != 100 or len(validation_indices) != 100:
        raise RuntimeError("Validation selection is not 100 unique frames")
    overlap = sorted(calibration_indices & validation_indices)
    if overlap:
        raise RuntimeError(f"Calibration/validation overlap: {overlap}")

    payload = {
        "schema_version": 1,
        "status": "FROZEN",
        "dataset": {"repo_id": REPO_ID, "root": str(DATASET_ROOT), "total_episodes": dataset.num_episodes, "total_frames": len(dataset)},
        "selection": {
            "calibration_fractions": list(CALIBRATION_FRACTIONS),
            "validation_fractions": list(VALIDATION_FRACTIONS),
            "calibration_count": len(calibration),
            "validation_count": len(validation),
            "overlap_count": 0,
        },
        "episode_bounds": episode_bounds,
        "calibration": calibration,
        "validation": validation,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"PTQ INDEX GATE: PASS")
    print(f"calibration={len(calibration)} validation={len(validation)} overlap=0 episodes={dataset.num_episodes}")
    print(f"content_sha256={payload['content_sha256']}")
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
