# Outputs: Understanding Your Audit Report

## The Audit Package

`audit.html` is the only human-readable report. `audit.json`, `manifest.json`,
and `inputs/` are retained for reproducibility and integration.

Every run produces:

```text
out/
├── audit.html            ← Human-readable HTML report
├── audit.json            ← Machine-readable (full indicator register)
├── manifest.json         ← sha256, git commit, Python version
├── inputs/               ← All inputs copied with hash-prefixed names
└── .tmp/                 ← Auto-generated resolved config
```

## Guided Workflow Outputs

`run_full_audit.py` additionally writes `workflow-state.json` (v2 durable
stage state, signature-bound steps, artifact hashes, and recoverable errors),
`next-actions.json` (recoverable actions), and, when applicable,
`import/import-preview.json`, `screening/screening-decisions.json`,
`screening/screening-summary.json`, and `citations/citation-candidates.json`
plus manifests. Use `--resume` only with the same inputs; use a fresh run or
`--force` when inputs change. Older v1.1 step-only state remains readable, but
new runs write the v2 contract.

When online metadata enrichment is explicitly allowed, it also writes `enrichment/library-enriched.json` and `enrichment/metadata-enrichment.json`. The enriched library is used for downstream auditing, while user-provided fields always take precedence. Missing credentials, ambiguous matches, and source failures are recorded as gaps and do not silently become guessed values. Absent metadata-enrichment permission skips this step; `automation.local_only_confirmed=true` is reserved for a user-confirmed fully local run.

> **Privacy**: No absolute paths recorded. Input files are copied with sha256 prefix only.

## Report Sections

1. **Input Evidence Table** — Shows exactly what data was available and what was missing
2. **Priority Actions** — Top 3 highest-priority actions (🔴 blocking first, 🟡 warnings second)
3. **A–F Summary Table** — All 21 (24 for umbrella) indicators in one table
4. **Dimension Narratives** — One paragraph per dimension connecting numbers to meaning
5. **Recommendations** — Grouped blocking vs. suggested, each with concrete action
6. **Limitations & Disclaimers** — What this report cannot tell you
7. **Standards Appendix** — Every threshold applied, its source, and whether user-modified

## Indicator Register (audit.json)

Each entry:
```json
{
  "parent_dimension": "A 覆盖",
  "subproject": "A1",
  "project_name": "基准集召回率",
  "standard": "阈值 ≥ 0.75",
  "meets_standard": "fail",
  "current_status": "0.500（1/2）",
  "evidence_status": "measured",
  "description_and_action": "..."
}
```

Derived from `schemas/indicator-registry.json` — the single source of truth.

## Verdict Meanings

| Verdict | Means | Does NOT mean |
|---|---|---|
| `pass` | Current evidence meets standard | "Perfect" |
| `warning` | Risk signal — attention recommended | "Cannot write review" |
| `fail` | Standard not met — address first | "Worthless" |
| `not_assessable` | Missing input — fixable | "Doesn't matter" |

## Reproducibility

Every run is reproducible: `run-config.json` captures decisions, `manifest.json` records hashes, inputs are copied. Re-running with same inputs produces identical `audit.json`.
