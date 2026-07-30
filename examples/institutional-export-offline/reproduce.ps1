$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$example = $PSScriptRoot
$env:PYTHONUTF8 = "1"
$out = Join-Path $example ".local-output"
& python (Join-Path $repo "scripts\import_source_snapshots.py") --manifest (Join-Path $example "institutional-exports.json") --out (Join-Path $out "institutional-snapshot.json")
& python (Join-Path $repo "scripts\run_audit.py") --run-config (Join-Path $example "run-config.json") --out (Join-Path $out "audit")
$audit = Get-Content -Raw (Join-Path $out "audit\audit.json") | ConvertFrom-Json
if ($audit.coverage.a3.status -ne "estimated_lower_bound" -or $audit.coverage.a3.deduplicated_candidate_lower_bound -ne 3) { throw "Teaching expectation failed: A3 lower bound should be 3." }
Write-Host "Success: institutional exports are in the audit; A3 lower bound = 3. Next: create a 10–20 paper independent must-include set, run forward/backward citation tracking, and save each query's fields/date/filters."
