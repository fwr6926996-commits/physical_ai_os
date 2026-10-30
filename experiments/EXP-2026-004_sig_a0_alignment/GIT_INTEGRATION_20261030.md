# Git progress integration — 2026-10-30

This integration publishes the existing local progress while retaining all commits previously
on origin/main (`0807dd2`). It records repository synchronization only; no new engineering
acceptance, protocol authorization or execution result is created.

## Dated source records

The local checkout began at `3f141d0` and accumulated later records without the 13 intervening
remote commits. Both histories independently added several SIG-A0 files. The parent directory
retains the exact bytes of the local 2026-10-26/27 records so their frozen hash references remain
valid. `history_20261017/` preserves the remote review bundle and protocol byte for byte.
Remote-only planning and consistency-review documents are also retained at their original paths.
Their relative references describe the 2026-10-17 baseline preserved in that archive.

The 2026-10-17 interface correction and the later local drafts are separate dated records.
This file does not declare one contract accepted in place of another, resolve their differences,
or expand any human decision. Consult each decision and its referenced source revision before
using a contract for further work.

## Local Notion evidence

The remote privacy policy and checker are retained: real page IDs and URLs stay outside the
public repository. The local registry and the following original evidence files are preserved
on disk and ignored by Git. Public manifests may refer to these local-only files; those
references are not a claim that the complete Notion evidence is available in a fresh clone.
Original evidence is not redacted or rehashed to make a different artifact look identical.

- `docs/process/notion_sync_registry.json`
- `experiments/EXP-2026-004_sig_a0_alignment/acceptance_20261027/notion_readback.json`
- `experiments/EXP-2026-004_sig_a0_alignment/review_20261027/CANDIDATE_TRIGGER_REVIEW.md`
- `experiments/EXP-2026-004_sig_a0_alignment/review_20261027/notion_candidate_snapshot.json`
- `experiments/EXP-2026-004_sig_a0_alignment/t0_acceptance_20261027/notion_readback.json`
- `experiments/EXP-2026-004_sig_a0_alignment/t0_host_implementation_20261027/notion_sync_pending.json`
- `experiments/EXP-2026-004_sig_a0_alignment/t0_implementation_20261027/notion_readback.json`
- `experiments/EXP-2026-004_sig_a0_alignment/t0_ros_design_20261028/host_notion_partial.json`
- `experiments/EXP-2026-004_sig_a0_alignment/t0_ros_design_20261028/host_notion_sync_resolution.json`
