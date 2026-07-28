# Workflow kernel and contract layer

This document is the implementation contract for the architecture kernel.
The public entry point remains `scripts/run_full_audit.py`; the kernel lives
in `scripts/lle_core/` so existing command-line tools can migrate gradually.

## Core objects

| Object | Responsibility | Durable representation |
|---|---|---|
| `ReviewConfig` | User-confirmed scope, permissions and output policy | `run-config.json` |
| `WorkflowState` | Current stage, step statuses, failures and resume signature | `workflow-state.json` |
| `ArtifactRecord` | Relative path, SHA-256, size, producer and artifact kind | `workflow-state.json.artifacts` |
| `StageContract` | Declared inputs, outputs, human gate and recovery semantics | `lle_core.contracts` / `stage-contract-schema.json` |

## Stage lifecycle

```text
created
  -> config_validated
  -> library_ready
  -> collection_ready
  -> screening_ready
  -> audit_ready
  -> report_ready
  -> completed
```

Stages may be skipped when the user does not request an optional capability,
but they may not move backward. A failed run remains resumable only after the
failed step and its artifacts are inspected. `--resume` requires the same
input signature; `--force` starts from the current filesystem while preserving
the prior state file until the next atomic write.

## Artifact rules

1. Output artifacts must exist before a stage is marked complete.
2. Output paths must remain inside the workflow output directory.
3. Every output records its SHA-256, size, producer and kind.
4. External inputs such as the separate optimization workspace are validated
   for existence but are not copied into the audit artifact tree.
5. Human-readable reports and machine-readable evidence remain separate.

## Migration rule for new modules

New workflow modules should expose a small adapter with:

```text
validate_inputs() -> errors
execute() -> output paths
validate_outputs() -> errors
```

The adapter then calls `WorkflowContext.complete_step(...)`. It must not create
another `workflow-state.json`, another artifact manifest format, or an implicit
source of truth for scope and permissions.
