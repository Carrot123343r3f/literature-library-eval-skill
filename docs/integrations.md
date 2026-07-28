# Integrations

## Reference Managers

The workflow creates an import preview before auditing and an HTML screening workbench after candidate collection. Use JSON for lossless workflow artifacts; CSV is supported for convenient spreadsheet review and re-import of screening decisions.

### Zotero

Export collection as Better BibTeX JSON or CSL JSON → point `library.path` to the file.

### EndNote / Mendeley

Export to RIS, BibTeX or CSV → normalize with `scripts/import_library.py` before auditing. Zotero API synchronization remains a roadmap item.

## Literature Databases

| Source | Status | Notes |
|---|---|---|
| OpenAlex | ✅ v1.0 | Open scholarly metadata and optional default discovery source. A missing `OPENALEX_API_KEY` does not block arXiv/Crossref/Europe PMC adapters; the key is never requested in chat or written to outputs. |
| Crossref | 📋 v1.x | Better DOI metadata quality |
| Semantic Scholar | 📋 v1.x | Strong AI/CS coverage, citation graph |
| IEEE Xplore / Scopus / WoS | 📋 v2.0 | Institutional access required |

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
