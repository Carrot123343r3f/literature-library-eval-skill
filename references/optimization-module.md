# Optimization Module

This is the reusable optimization layer for the literature workflow. It is
based on SkillHone's hard eval/skill split and persistent decision history.

## Three-boundary contract

Each optimization run has two repositories and one separate run workspace:

- Skill Repo: the skill folder being improved.
- Eval Repo: benchmark/validation data, scorers, contracts, and gold labels.
  It must be outside the Skill Repo and is not readable by the optimizer.
- Run Workspace: candidates, observations, manifests, and decision history.
  It must be outside both repositories.

The default recommended locations are:

```text
C:\Users\Qt\.claude\skills\literature-library-eval  # Skill Repo
C:\Users\Qt\.claude\skill-evals\literature-library-eval # Eval Repo
C:\Users\Qt\.claude\skill-runs\literature-library-eval\<run-id> # Run Workspace
```

Create the standard workspace with:

```bash
python scripts/optimization.py init-workspace \
  --skill-repo C:\Users\Qt\.claude\skills\literature-library-eval \
  --eval-repo C:\Users\Qt\.claude\skill-evals\literature-library-eval \
  --run-root C:\Users\Qt\.claude\skill-runs\literature-library-eval\opt-001 \
  --topic "industrial defect detection" \
  --objective "improve search recall without unacceptable noise"
```

The command writes `workspace-manifest.json`; every run must pass its path and
role checks before optimization starts.

Within the Run Workspace, the evaluator writes only aggregate observations to
`observations/`, while the optimizer writes candidates and decision history.
The transport contract is `observation-v1`; raw validation records and stable
identifiers are rejected by the writer.

The optimization store is analogous to SkillHone's public skill surface; the
validation store is analogous to its private evaluation contract. A score alone
is not an explanation. Each round must persist:

`diagnosis -> candidate_revision -> redacted_evidence -> outcome`

## Candidate lifecycle

Every proposed revision has an auditable state:

```text
proposed -> under_evaluation -> accepted
                       ├──────> rejected
                       └──────> deferred
accepted -> reverted
```

Only an accepted candidate becomes the current candidate. A rejected or
reverted candidate remains on disk and in `candidate-events.jsonl`; it is never
silently deleted. Use `history-search` before proposing a new change and use
`rollback` when a later regression invalidates an accepted revision.

## Evaluation stages and metrics

The standard stages are:

- `probe`: fast practice feedback used for diagnosis;
- `pr_val`: candidate merge gate;
- `regression`: checks that existing capabilities did not degrade;
- `heldout`: final validation, never used to formulate a revision.

The module keeps metrics as a vector rather than a single score. The default
objective considers validation recall, precision, discovery yield, source
coverage, cost, and duration. Constraints include regression tolerance and
optional cost/duration ceilings. `metric-evaluate` returns the components,
constraint violations, and an `eligible` decision without hiding the individual
metrics.

## Invocation

For compatibility, the short `init` command still creates a self-contained
local run. New workflows should use `init-workspace` so the repository
boundaries are enforced.

Create a run when a workflow needs optimization but the user did not provide a
complete baseline library, gold set, vocabulary, query plan, or prior decision
history:

```bash
python scripts/optimization.py init --output run/optimization \
  --topic "industrial defect detection" \
  --objective "improve search recall without unacceptable noise"
```

Put development and held-out records in their respective stores, then record
one atomic iteration at a time:

```bash
python scripts/optimization.py record --run run/optimization \
  --iteration iteration-v2.json
python scripts/optimization.py validate --run run/optimization --strict
python scripts/optimization.py status --run run/optimization
```

Useful lifecycle operations:

```bash
python scripts/optimization.py history-search --run run/optimization \
  --query "OpenAlex query field misses transfer-learning papers"
python scripts/optimization.py candidate-status --run run/optimization \
  --candidate-id c2 --state under_evaluation
python scripts/optimization.py rollback --run run/optimization \
  --candidate-id c2 --reason "regression on source coverage"
```

The main audit workflow can enforce the contract without changing the default
behavior of older runs:

```bash
python scripts/run_full_audit.py run --run-config run-config.json \
  --out audit-run --optimization-run run/optimization
```

When `optimization.run_root` is present in `run-config.json`, the same gate is
applied automatically. A failed contract gate stops before the A–F report is
produced.

## Rules

1. Diagnose before changing anything; distinguish infrastructure, data,
   workflow, and instruction failures.
2. One iteration contains one focused change type. A query synonym addition,
   field change, new source, screening-rule change, and helper-script change
   are separate iterations.
3. Validation evidence must be redacted. Store only aggregate metrics and
   non-identifying failure patterns in the optimization history.
4. Prefer the best eligible candidate, not the latest candidate. A regression
   must leave a record and must not silently replace the best candidate.
5. Stop after the held-out score reaches the applicable threshold and plateaus,
   or after the configured iteration limit. Optimization stop and literature
   saturation stop remain separate decisions.
6. The held-out stage may return aggregate metrics to the controller, but never
   raw validation records, identifiers, questions, targets, or traces.

For search optimization, `references/search-strategy-protocol.md` supplies the
domain-specific dev/validation construction, query syntax mapping, pathway
rules, and A2/B stop criteria. `scripts/search_iterator.py` remains a
compatibility validator for legacy iteration records; new orchestrators should
write the optimization module's decision-history contract. Use
`python scripts/search_iterator.py sync` to persist validated search rounds in
the shared run rather than maintaining a second history format.

## Quality optimization utilities

The companion `scripts/quality_optimization.py` adds three maintenance loops:

```bash
python scripts/quality_optimization.py counterexample \
  --run run/optimization --item counterexample.json
python scripts/quality_optimization.py screen-queue \
  --candidates candidates.json --out screening-queue.json --budget 30
python scripts/quality_optimization.py canary \
  --baseline baseline-metrics.json --current current-metrics.json \
  --out canary.json
```

Counterexamples preserve false positives, false negatives, boundary cases,
source conflicts, and tool failures. The screening queue ranks human-review
items by uncertainty, impact, source conflict, missingness, and novelty; it is
a prioritization aid, not an automatic inclusion decision. Canary drift is a
maintenance signal and does not by itself change A–F conclusions.

Counterexample records also create a redacted `defer` entry in decision
history, keeping failure learning and candidate evolution in one trace. Canary
input may be a flat metric object or `{metrics, metadata}`; changes to query
hash, source, schema, or completion metadata are reported as metadata drift.

## Additional components

Two independent analysis components extend the optimization loop:

```bash
python scripts/experiment_attribution.py \
  --baseline baseline-metrics.json \
  --candidates candidate-metrics.json \
  --out attribution.json

python scripts/evalset_audit.py \
  --dev dev-set.json --validation validation-set.json \
  --out evalset-audit.json
```

`experiment_attribution.py` compares each candidate with its parent or the
baseline, reports metric deltas and regressions, and identifies a Pareto front.
It is an attribution report, not a causal proof. `evalset_audit.py` checks
stable-ID overlap, duplicates, minimum sizes, and missing identifiers without
printing the underlying evaluation records.
