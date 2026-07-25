# Architecture

## Pipeline

> **Current state (v1.0)**: Steps 1–2, 6–9 are fully implemented in code.
> Steps 3–5 are partially automated (single-round diagnostic search,
> automated candidate dedup) but rely on AI agent orchestration in
> conversation for multi-round iteration, cross-database queries,
> citation tracking, and formal screening are available as explicit, persisted workflow steps.
> `run_full_audit.py` provides a resumable orchestration layer; it never silently
> converts discovery candidates into screened inclusions.

```text
User Intake (run-config.json)
  │
  ├─→ [1] Problem & Scope Modeling         ✅
  │       PICO decomposition, review type, profile, boundaries
  │
  ├─→ [2] Search Plan & Vocabulary         ✅ (protocol) / 📋 (auto-build)
  │       Concept matrix, source syntax mapping, query construction
  │
  ├─→ [3] Multi-Source Search & Snapshots    🔧
  │       Execute queries, paginate, retry, save raw snapshots
  │
  ├─→ [4] Normalize, Deduplicate, Version-Family ✅
  │       Stable-ID dedup, title-year fuzzy matching, preprint–published linking
  │
  ├─→ [5] Automated Screening & Decision Log   🔧
  │       Frozen inclusion/exclusion rules → per-item decisions
  │
  ├─→ [6] Dev Set / Validation Set              ✅
  │       Evidence set separation, independence verification
  │
  ├─→ [7] Query Iteration & Stop Decision       🔧 (AI-assisted)
  │       Atomic changes, comparison table, A2 stop ≠ B stop
  │
  ├─→ [8] A–F Indicator Calculation             ✅
  │       run_audit.py — deterministic computation + report
  │
  └─→ [9] Audit Package
        audit.md + audit.html + audit.json + manifest.json + inputs/
```

## Component Map

| Component | Responsibility | Status |
|---|---|---|
| `intake-protocol.md` | User interaction state machine | ✅ |
| `run-config-schema.json` | Single source of truth for evaluation inputs | ✅ |
| `search-strategy-protocol.md` | Query iteration protocol | ✅ |
| `indicator-registry.json` | Machine-readable indicator definitions | ✅ |
| `search_for_eval.py` | Single-round diagnostic search | ✅ |
| `search_iterator.py` | Multi-round iteration validator | ✅ |
| `normalize_candidates.py` | Identifier dedup + version grouping | ✅ |
| `import_library.py` | JSON/CSV/RIS/BibTeX normalization + import preview | ✅ |
| `run_full_audit.py` | Guided, resumable import → collect → screen → audit workflow | ✅ |
| `screen_candidates.py` | Human screening template and decision-log validation | ✅ |
| `citation_candidates.py` | Authorized OpenAlex forward/backward candidate discovery | ✅ |
| `next_actions.py` | Decision-first recovery actions derived from audit output | ✅ |
| `run_audit.py` | A–F orchestration, computation and audit-package assembly | ✅ |
| `run_paper_evaluation.py` | V2 orchestration for design-aware per-paper evidence evaluation, core support and external candidates | ✅ |
| `audit_core/contracts.py` | Shared v1.0 configuration validation, report-cell normalization and recursive redaction | ✅ |
| `audit_core/rendering.py` | Shared dependency-free Markdown-to-HTML renderer used by both report workflows | ✅ |
| `paper_evaluation/contracts.py` | V2 paper-record contract and canonical identifiers | ✅ |
| `paper_evaluation/evaluation.py` | V2 study-design routing, evidence appraisal and ranking signals | ✅ |
| `paper_evaluation/external.py` | Authorized OpenAlex discovery, normalization and library de-duplication | ✅ |
| `credentials.py` | Configured external-source credentials; never serializes secrets | ✅ |
| `artifact_manifest.py` | Redacted input copies, hashes and standalone workflow step status | ✅ |
| `build_query_plan.py` | Cross-database query plan from PICO | 📋 |
| `execute_search.py` | Multi-source search with pagination | 📋 |
| `refine_queries.py` | Constrained atomic query modification | 📋 |
| `screen_candidates.py` | Automated screening with frozen rules | 📋 |
| `build_evidence_sets.py` | Dev/validation set construction | 📋 |
| `validate_run.py` | Pre-report completeness check | 📋 |

## Data Contracts

- **run-config.json**: Single entry point, validated against schema, relative paths resolved against config directory
- **search_meta.json**: Bridge between search execution and audit computation
- **audit.json**: Machine-readable output with full indicator register
- **manifest.json**: sha256, git commit, Python version — every input accounted for
- **paper-evaluation.json**: V2 per-paper evidence output; its companion manifest records redacted input copies, hashes and step status
- **paper-evaluation-schema.json**: Machine-readable V2 output contract
- **audit_core public API**: shared components own cross-workflow concerns; workflow entry points must not import another workflow's private helpers

## Workflow Boundary

The repository intentionally does not claim that multi-round searching, screening and evidence extraction are fully automatic. The workflow persists each completed artifact and can resume from its state file. Discovery candidates remain `candidate_discovery` until a human creates final include/exclude decisions. `run_paper_evaluation.py` is independently reproducible from its input artifacts and does not alter A–F evidence or saturation results.

## Extension Points

1. **New database sources**: Add syntax mapping + API adapter
2. **New engineering profiles**: Entry in `PROFILES` dict + Tier-1 venue list
3. **New indicators**: Add to indicator-registry.json → add the computation in `run_audit.py` → update the report assembly
4. **New output formats**: Add a renderer beside `audit_core/rendering.py`; keep report data generation independent of presentation
5. **New review types**: Add threshold row + schema enum value
