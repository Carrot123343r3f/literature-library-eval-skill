# Architecture

## Pipeline

> **Current implementation**: Steps 1–2, 6–9 are implemented in code.
> Steps 3–5 are partly automated (first-run q0/atomic diagnostics,
> automated candidate dedup) but rely on AI agent orchestration in
> conversation for multi-round iteration, cross-database queries,
> citation tracking, and formal screening. A one-shot end-to-end
> orchestrator (`run_full_audit.py`) is planned for v2.0.

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
| `run_initial_assessment.py` | No-anchor/no-query first-run orchestration; outputs A1–A3/B1–B3 with direct verdicts and explicit evidence tiers | ✅ |
| `prepare_first_run_evidence.py` | Candidate-anchor auto-screening and deterministic dev/holdout preparation | ✅ |
| `search_for_eval.py` | Profile-aware multi-source q0 + atomic-variant diagnostic search | ✅ |
| `search_iterator.py` | Multi-round iteration validator | ✅ |
| `evidence_isolation.py` | Evidence-set provenance and leakage checks | ✅ |
| `collect_open_sources.py` | Open-source candidate snapshot collection | 🔧 |
| `normalize_candidates.py` | Identifier dedup + version grouping | ✅ |
| `validate_registry.py` | Validate a real audit output against the indicator registry | ✅ |
| `run_audit.py` | A–F computation + report generation | ✅ |
| `build_query_plan.py` | Cross-database query plan from PICO | 📋 |
| `execute_search.py` | Multi-source search with pagination | 📋 |
| `refine_queries.py` | Constrained atomic query modification | 📋 |
| `screen_candidates.py` | Automated screening with frozen rules | 📋 |
| `build_evidence_sets.py` | Dev/validation set construction | 📋 |
| `validate_run.py` | Pre-report completeness check | 📋 |
| `run_full_audit.py` | End-to-end orchestrator | 📋 |

## Data Contracts

- **run-config.json**: Single entry point, validated against schema, relative paths resolved against config directory
- **search_meta.json**: Bridge between search execution and audit computation
- **audit.json**: Machine-readable output with full indicator register
- **manifest.json**: sha256, git commit, Python version — every input accounted for
- **evidence-manifest.json**: dataset roles, source routes, freeze state, and A2/B3 + A3/B2 evidence reuse checks

## Extension Points

1. **New database sources**: Add syntax mapping + API adapter
2. **New engineering profiles**: Entry in `PROFILES` dict + Tier-1 venue list
3. **New indicators**: Add to indicator-registry.json → update run_audit.py → update report
4. **New output formats**: Extend `write()` in run_audit.py
5. **New review types**: Add threshold row + schema enum value

## Agent-assisted evidence isolation

The recommended workflow uses four procedural roles: Dataset Builder, Query Optimizer, Blind Evaluator, and Audit Agent. They may be separate threads, but independence is established by frozen artifacts and access boundaries, not memory separation alone. `evidence-manifest.json` is the machine-readable handoff contract.
