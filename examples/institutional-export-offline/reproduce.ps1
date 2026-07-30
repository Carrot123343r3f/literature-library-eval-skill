$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$example = $PSScriptRoot
$env:PYTHONUTF8 = "1"
& python (Join-Path $repo "scripts\import_source_snapshots.py") --manifest (Join-Path $example "institutional-exports.json") --out (Join-Path $example "outputs\institutional-snapshot.json")
& python (Join-Path $repo "scripts\run_audit.py") --run-config (Join-Path $example "run-config.json") --out (Join-Path $example "outputs\audit")
