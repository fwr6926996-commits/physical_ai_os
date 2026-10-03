#!/usr/bin/env python3
"""Portable frozen ACT preprocessing and postprocessing for Phase 4.

The implementation intentionally depends only on NumPy.  Its constants live in the frozen
Phase 4 config and are checked against the original LeRobot pipeline before deployment.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _float32(values: Any, expected_shape: tuple[int, ...], name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype != np.dtype("float32"):
        raise RuntimeError(f"{name} dtype changed: {array.dtype} != float32")
    if array.shape != expected_shape:
        raise RuntimeError(f"{name} shape changed: {array.shape} != {expected_shape}")
    return array


def _stats(spec: dict[str, Any], feature: str, shape: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    feature_spec = spec["features"][feature]
    mean = np.asarray(feature_spec["mean"], dtype=np.float32).reshape(shape)
    std = np.asarray(feature_spec["std"], dtype=np.float32).reshape(shape)
    if np.any(std <= 0):
        raise RuntimeError(f"Frozen standard deviation for {feature} must be positive")
    return mean, std


def preprocess_observation(
    raw_observation: dict[str, np.ndarray], spec: dict[str, Any]
) -> dict[str, np.ndarray]:
    """Clone, batch and mean/std-normalize the frozen state and wrist image."""

    eps = np.float32(spec["eps"])
    raw_state = _float32(raw_observation["observation.state"], (6,), "raw state")
    raw_image = _float32(
        raw_observation["observation.images.wrist"], (3, 480, 640), "raw wrist image"
    )
    state_mean, state_std = _stats(spec, "observation.state", (6,))
    image_mean, image_std = _stats(spec, "observation.images.wrist", (3, 1, 1))

    state = ((raw_state.copy() - state_mean) / (state_std + eps))[None, :]
    image = ((raw_image.copy() - image_mean) / (image_std + eps))[None, :]
    return {
        "state": np.ascontiguousarray(state, dtype=np.float32),
        "wrist_image": np.ascontiguousarray(image, dtype=np.float32),
    }


def postprocess_action(normalized_action: np.ndarray, spec: dict[str, Any]) -> np.ndarray:
    """Clone and mean/std-unnormalize one normalized ACT action chunk."""

    normalized = _float32(normalized_action, (1, 100, 6), "normalized action")
    action_mean, action_std = _stats(spec, "action", (6,))
    return np.ascontiguousarray(normalized.copy() * action_std + action_mean, dtype=np.float32)
