"""Run a correctness-gated segmented benchmark for one logical Intel device."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
EVIDENCE_DIR = HERE / "evidence" / "phase3_2_measurements"
LEROBOT_PYTHON = "/home/lucas/miniconda3/envs/lerobot/bin/python"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, choices=("CPU", "GPU.0", "NPU"))
    parser.add_argument("--inference-precision", choices=("default", "f32", "f16"), default="default")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    slug = args.device.lower().replace(".", "_")
    run_id = f"{slug}_{args.inference_precision}_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    env["HF_HOME"] = "/tmp/so101_phase3_hf_cache"
    common = ["--run-id", run_id, "--warmup", str(args.warmup), "--iterations", str(args.iterations)]
    subprocess.run([LEROBOT_PYTHON, str(HERE / "benchmark_prepost_v2_9.py"), *common], check=True, env=env)
    subprocess.run([
        sys.executable, str(HERE / "benchmark_device_v2_9.py"), *common,
        "--device", args.device, "--inference-precision", args.inference_precision,
    ], check=True, env=env)

    prepost_path = EVIDENCE_DIR / f"{run_id}_prepost.json"
    inference_path = EVIDENCE_DIR / f"{run_id}_inference.json"
    prepost = json.loads(prepost_path.read_text())
    inference = json.loads(inference_path.read_text())
    stages = {
        "preprocessing": prepost["latency_ms"]["preprocessing"],
        "inference": inference["latency_ms"],
        "postprocessing": prepost["latency_ms"]["postprocessing"],
    }
    summary = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "PASS",
        "logical_device": args.device,
        "runtime_device": inference["runtime_device"],
        "requested_inference_precision": args.inference_precision,
        "warmup_iterations": args.warmup,
        "measured_iterations": args.iterations,
        "stages_ms": stages,
        "sum_of_independent_stage_percentiles_ms": {
            key: sum(stage[key] for stage in stages.values()) for key in ("p50", "p95", "p99")
        },
        "interpretation_limit": "Stages run in two isolated environments; percentile sums are diagnostic, not a same-process end-to-end distribution.",
        "evidence": {"prepost": str(prepost_path), "inference": str(inference_path)},
    }
    summary_path = EVIDENCE_DIR / f"{run_id}_segmented_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"SEGMENTED BENCHMARK: PASS\nSaved summary: {summary_path}")


if __name__ == "__main__":
    main()
