# Engineering Literature Library Audit

<p align="center">
  <strong>Most literature reviews fail before the writing begins.</strong>
</p>

<p align="center">
  They fail when the library is incomplete, the search cannot be reproduced, or apparent saturation is only an artifact of one database. An audit that runs <em>before</em> you write saves months of rework — and a manuscript that cannot be defended.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-9%2F9%20passing-22c55e" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License">
  <img src="https://img.shields.io/badge/indicators-21%20(%2B3%20umbrella)-8b5cf6" alt="Indicators">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Platform">
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

## Quickstart

```text
使用 literature-library-eval 评估我的文献库，
判断它能否支撑"工业视觉缺陷检测的跨产线迁移"的系统综述。
```

The AI will:

1. Confirm your research question, review type, domain, and boundaries (max 3 questions)
2. Accept your library (Zotero export, JSON, or let the AI design a search strategy)
3. Execute searches, compute indicators, and produce an audit package

```text
Input → Scope → Search → Dedup → Screen → Iterate → A–F Compute → Audit Package
```

→ [View example report](example-report.md)

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

Every run produces a self-contained, reproducible audit package:

```text
out/
├── audit.md          ← Human-readable report with prioritized actions
├── audit.html        ← Rendered HTML
├── audit.json        ← Machine-readable with full indicator register
├── manifest.json     ← sha256, git commit, Python version
├── inputs/           ← All inputs copied with hash-prefixed names
└── .tmp/             ← Resolved config (auto-generated)
```

→ [Understanding outputs](docs/outputs.md)

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

### Codex

```bash
git clone https://github.com/Carrot123343r3f/literature-library-eval-skill.git \
  ~/.codex/skills/literature-library-eval
```

### Requirements

| Dependency | Why |
|---|---|
| Python 3.10+ | `run_audit.py`, `search_for_eval.py`, `search_iterator.py` |
| Internet access | OpenAlex, Crossref, arXiv (open-access APIs) |
| **No API keys** | All data sources are open-access |

## Documentation

| Audience | Resources |
|---|---|
| **New users** | [README.zh-CN.md](README.zh-CN.md) · [Quickstart](#quickstart) · [Example report](example-report.md) |
| **Deep dive** | [Methodology](docs/methodology.md) · [Architecture](docs/architecture.md) · [Outputs](docs/outputs.md) |
| **Integration** | [Integrations](docs/integrations.md) · [Zotero / databases / companion skills](docs/integrations.md) |
| **Standards** | [User standards guide](references/user-standards-guide.md) · [Indicator registry](schemas/indicator-registry.json) |
| **AI Agents** | [AI Guide](AI_GUIDE.md) · [Intake protocol](references/intake-protocol.md) · [Search protocol](references/search-strategy-protocol.md) |
| **Developers** | [run-config-schema.json](schemas/run-config-schema.json) · [Architecture](docs/architecture.md) · [tests/](tests/) |

## Roadmap

| Phase | What | Status |
|---|---|---|
| v1.0 | Core A–F (21+3 indicators), CLI, 5 review types, 9 engineering profiles | ✅ Current |
| v1.x | BibTeX/RIS/CSV import, Scopus/WoS/IEEE adapters, Crossref/Semantic Scholar API | 🔜 Next |
| v2.0 | `run_full_audit.py` — end-to-end orchestrator (search→screen→audit→report) | 📋 Planned |
| Future | `review-manuscript-audit` — PRISMA compliance, citation integrity, study quality tool matching | 💡 Planned |

## Contributing

MIT License. Issues and pull requests welcome. Areas particularly valuable:

- Format importers (BibTeX, RIS, CSV, Zotero API)
- Source adapters (Scopus, Web of Science, IEEE Xplore)
- Internationalization of report output
- Additional engineering profiles and venue mappings

See [LICENSE](LICENSE) for terms.

---

<p align="center">
  Not "is your library good enough?" — <strong>what should you do next?</strong>
</p>
