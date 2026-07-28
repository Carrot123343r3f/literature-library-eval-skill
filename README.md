# Engineering Literature Library Audit

<p align="center">
  <strong>Most literature reviews fail before the writing begins.</strong>
</p>

<p align="center">
  They fail when the library is incomplete, the search cannot be reproduced, or apparent saturation is only an artifact of one database. An audit that runs <em>before</em> you write saves months of rework — and a manuscript that cannot be defended.
</p>

<p align="center">
  <a href="https://github.com/Carrot123343r3f/literature-library-eval-skill/actions/workflows/ci.yml"><img src="https://github.com/Carrot123343r3f/literature-library-eval-skill/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License">
  <img src="https://img.shields.io/badge/indicators-21%20(%2B3%20umbrella)-8b5cf6" alt="Indicators">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Platform">
</p>

<p align="center">
  <a href="README.zh-CN.md">中文说明</a>
</p>

---

## What This Is

**Engineering Literature Library Audit** is an evidence-readiness diagnostic for engineering reviews. It does not write your review. It does not assign one opaque score. It shows what your library can support, what it cannot yet support, and why — before you invest months in a manuscript.

### The Problem

Every researcher knows this feeling:

- A new area, a scattered literature landscape — where do you even start searching?
- You've collected 200 papers, but there's a nagging worry: *did I miss an entire sub-direction?*
- You finish a draft, send it to your supervisor, and get back: *"You're missing X, Y, Z."* Three months of work, and the foundation was never checked.
- You searched one database thoroughly — but another would have surfaced entirely different papers.
- You wrote the review first, checked completeness later — and found out too late that the evidence base was never solid.

**This is structural waste.** The review-writing process should start with a structural check, not end with one.

### How This Fixes It

Run the audit **before** writing. In one command (or one conversation with an AI agent), you get:

- A prioritized list of exactly what needs fixing — blocking items first
- Six independent dimensions of readiness — no single score hides a fatal flaw
- Every input accounted for with sha256 hashes — the audit is reproducible
- Missing inputs are flagged as `not_assessable`, not hidden — *"here's the cheapest way to fix this"*

## Try the Demo — No Configuration Required

The repository includes a complete local reference fixture in
[`example-all-modules-report/`](example-all-modules-report/). It contains a small
sample library, a research question, search evidence, and the expected audit
artifacts. You can inspect the [bundled HTML report](example-all-modules-report/audit/audit.html)
after you have completed a first run. It is for maintainers, reviewers, and regression checks; it is not the recommended new-user entry point.

From the repository root, run:

```bash
python scripts/run_audit.py \
  --run-config example-all-modules-report/run-config.json \
  --out demo-output
```

Then open [`demo-output/audit.html`](demo-output/audit.html) in a browser. Before
running the command, the same kind of result is available in the bundled report
linked above.

This demo needs no API key, database account, research question, or personal
literature library because all required inputs are included locally. It is a
reproducible product tour, not an audit of your own research topic. To audit
your project, replace the example inputs with your own library and confirmed
research scope.

If the demo helps you find a gap in your review workflow, a GitHub Star is a
small way to help other engineering researchers discover the project.

## Why This Project

This project fills the gap between collecting papers and writing the review:

| Tool | Main job |
|---|---|
| Zotero | Store and organize references |
| Scholarly databases | Find papers |
| This project | Check whether the library and search evidence can support the review |

It is not a replacement for a reference manager, a database, or domain-expert
screening. Its distinctive output is a reproducible, evidence-graded diagnosis
of what the current library supports and what should happen next.

## Quickstart

**Current capability**: A guided, resumable CLI workflow now covers import, authorized metadata enrichment, collection, deduplication, HTML/CSV human screening workbenches, audit, and recovery actions. All online capabilities are opt-in; candidates never become formal inclusions without a human decision.

| Status | Step |
| :---: | --- |
| ✅ Automated | Audit computation (`run_audit.py`), single-round diagnostic search (`search_for_eval.py`), candidate dedup (`normalize_candidates.py`), optimization harness (`optimization.py`), counterexample/active-screening/drift checks (`quality_optimization.py`), experiment attribution/eval-set audit (`experiment_attribution.py`/`evalset_audit.py`), iteration validation/sync (`search_iterator.py`), report generation |
| ✅ Guided workflow | `run_full_audit.py` produces `workflow-state.json` and `next-actions.json`; it can import JSON/CSV/RIS/BibTeX and resume safely |
| 🔧 Human-confirmed | Multi-round iteration, cross-database search, citation tracking, and screening remain evidence-producing steps; candidates require explicit human decisions |

```text
使用 literature-library-eval 评估我的文献库，
判断它能否支撑"工业视觉缺陷检测的跨产线迁移"的系统综述。
```

The AI will:

