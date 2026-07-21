# Methodology: A–F Six-Dimension Framework

## Why This Exists

Most literature reviews fail before writing begins — not because the writing is bad, but because the evidence base cannot support the conclusions. You've probably experienced this yourself:

- You open a new research area and can't find a clear entry point — everything seems scattered.
- You spend weeks collecting papers, only to worry you've missed an entire sub-direction.
- You finish a review draft, send it to a supervisor or reviewer, and get told "you're missing X, Y, Z" — after months of work.
- You write the review first, then realize the search was incomplete — wasting time on a manuscript that can't be defended.
- You search one database thoroughly and think you're done — but a different database would have surfaced entirely different papers.

**Engineering Literature Library Audit** addresses the problem upstream: **before writing, verify that the evidence base is structurally sound.** It answers a specific question that sits between "did I search enough?" and "is my paper ready for publication?":

> Given this research question, this review type, and this engineering domain — can the literature library currently support a credible review? And if not, what exactly needs to be fixed?

It does not replace AMSTAR-2, ROBIS, PRISMA, or any critical appraisal tool. It does not judge whether individual studies are internally valid. It audits **readiness** — the structural preconditions for a defensible review.

## The Six Dimensions

Six dimensions, peer-level, no composite score. A perfect A1 does not hide a broken F1 — in library readiness diagnosis, identifying weak points has more action value than assigning an overall label. (Contrast: ScholarEval's 8-dimension weighted average is appropriate for evaluating a finished paper's overall quality but would obscure actionable diagnostics in a library-readiness context — a library with perfect benchmark recall but zero query reproducibility would get a misleading "3.8/5.0".)

### A · Coverage — Did we find the known must-include works?

Three layers, each with its own evidence status:

| Layer | Question | What it is | What it is not |
|---|---|---|---|
| A1 Benchmark Recall | Are confirmed anchor papers in the library? | Stable-ID match against a user-supplied benchmark set | "The search was complete" |
| A2 Search Sensitivity | Does the query retrieve known related work? | Stable-ID match between query hits and a gold set | "The gold set is representative" |
| A3 Multi-Source Lower Bound | At minimum, how many unique candidates exist across sources? | Deduplicated union of ≥2 source snapshots | "How many were missed" |

**A2's gold set must be split into a dev set and an independent validation set** (see Search Strategy Protocol). Without an independent validation set, A2 evidence is `estimated`, not `measured` — the query may simply have memorized the dev set.

### B · Saturation — Is the search still growing?

Three conditions must hold simultaneously:
1. **B1 GGR**: Core growth rate < 2% across two screened rounds
2. **B2 DRR**: All independent pathways show marginal yield < 5%
3. **B3 Process Evidence**: All planned pathways completed + independent validation passed

**Critical**: B2's "pathways" must be truly independent discovery channels (database search, backward citation, forward citation, related articles, standards), not query variants within the same database. **A2 stop ≠ B stop** — a query can recall all known work while the result set still contains undiscovered high-relevance items.

### C · Balance — Are topics and sources skewed?

Five parameters, none a substitute for the others: Top-share, CV, Gini, Shannon Hn, TVD. C1 now checks for **opposing viewpoints** (numerical balance ≠ content balance) and C2 includes **author concentration** (single author >25% suggests group bias).

### D · Recency — Does the library reflect the current state?

Profile-aware: AI/communications (3 years, 40%), mechanical/materials (5 years, 35%), civil/energy/aerospace (7 years, 30%). D2 degrades to warning when year completeness <50% — the numerator cannot hide missing data.

### E · Impact Signals — Background context only

h-core and Tier-1 venue coverage. No hard thresholds. High citations ≠ high quality. Actual research quality assessment requires design-appropriate critical appraisal tools.

### F · Usability — Can you actually write the review?

From query reproducibility (F1 — the only hard blocking item) through fulltext access, deduplication, provenance, to retraction checking. F5 now includes a **descriptive listing risk** diagnostic — if inclusion decisions lack topic labels, the review risks becoming a sequential summary rather than thematic synthesis.

## Evidence Statuses

Every conclusion is evidence-graded:

| Status | Meaning |
|---|---|
| `measured` | Reproducible inputs, independently verifiable |
| `estimated` | Based on explicit assumptions |
| `automated-screening` | Rule-based, not human-verified |
| `manual-verification-required` | Needs human decision |
| `not_assessable` | Missing inputs — this is *actionable*, not failure |

## Limitations

- All thresholds are reference values, not universal laws
- Does not evaluate internal validity of individual studies
- Automated classification requires human spot-checking
- h-core and Tier-1 are diagnostic background only
- Capture-recapture validity requires approximate source independence

## Key References

- AMSTAR-2: Shea et al. (2017), BMJ, 358, j4008
- ROBIS: Whiting et al. (2016), J Clin Epidemiol, 69, 225–234
- ScholarEval: Moussa et al. (2025), arXiv:2510.16234
- PRISMA 2020: Page et al., BMJ, 372, n71
