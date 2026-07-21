# Literature Library Eval

<p align="center">
  <strong>帮工程研究者把模糊的文献库，转变为一份可解释、可复跑、知道下一步该补什么的综述准备度诊断。</strong>
</p>

<p align="center">
  <em>An engineering literature-library readiness diagnostic — not a single score, not an automatic pass/fail.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/tests-9%2F9%20passing-22c55e" alt="Tests">
  <img src="https://img.shields.io/badge/license-MIT-3b82f6" alt="License MIT">
  <img src="https://img.shields.io/badge/coverage-A–F%20(%E5%85%AD%E7%BB%B4%2021%2B3%20%E5%AD%90%E9%A1%B9)-8b5cf6" alt="A-F 6-dim 24-indicator">
  <img src="https://img.shields.io/badge/platform-Claude%20%7C%20Codex-6366f1" alt="Claude | Codex">
</p>

---

## Quickstart

```text
使用 literature-library-eval 评估我的文献库，
判断它能否支撑"工业视觉缺陷检测的跨产线迁移"的系统综述。
```

| Step | What happens |
|:---:|---|
| 1 | **AI 确认范围**：自动判断工程领域、综述类型、边界——一次最多三个问题 |
| 2 | **提供文献库**：Zotero / JSON / CSV，或者让 AI 帮你设计检索策略 |
| 3 | **得到诊断报告**：优先级行动 + 六维总表 + 输入快照 + 可复跑包 |

→ [查看示例报告](example-report.md)

## What You Get

Every run produces a **self-contained audit package**:

```text
out/
├── audit.md          ← human-readable report with prioritized actions
├── audit.html        ← rendered HTML
├── audit.json        ← machine-readable with full indicator register
├── manifest.json     ← sha256, git commit, Python version — every input accounted for
├── inputs/           ← all input files copied with hash-prefixed names
└── .tmp/             ← resolved config (auto-generated)
```

The report opens with an **input evidence table** — so you immediately know what data is available and what is missing — followed by the **top 3 priority actions** (blocking items first).

## Six-Dimension Framework

| Dim | Question | What we measure |
|:---:|---|---|
| **A · Coverage** | Did we find the known must-include works? | Benchmark recall, search sensitivity, multi-source lower bound |
| **B · Saturation** | Is the search still growing? | GGR, DRR, pathway completion + independent validation |
| **C · Balance** | Are topics and sources skewed? | Top-share, CV, Gini, Shannon entropy, topic–source cross-tabulation |
| **D · Recency** | Does the library reflect current research? | Source freshness, recent-share (profile-aware), frontier coverage |
| **E · Impact Signals** | Are core citations and venue channels covered? | h-core, Tier-1 venue coverage *(background signals only — not a quality verdict)* |
| **F · Usability** | Can you actually write the review? | Query reproducibility, abstract/fulltext access, dedup, provenance, retraction checks |

**21 indicators** (24 for umbrella reviews). No composite score. `not_assessable` means *"missing input — here's the cheapest way to fix it."*

→ [Full standards guide](references/user-standards-guide.md) · [Indicator dictionary](references/indicator-dictionary.md) · [Engineering profiles](references/engineering-profiles.md)

## Scope

| Supported | Not supported |
|---|---|
| CS & AI, Electronics, Mechanical, Civil, Materials | Pure mathematics, physics, chemistry |
| Energy, Environmental, Chemical, Aerospace, Transport, Biomedical Engineering | Clinical medicine, basic life sciences |

**Review types**: systematic · scoping · narrative · rapid · umbrella

Out-of-scope questions receive **downgraded service** (metadata health check / search design) — never a blunt rejection.

→ [Intake protocol](references/intake-protocol.md)

## Can / Cannot

| Can do | Cannot do |
|---|---|
| Diagnose coverage, saturation, balance, recency, usability | Replace domain-expert inclusion judgment |
| Produce traceable, reproducible run packages | Guarantee global literature exhaustiveness |
| Estimate multi-source lower bounds under explicit assumptions | Replace AMSTAR-2, ROBIS, or other critical appraisal tools |
| Auto-dedup, field completion, search expansion, basic statistics | Auto-decide "should this paper be included?" |
| Offer downgraded service for out-of-scope questions | Evaluate the internal validity of individual studies |

## Design Principles

- **No composite score.** Six dimensions are peer-level — a perfect A1 doesn't hide a broken F1.
- **Evidence-graded.** Every conclusion is `measured · estimated · automated-screening · manual-verification-required · not_assessable`.
- **Thresholds are signals, not verdicts.** All defaults are documented with rationale; all can be overridden by the user.
- **privacy-first.** No absolute paths in manifests, no API keys in prompts, input files are copied with hash-prefixed names.
- **Reproducible.** Every run records git commit, script sha256, Python version, and all input hashes.

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
| Python 3.10+ | Local scripts (`run_audit.py`, `search_for_eval.py`, etc.) |
| Internet access | Open-source APIs (OpenAlex, Crossref, Europe PMC, arXiv) for online search |
| **No API keys** | All data sources are open-access |

## Documentation

| Audience | Resources |
|---|---|
| **Users** | [Standards guide](references/user-standards-guide.md) · Input evidence table (in every report) |
| **AI Agents** | [AI Guide](AI_GUIDE.md) · [Intake protocol](references/intake-protocol.md) |
| **Developers** | [run-config-schema.json](references/run-config-schema.json) · [tests/](tests/) · [scripts/](scripts/) |

## Contributing

MIT License. Issues and pull requests are welcome.

Areas where contributions are particularly valuable:

- Format importers (BibTeX, RIS, CSV, Zotero API)
- Source adapters (Scopus, Web of Science, IEEE Xplore)
- `run_full_audit.py` — end-to-end orchestrator
- Internationalization of report output
- Additional engineering profiles and venue mappings

See [LICENSE](LICENSE) for terms.

---

<p align="center">
  Not &ldquo;is your library good enough?&rdquo; — <strong>what should you do next?</strong>
</p>
