# Outputs: Understanding Your Audit Report

## The Audit Package

Every run produces:

```text
out/
├── audit.md              ← Human-readable report
├── audit.html            ← Rendered HTML
├── audit.json            ← Machine-readable (full indicator register)
├── manifest.json         ← sha256, git commit, Python version
├── inputs/               ← All inputs copied with hash-prefixed names
└── .tmp/                 ← Auto-generated resolved config
```

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
