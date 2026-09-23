"""Generate a deterministic hash inventory for the Phase 3 V2.9 workspace."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
PHASE_ROOT = REPOSITORY / "projects" / "so101_L1" / "openvino" / "phase3_v2_9"
OUTPUT = PHASE_ROOT / "phase3_artifact_manifest.json"
EXCLUDED_PARTS = {"__pycache__"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    files = []
    for path in sorted(PHASE_ROOT.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        relative = path.relative_to(PHASE_ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "git_payload_policy": (
                    "EXTERNAL_CONTENT_ADDRESSED_ARTIFACT"
                    if path.suffix.lower() in {".bin", ".xml", ".pt", ".pt2", ".npy", ".npz"}
                    and "policy_package" in relative.parts
                    else "TRACKED_EVIDENCE_OR_SOURCE"
                ),
            }
        )

    manifest = {
        "schema_version": 1,
        "phase": "Phase 3 V2.9 255H Intel Pre-Deployment",
        "generated_on_local_date": date.today().isoformat(),
        "root": str(PHASE_ROOT.relative_to(REPOSITORY)),
        "exclusions": ["__pycache__", OUTPUT.name],
        "file_count": len(files),
        "files": files,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(files)} entries")


if __name__ == "__main__":
    main()