1. Confirm your research question, review type, domain, and boundaries (max 3 questions)
2. Accept JSON, CSV, RIS, or BibTeX through `import_library.py`; review the generated import preview before auditing.
3. Execute single-round diagnostic search, help you iterate the query, compute all A–F indicators, and produce the audit package

The full example report is a reference fixture, not a prerequisite for getting started.

### One-command first pass

For a low-friction first run, use the autopilot. It creates a source-aware query plan, runs the resumable workflow, generates an active screening queue, and writes AI suggestions separately from formal screening decisions:

```bash
python scripts/autopilot.py \
  --question "How do robot localization methods handle low-light sensing?" \
  --out first-pass
```

This creates `first-pass/onboarding.html`: a small handoff with the saved question and next command. When you confirm the question is in scope, run:

```bash
python scripts/autopilot.py \
  --question "How do robot localization methods handle low-light sensing?" \
  --scope-status in_scope \
  --library library.json \
  --out first-pass
```

`--scope-status in_scope` is an explicit confirmation that this is an engineering question within the Skill's scope; without it, autopilot produces an onboarding plan rather than inventing a full A-F verdict. `--library` is optional: a confirmed run without one creates an empty starter library and reports only what is assessable. OpenAlex is used when its key is available; authorized arXiv, Crossref, and Europe PMC adapters remain available without it. Autopilot suggestions are never formal inclusion decisions.

## Six-Dimension Framework

21 indicators. 24 for umbrella reviews. No composite score. Every dimension stands alone — a perfect A1 cannot hide a broken F1.

| Dim | Question | What we measure |
|:---:|---|---|
| **A · Coverage** | Did we find the known must-include works? | Benchmark recall, search sensitivity, multi-source lower bound |
| **B · Saturation** | Is the search still growing? | GGR, DRR, pathway completion + independent validation |
| **C · Balance** | Are topics and sources skewed? | Top-share, CV, Gini, Shannon entropy, author concentration, opposing viewpoints |
| **D · Recency** | Does the library reflect the current state? | Source freshness, recent-share (profile-aware), frontier coverage |
| **E · Impact** | Are core citations and venues covered? | h-core, Tier-1 venue coverage *(background signals only)* |
| **F · Usability** | Can you actually write the review? | Query reproducibility, abstract/fulltext access, dedup, provenance, retraction checks |

→ [Full methodology](docs/methodology.md) · [Indicator registry](schemas/indicator-registry.json) · [Standards guide](references/user-standards-guide.md)

## What You Get

The user-facing report is HTML only (`audit.html`). JSON, manifest, and input
snapshots remain machine-readable reproducibility artifacts.

Every run produces a self-contained, reproducible audit package:

```text
out/
├── audit.html        ← Human-readable report with prioritized actions
├── audit.html        ← Rendered HTML
├── audit.json        ← Machine-readable with full indicator register
├── manifest.json     ← sha256, git commit, Python version
├── inputs/           ← All inputs copied with hash-prefixed names
└── .tmp/             ← Resolved config (auto-generated)
```

→ [Understanding outputs](docs/outputs.md)

→ [User workflow](docs/user-workflow.md) · [Quality assurance](docs/quality-assurance.md)

## Can / Cannot

| Can do | Cannot do |
|---|---|
| Diagnose coverage, saturation, balance, recency, usability | Replace domain-expert inclusion judgment |
| Produce traceable, reproducible run packages | Guarantee global literature exhaustiveness |
| Estimate multi-source lower bounds under explicit assumptions | Replace AMSTAR-2, ROBIS, or critical appraisal tools |
| Auto-dedup, field completion, search expansion, basic statistics | Auto-decide "should this paper be included?" |
| Offer downgraded service for out-of-scope questions | Evaluate internal validity of individual studies |

## Design Principles

- **No composite score.** Six peer dimensions — a perfect A1 doesn't hide a broken F1. (Contrast: ScholarEval's weighted average suits finished-paper evaluation but would obscure library-readiness diagnostics.)
- **Evidence-graded.** Every conclusion: `measured · estimated · automated-screening · manual-verification-required · not_assessable`.
- **Thresholds are signals, not verdicts.** All defaults documented with rationale; all user-overridable.
- **Privacy-first.** No absolute paths, no API keys in prompts, hash-prefixed input file names.
- **Reproducible.** Every run records git commit, script sha256, Python version, all input hashes.

## Scope

**Supported**: CS & AI, Electronics, Mechanical, Civil, Materials, Chemical, Biomedical, Energy, Environmental, Aerospace, Transportation engineering.

**Not supported**: Pure mathematics, pure physics, pure chemistry, clinical medicine, basic life sciences.

**Review types**: systematic · scoping · narrative · rapid · umbrella

Out-of-scope questions receive downgraded service (metadata health check / search design) — never a blunt rejection.

→ [Intake protocol](references/intake-protocol.md) · [Search strategy protocol](references/search-strategy-protocol.md)

## Install

