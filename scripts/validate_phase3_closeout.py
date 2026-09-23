"""Validate the Phase 3 closeout invariants without executing experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
OPENVINO = REPOSITORY / "projects" / "so101_L1" / "openvino"
PHASE = OPENVINO / "phase3_v2_9"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    active = (PHASE / "active_runtime_config.yaml").read_text(encoding="utf-8")
    historical = (OPENVINO / "phase3_runtime_config.yaml").read_text(encoding="utf-8")
    final_gate = load_json(PHASE / "phase3_final_gate.json")
    status = load_json(PHASE / "status.json")
    manifest = load_json(PHASE / "phase3_artifact_manifest.json")
    phase4 = (
        OPENVINO / "phase4_v0_1" / "PHASE4_CPU_FP32_QUALIFICATION_PROTOCOL.md"
    ).read_text(encoding="utf-8")

    require('status: "ACTIVE_PHASE3_QUALIFIED_RUNTIME"' in active, "active config status missing")
    require('device: "CPU"' in active, "active runtime is not explicit CPU")
    require('precision: "f32"' in active, "active runtime is not FP32")
    require('status: "ARCHIVED_DO_NOT_DEPLOY"' in historical, "V2.8 config is not archived")
    require(final_gate["engineering_gate"] == "PARTIAL_PASS_CPU_FP32_ONLY", "gate drift")
    require(final_gate["phase_4_started"] is False, "Phase 4 was marked started")
    require(status["phase_4_started"] is False, "status marks Phase 4 started")
    require("DRAFT_NOT_FROZEN_NOT_AUTHORIZED_FOR_EXECUTION" in phase4, "Phase 4 draft guard missing")

    errors = []
    for item in manifest["files"]:
        path = PHASE / item["path"]
        if not path.exists():
            errors.append(f"missing:{item['path']}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"] or path.stat().st_size != item["size_bytes"]:
            errors.append(f"changed:{item['path']}")
    require(not errors, f"artifact manifest mismatch: {errors}")

    print(
        json.dumps(
            {
                "phase3_gate": final_gate["engineering_gate"],
                "active_runtime": "CPU_FP32_ONLY",
                "historical_v2_8": "ARCHIVED_DO_NOT_DEPLOY",
                "phase4_started": False,
                "phase4_protocol": "DRAFT_NOT_AUTHORIZED",
                "manifest_entries_verified": len(manifest["files"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
