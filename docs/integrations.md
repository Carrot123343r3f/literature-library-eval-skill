# Integrations

## Reference Managers

The workflow creates an import preview before auditing and an HTML screening workbench after candidate collection. Use JSON for lossless workflow artifacts; CSV is supported for convenient spreadsheet review and re-import of screening decisions.

### Zotero

Export collection as Better BibTeX JSON or CSL JSON → point `library.path` to the file.

### EndNote / Mendeley

Export to RIS, BibTeX or CSV → normalize with `scripts/import_library.py` before auditing. Zotero API synchronization remains a roadmap item.

## Literature Databases

`automation.online_allowed_sources` authorizes only built-in live collectors
(OpenAlex, Crossref, arXiv, Europe PMC). `automation.offline_snapshot_sources`
records sources supplied through local exports and never grants network access.
The legacy `allowed_sources` remains only for backwards-compatible configs.

| Source | Status | Notes |
|---|---|---|
| OpenAlex | ✅ v1.0 | Open scholarly metadata and optional default discovery source. A missing `OPENALEX_API_KEY` does not block arXiv/Crossref/Europe PMC adapters; the key is never requested in chat or written to outputs. |
| Crossref | 📋 v1.x | Better DOI metadata quality |
| Semantic Scholar | 📋 v1.x | Strong AI/CS coverage, citation graph |
| IEEE Xplore / Scopus / WoS | 📋 v2.0 | Institutional access required |

### Institutional database exports

IEEE Xplore, Scopus, Web of Science, Ei Compendex, and Inspec exports can be
used now without a live API connector. `scripts/import_source_snapshots.py`
converts RIS, CSV, BibTeX, or JSON exports into an A3-compatible snapshot using
a **per-source manifest**. It records the source-specific query, scope filters,
export time, reported total, export limit, completeness basis, and SHA-256 of
the original export. It never uses or stores database credentials.

```bash
python scripts/import_source_snapshots.py --manifest institutional-exports.json --out institutional-snapshot.json
```

Each `institutional-exports.json` entry must include `source`, `input`, `query`,
`scope_filters`, `dedup_rule`, and `exported_at`. A source is `complete` only
when its `reported_total` is present, the imported count covers that total, and
`completeness_basis` documents an uncapped/full export. Otherwise it is always
`partial`; it retains provenance but cannot support an A3 conclusion.

## Companion Skills

### literature-library-eval (this skill)

Audits whether a literature library has the structural evidence base for a credible review. **Use before writing.**

### scholar-evaluation (K-Dense)

Evaluates finished paper quality using 8-dimension ScholarEval with 1–5 scoring. **Use after writing.**

### review-manuscript-audit (planned)

Bridge between library readiness and paper quality:
- PRISMA / PRISMA-ScR compliance
- Search strategy completeness
- Inclusion/exclusion consistency
- Study quality tool → design matching
- Thematic synthesis vs. sequential listing detection
- Citation accuracy and opposing evidence coverage

## Automation Pipeline

```text
Research Question
  │
  ├─→ literature-library-eval
  │     └─→ "Ready" or "Fix these N things"
  │
  ├─→ [Write the review]
  │
  ├─→ review-manuscript-audit (future)
  │     └─→ PRISMA, citations, synthesis quality
  │
  └─→ scholar-evaluation (K-Dense)
       └─→ 8-dimension quality scores
```
