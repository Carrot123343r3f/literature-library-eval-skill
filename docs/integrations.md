# Integrations

## Reference Managers

### Zotero

Export collection as Better BibTeX JSON or CSL JSON → point `library.path` to the file.

### EndNote / Mendeley

Export to RIS or BibTeX → convert to JSON. Direct format support: v1.x roadmap.

## Literature Databases

| Source | Status | Notes |
|---|---|---|
| OpenAlex | ✅ v1.0 | Free, no API key — default discovery source |
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
