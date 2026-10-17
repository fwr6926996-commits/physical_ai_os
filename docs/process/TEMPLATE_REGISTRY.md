# Process Template Registry

Registry version: `0.3`

| Template | Version | Status | Required use |
|---|---:|---|---|
| `templates/EXPERIMENT_PROTOCOL.md` | 0.1 | TRIAL | Formal qualification experiments and high-impact comparative benchmarks |
| `templates/BUG_DIAGNOSIS.md` | 0.2 | TRIAL | Important failures, hangs, crashes, correctness regressions and unexplained performance anomalies; declare learning depth when learning value is material |
| `templates/PHASE_ACCEPTANCE.md` | 0.2 | TRIAL | Phase closeout, partial pass, waiver handoff and next-phase entry decisions |

Do not create a new template for a one-off issue. Record the issue in the applicable protocol, diagnosis, ADR or retrospective first.

Notion projections are governed by `NOTION_SYNC.md`. The public configuration shape is tracked in
`notion_sync_registry.example.json`; real page mappings remain in the ignored local
`notion_sync_registry.json` and do not introduce a second engineering record template.
