#!/usr/bin/env python3
"""Unit checks for the portable Phase 4 pre/post transform."""

from __future__ import annotations

import unittest

import numpy as np

from phase4_prepost import postprocess_action, preprocess_observation


SPEC = {
    "eps": 1e-8,
    "features": {
        "observation.state": {"mean": [1, 2, 3, 4, 5, 6], "std": [2] * 6},
        "observation.images.wrist": {"mean": [0.1, 0.2, 0.3], "std": [0.5] * 3},
        "action": {"mean": [1, 2, 3, 4, 5, 6], "std": [2] * 6},
    },
}


class PortablePrePostTests(unittest.TestCase):
    def test_preprocess_batches_normalizes_and_does_not_mutate_source(self) -> None:
        state = np.asarray([1, 4, 3, 8, 5, 10], dtype=np.float32)
        image = np.zeros((3, 480, 640), dtype=np.float32)
        original_state = state.copy()
        original_image = image.copy()

        result = preprocess_observation(
            {"observation.state": state, "observation.images.wrist": image}, SPEC
        )

        self.assertEqual(result["state"].shape, (1, 6))
        self.assertEqual(result["wrist_image"].shape, (1, 3, 480, 640))
        self.assertEqual(result["state"].dtype, np.dtype("float32"))
        np.testing.assert_array_equal(state, original_state)
        np.testing.assert_array_equal(image, original_image)
        np.testing.assert_allclose(
            result["state"], np.asarray([[0, 1, 0, 2, 0, 2]], dtype=np.float32)
        )

    def test_postprocess_unnormalizes_without_mutating_source(self) -> None:
        normalized = np.ones((1, 100, 6), dtype=np.float32)
        original = normalized.copy()

        result = postprocess_action(normalized, SPEC)

        np.testing.assert_array_equal(normalized, original)
        np.testing.assert_allclose(
            result[0, 0], np.asarray([3, 4, 5, 6, 7, 8], dtype=np.float32)
        )

    def test_wrong_dtype_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "dtype changed"):
            preprocess_observation(
                {
                    "observation.state": np.zeros((6,), dtype=np.float64),
                    "observation.images.wrist": np.zeros((3, 480, 640), dtype=np.float32),
                },
                SPEC,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
