# Offline institutional-export audit: reproducible example

This self-contained example simulates an engineering review of vision-based
surface-defect inspection. It uses local IEEE Xplore and Scopus-style exports;
all records, DOI values, queries, and counts are synthetic. No network access,
credentials, or commercial API is required.

## Reproduce

From the repository root in PowerShell:

```powershell
./examples/institutional-export-offline/reproduce.ps1
```

The script first validates and normalizes the two raw exports into
`outputs/institutional-snapshot.json`, then runs the A–F audit with the
persisted `run-config.json`. Open `outputs/audit/audit.html` afterwards.

## What the result demonstrates

- A3 is an `estimated_lower_bound`: both source exports have a documented,
  uncapped total and use the same scope and DOI deduplication rule.
- The report intentionally retains `not_assessable` outcomes for A1/A2/B/F1
  because a two-database export alone cannot establish recall, saturation, or
  reproducible full search evidence.
- The snapshot includes per-source query text, scope, timestamps, totals,
  export limits, completeness basis, import quality, and SHA-256 values.

This is a teaching example, not evidence that the simulated topic is covered.
