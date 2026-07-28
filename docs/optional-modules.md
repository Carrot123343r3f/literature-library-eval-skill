# Optional modules

The basic workflow always creates a query plan, a citation seed plan, and—when an authorized OpenAlex connection is available—forward/backward citation candidates. Those outputs are candidate-discovery evidence, never formal inclusions.

Enable the following only when their extra time, network use, or review effort is justified:

| Module | When to use it | Entry point | What it does not do |
| --- | --- | --- | --- |
| Metadata enrichment | Existing records are missing DOI, abstracts, years, or source fields | `automation.allow_metadata_enrichment=true` | Does not replace original records or invent missing facts |
| Search iteration | The first query misses important work or needs reproducible tuning | `search_iterator.py` + `evalset_audit.py` | Does not turn a development set into independent validation |
| Two-store optimization | A team will improve prompts, policies, or retrieval over time | `optimization.py` | Does not modify the audit unless its contract validates |
| Paper evidence evaluation | You need per-paper evidence roles and appraisal, not just library readiness | `run_paper_evaluation.py` | Does not make external candidates formal inclusions |

Each module is opt-in, preserves artifacts and decision history, and may be run after the basic audit without rerunning unrelated stages.
