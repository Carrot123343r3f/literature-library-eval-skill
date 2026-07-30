# Offline institutional-export audit: reproducible example

This self-contained example simulates an engineering review of vision-based
surface-defect inspection. It uses local IEEE Xplore and Scopus-style exports;
all records, DOI values, queries, and counts are synthetic. No network access,
credentials, or commercial API is required.

## Reproduce

From the repository root in PowerShell (without changing your global execution
policy):

```powershell
powershell -ExecutionPolicy Bypass -File .\examples\institutional-export-offline\reproduce.ps1
```

Cross-platform alternative: `python examples/institutional-export-offline/reproduce.py`.

The script first validates and normalizes the two raw exports into
`outputs/institutional-snapshot.json`, then runs the A–F audit with the
persisted `run-config.json`. Open `outputs/audit/audit.html` afterwards.
It also checks the teaching expectations and prints a short success message.

## What the result demonstrates

- A3 is an `estimated_lower_bound`: both source exports have a documented,
  uncapped total and use the same scope and DOI deduplication rule.
- The report intentionally retains `not_assessable` outcomes for A1/A2/B/F1
  because a two-database export alone cannot establish recall, saturation, or
  reproducible full search evidence.
- The snapshot includes per-source query text, scope, timestamps, totals,
  export limits, completeness basis, import quality, and SHA-256 values.

This is a teaching example, not evidence that the simulated topic is covered.

## Concrete next tasks after this example

1. Create a 10–20 paper independent must-include set for A1/A2.
2. Complete one backward- and one forward-citation pass, screen the results,
   and log additions before assessing B saturation.
3. Add topic/evidence-role tags and save every query's fields, date, filters,
   and result count.
