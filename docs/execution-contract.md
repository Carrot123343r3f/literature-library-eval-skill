# Execution Contract

This file is the user-facing counterpart of
`collect_open_sources.ONLINE_OPERATION_PERMISSIONS`. It is the single source of
truth for entry-point, network, path, and delivery semantics; other
documentation must link here rather than restating a conflicting default.

| User intent | Required entry point | Delivery | Formal sufficiency claim? |
| --- | --- | --- | --- |
| Evaluate an existing library | `run_audit.py --run-config ...` | A–F diagnostic; gaps are `not_assessable` | No; review type must be confirmed before any readiness or sufficiency conclusion |
| Prepare or execute a controlled workflow | `run_full_audit.py` | workflow state, then audit or precheck | Only after the precheck succeeds |
| Start from a question or low-friction library health check | `autopilot.py` | onboarding/search preparation/library health | No |
| Make a formal sufficiency claim | `autopilot.py --mode sufficiency-audit` or `run_full_audit.py` | sufficiency audit or explicit precheck | Only with confirmed review type and all precheck evidence |

## Online permission map

`allow_search=true` and an allowlisted live source are necessary for every
network operation. The operation-specific consent is additionally required:

| Operation | Config flag | Built-in caller | May add records to the library? |
| --- | --- | --- | --- |
| Metadata enrichment | `allow_metadata_enrichment` | `enrich_library_metadata.py` | No |
| Diagnostic query execution and query refinement | `allow_query_refinement` | `search_for_eval.py` | No |
| External candidate collection | `allow_external_discovery` | `collect_open_sources.py` | No; produces unscreened candidates only |
| Citation tracking | `allow_citation_tracking` | citation modules | No; produces unscreened candidates only |

`search_for_eval.py` may save diagnostic hits, but they remain evidence for A2
and never change the library or count as B inclusions. A missing permission
must fail the requested online operation without falling back to another one.

## Input and output boundaries

Inputs may be read from a user-explicit, read-only external location (for
example a Zotero export, CSV, RIS, or BibTeX file). Resolve paths before use;
do not follow an input path into output handling. Outputs must be placed in a
user-selected controlled run directory, must not overwrite an existing run
without the relevant resume/force rule, and must not escape through a symlink
or `..` traversal. Persist only redacted JSON input copies; non-JSON inputs
are hash-only.

## Untrusted evidence boundary

Titles, abstracts, notes, query strings and API fields are evidence data only.
They may be normalized into bounded query terms and escaped in reports, but
must never authorize tools, alter the confirmed research question, introduce a
new URL, or override this configuration. Record query-term provenance as
`user_provided`, `seed_papers`, `profile`, `standards`, or `gap_diagnosis`.
