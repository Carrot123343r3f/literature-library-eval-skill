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

When an evidence-isolation manifest is supplied, it is copied into `inputs/` and the report records whether the validation set was frozen, query-independent, and separate from B3/A3 evidence. See `schemas/evidence-manifest-schema.json`.

> **Privacy**: No absolute paths recorded. Input files are copied with sha256 prefix only.

## Report Sections

The report includes a **Search Strategy & Iteration Process** section whenever q0, query versions, or an iteration log is available. It lists query origin, exact query text, database/source, execution date, hit count, status, and every atomic change. A first-round-only record is explicitly described as diagnostic rather than an optimized final strategy.

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

### How to read a missing result

`not_assessable` does not mean that the library is poor. It means the current run does not contain enough evidence for that indicator. The report should name the lowest-cost next input, such as an executed query log, an independent validation set, or a screening decision log. Treat `fail` as a risk signal against the configured standard, not as a final judgment about the review.
