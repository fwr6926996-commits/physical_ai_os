"""Validate repository-to-Notion projection records and detect source drift."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPOSITORY / "docs" / "process" / "notion_sync_registry.json"
EXAMPLE_REGISTRY = REPOSITORY / "docs" / "process" / "notion_sync_registry.example.json"
ALLOWED_STATES = {"PENDING", "SYNCED", "STALE", "FAILED", "BLOCKED", "NOT_REQUIRED"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_record(record: dict[str, Any]) -> dict[str, Any]:
    sync_id = record.get("sync_id", "<missing>")
    state = record.get("sync_status")
    require(state in ALLOWED_STATES, f"{sync_id}: invalid sync_status {state!r}")

    paths = record.get("source_paths")
    hashes = record.get("source_sha256")
    require(isinstance(paths, list) and paths, f"{sync_id}: source_paths must be non-empty")
    require(isinstance(hashes, dict), f"{sync_id}: source_sha256 must be an object")

    changed: list[str] = []
    for relative_text in paths:
        require(isinstance(relative_text, str), f"{sync_id}: source path must be a string")
        relative = Path(relative_text)
        require(not relative.is_absolute() and ".." not in relative.parts, f"{sync_id}: unsafe path")
        source = REPOSITORY / relative
        require(source.is_file(), f"{sync_id}: missing source {relative_text}")
        expected = hashes.get(relative_text)
        require(isinstance(expected, str) and len(expected) == 64, f"{sync_id}: missing hash for {relative_text}")
        if sha256(source) != expected:
            changed.append(relative_text)

    notion_url = record.get("notion_url")
    notion_page_id = record.get("notion_page_id")
    if state in {"SYNCED", "STALE"}:
        require(isinstance(notion_page_id, str) and notion_page_id, f"{sync_id}: missing page ID")
        require(
            isinstance(notion_url, str) and notion_url.startswith("https://"),
            f"{sync_id}: invalid Notion URL",
        )
        require(isinstance(record.get("synced_at"), str), f"{sync_id}: missing synced_at")

    effective_state = "STALE" if changed and state == "SYNCED" else state
    return {
        "sync_id": sync_id,
        "declared_state": state,
        "effective_state": effective_state,
        "changed_sources": changed,
        "notion_url": notion_url,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
        help="local registry to validate (default: ignored docs/process/notion_sync_registry.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    registry_path = args.registry.expanduser().resolve()
    if not registry_path.is_file():
        raise SystemExit(
            f"missing local registry: {registry_path}\n"
            f"initialize it from the redacted template: {EXAMPLE_REGISTRY}"
        )

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    require(registry.get("schema_version") == 1, "unsupported registry schema")
    records = registry.get("sync_records")
    require(isinstance(records, list), "sync_records must be a list")

    results = [validate_record(record) for record in records]
    ids = [result["sync_id"] for result in results]
    require(len(ids) == len(set(ids)), "duplicate sync_id")

    stale = [result["sync_id"] for result in results if result["effective_state"] == "STALE"]
    print(json.dumps({"records": results, "stale_count": len(stale)}, indent=2))
    if stale:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