### Claude Code / Desktop

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.claude/skills/literature-library-eval
```

Restart Claude. That's it.

On Windows PowerShell, use:

```powershell
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git `
  "$env:USERPROFILE\.claude\skills\literature-library-eval"
```

### Codex

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.codex/skills/literature-library-eval
```

On Windows PowerShell, use:

```powershell
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git `
  "$env:USERPROFILE\.codex\skills\literature-library-eval"
```

### Requirements

| Dependency | Why |
|---|---|
| Python 3.10+ | `run_audit.py`, `search_for_eval.py`, `search_iterator.py`, `optimization.py`, `quality_optimization.py`, `experiment_attribution.py`, `evalset_audit.py` |
| Internet access | OpenAlex, Crossref, arXiv (open-access APIs) |
| **No credentials in prompts** | Open sources may still require a preconfigured API key; never paste keys into chat or output artifacts |

**Development:** `pip install -r requirements-dev.txt` adds `pytest` and `jsonschema` for running the test suite.

The local Demo uses the Python standard library and the files included in this
repository. Network access and source credentials are only relevant when you
choose an online search or metadata-enrichment workflow.

## Documentation

| Audience | Resources |
|---|---|
| **New users** | [README.zh-CN.md](README.zh-CN.md) · [Quickstart](#quickstart) |
| **Deep dive** | [Methodology](docs/methodology.md) · [Architecture](docs/architecture.md) · [Outputs](docs/outputs.md) |
| **Integration** | [Integrations](docs/integrations.md) · [Zotero / databases / companion skills](docs/integrations.md) |
| **Standards** | [User standards guide](references/user-standards-guide.md) · [Indicator registry](schemas/indicator-registry.json) |
| **AI Agents** | [SKILL.md](SKILL.md) · [Intake protocol](references/intake-protocol.md) · [Search protocol](references/search-strategy-protocol.md) |
| **Developers** | [run-config-schema.json](schemas/run-config-schema.json) · [Architecture](docs/architecture.md) · [tests/](tests/) |
| **Contributors** | [Contributing guide](CONTRIBUTING.md) · [Launch kit](docs/launch-kit.md) · [Issue templates](https://github.com/Carrot123343r3f/literature-library-eval-skill/issues/new/choose) |

### Optional paper-value-ranking module

`scripts/run_paper_evaluation.py` (`rank_papers.py` remains a compatible entry point) is independent from the A–F readiness audit. It routes each paper by study design, separates eligibility, appraisal, reproducibility, integrity, bibliometric signals, and marginal review contribution, and then produces three transparent rankings. It never treats citation count or venue as a research-quality verdict or emits a cross-design universal quality score. See [the V2 evidence and contract note](references/paper-evaluation-v2.md).

```bash
python scripts/run_paper_evaluation.py --library library.json --context context.json --run-config run-config.json --out paper-evaluation
```

For a first pass on one article, use a JSON object with `--paper`:

```bash
python scripts/run_paper_evaluation.py --paper one-paper.json --context context.json --run-config run-config.json --out one-paper-evaluation
```

This keeps the evidence boundaries explicit: `metadata_priority` means “read/verify earlier”, not “high quality”. Method appraisal, reproducibility, integrity and review contribution remain separate, and the report exposes the components behind a reading-priority signal.

Single-paper mode performs authorized metadata enrichment by default when `automation.allow_search=true`. Use `--external-candidates saved.json` for an offline candidate snapshot, `--external-search` for live candidate discovery, or `--offline` only after the user explicitly chooses fully local execution.

The search diagnostic uses every source authorized in `automation.allowed_sources`: OpenAlex, arXiv, Crossref, and Europe PMC. OpenAlex is used when an `OPENALEX_API_KEY` is configured; without it, authorized free-source adapters can still run. Citation counts are only used when the selected source provides them, and source coverage is recorded in `search_meta.json`. Paper-evaluation external discovery remains OpenAlex-specific and requires its separate permission and key. A saved candidate snapshot can be supplied with `--external-candidates` for reproducible/offline reruns.

## Roadmap

| Phase | What | Status |
|---|---|---|
| v1.0 | Core A–F (21+3 indicators), CLI, 5 review types, 9 engineering profiles | ✅ Current |
| v1.x | Scopus/WoS/IEEE adapters and Semantic Scholar API | 🔜 Next |
| v1.1 | `run_full_audit.py` — resumable guided workflow (import→collect→screen→audit→actions) | ✅ |
| Future | `review-manuscript-audit` — PRISMA compliance, citation integrity, study quality tool matching | 💡 Planned |

## Contributing

MIT License. Issues and pull requests welcome. Areas particularly valuable:

- Zotero API integration and institutional-source adapters
- Source adapters (Scopus, Web of Science, IEEE Xplore)
- Internationalization of report output
- Additional engineering profiles and venue mappings

See [LICENSE](LICENSE) for terms.

---

<p align="center">
  Not "is your library good enough?" — <strong>what should you do next?</strong>
</p>
