"""Create the V2.9 frozen ACT reference and ExportedProgram in the LeRobot environment."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
OPENVINO_ROOT = HERE.parent
PACKAGE_DIR = HERE / "policy_package_v2_9"
EVIDENCE_DIR = HERE / "evidence" / "phase3_1_policy_package"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    create_reference = load_script("phase3_create_reference", OPENVINO_ROOT / "create_act_reference.py")
    create_reference.OUTPUT_DIR = PACKAGE_DIR
    export_wrapper = load_script("phase3_export_wrapper", OPENVINO_ROOT / "export_act_wrapper.py")
    export_wrapper.PACKAGE_DIR = PACKAGE_DIR

    started = time.perf_counter_ns()
    create_reference.main()
    reference_ms = (time.perf_counter_ns() - started) / 1_000_000

    manifest_path = PACKAGE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["phase"] = "Phase 3.1 V2.9 frozen PyTorch reference"
    manifest["package_id"] = "policy_package_v2_9"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    started = time.perf_counter_ns()
    export_wrapper.main()
    export_ms = (time.perf_counter_ns() - started) / 1_000_000

    expected = {
        "reference_raw_observation.pt",
        "reference_model_input.pt",
        "reference_output_normalized.pt",
        "reference_output_action_chunk.pt",
        "manifest.json",
        "act_tensor_wrapper.pt2",
    }
    missing = sorted(name for name in expected if not (PACKAGE_DIR / name).is_file())
    if missing:
        raise RuntimeError(f"Missing Phase 3.1 artifacts: {missing}")

    model_input = torch.load(PACKAGE_DIR / "reference_model_input.pt", weights_only=False)
    normalized = torch.load(PACKAGE_DIR / "reference_output_normalized.pt", weights_only=False)["action_chunk"]
    evidence = {
        "schema_version": 1,
        "phase": "Phase 3.1 source reference and export",
        "status": "PASS",
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "cuda_visible_to_torch": torch.cuda.is_available(),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "huggingface_home": os.environ.get("HF_HOME"),
        "required_runtime_device": "cpu",
        "timing_ms": {"reference_creation": reference_ms, "strict_export": export_ms},
        "tensor_contract": {
            "state": list(model_input["observation.state"].shape),
            "wrist_image": list(model_input["observation.images.wrist"].shape),
            "normalized_action_chunk": list(normalized.shape),
        },
        "artifact_sha256": {name: sha256(PACKAGE_DIR / name) for name in sorted(expected)},
    }
    evidence_path = EVIDENCE_DIR / "source_reference_export.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"SOURCE REFERENCE/EXPORT GATE: PASS")
    print(f"Saved evidence: {evidence_path}")


if __name__ == "__main__":
    main()
