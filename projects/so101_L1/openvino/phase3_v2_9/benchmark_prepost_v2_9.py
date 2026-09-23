"""Measure the saved LeRobot preprocessing and postprocessing stages."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import torch
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors


HERE = Path(__file__).resolve().parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_DIR = HERE / "evidence" / "phase3_2_measurements"
CHECKPOINT = Path("/data/checkpoints/act_so101_50ep_10k/checkpoints/last/pretrained_model")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    return parser.parse_args()


def clone_tensors(values: dict) -> dict:
    return {key: value.clone() if isinstance(value, torch.Tensor) else value for key, value in values.items()}


def stats(samples: list[float]) -> dict[str, float]:
    values = np.asarray(samples, dtype=np.float64)
    return {
        "min": float(values.min()),
        "mean": float(values.mean()),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(values.max()),
    }


def measure(callable_, iterations: int) -> list[float]:
    samples = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        callable_()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return samples


def write_csv(path: Path, values: list[float]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["iteration", "latency_ms"])
        writer.writerows(enumerate(values, start=1))


def main() -> None:
    args = arguments()
    if args.warmup < 0 or args.iterations < 1:
        raise ValueError("--warmup must be >= 0 and --iterations must be >= 1")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    raw = torch.load(PACKAGE_DIR / "reference_raw_observation.pt", weights_only=False)
    normalized = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"]
    policy = ACTPolicy.from_pretrained(CHECKPOINT).eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=str(CHECKPOINT),
        preprocessor_overrides={"device_processor": {"device": "cpu"}},
    )

    def preprocess_once():
        result = preprocessor(clone_tensors(raw))
        return {key: result[key] for key in policy.config.input_features}

    def postprocess_once():
        return postprocessor(normalized.clone())

    for _ in range(args.warmup):
        preprocess_once()
        postprocess_once()

    process = psutil.Process()
    rss_before = process.memory_info().rss
    preprocessing = measure(preprocess_once, args.iterations)
    postprocessing = measure(postprocess_once, args.iterations)
    rss_after = process.memory_info().rss

    payload = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "status": "PASS",
        "scope": "Saved LeRobot preprocessing and postprocessing only; model inference excluded.",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "runtime_device": "cpu",
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "warmup_iterations": args.warmup,
        "measured_iterations": args.iterations,
        "latency_ms": {
            "preprocessing": stats(preprocessing),
            "postprocessing": stats(postprocessing),
        },
        "process_rss_bytes": {"before": rss_before, "after": rss_after, "delta": rss_after - rss_before},
    }
    result_path = EVIDENCE_DIR / f"{args.run_id}_prepost.json"
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_csv(EVIDENCE_DIR / f"{args.run_id}_preprocessing.csv", preprocessing)
    write_csv(EVIDENCE_DIR / f"{args.run_id}_postprocessing.csv", postprocessing)
    print(json.dumps(payload, indent=2))
    print(f"Saved pre/post evidence: {result_path}")


if __name__ == "__main__":
    main()
