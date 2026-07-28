"""Durable runtime context for workflow orchestration."""
from __future__ import annotations

import json
import os
import pathlib

from .artifacts import artifact_record
from .models import WorkflowState
from .state_machine import advance


def _dump(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class WorkflowContext:
    """One run's configuration, state, and artifact lineage."""

    def __init__(self, root, run_id, run_signature, state):
        self.root = pathlib.Path(root).resolve()
        self.state_path = self.root / "workflow-state.json"
        self.run_id = run_id
        self.run_signature = run_signature
        self.state = state

    @classmethod
    def open(cls, root, run_signature, resume=False, force=False):
        root = pathlib.Path(root).resolve(); root.mkdir(parents=True, exist_ok=True)
        state_path = root / "workflow-state.json"
        if state_path.exists() and resume:
            state = WorkflowState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
            if state.run_signature and state.run_signature != run_signature and not force:
                raise ValueError("workflow inputs changed; use a new run or --force")
            return cls(root, state.run_id, run_signature, state)
        run_id = f"run-{os.urandom(6).hex()}"
        return cls(root, run_id, run_signature, WorkflowState(run_id, run_signature))

    def persist(self):
        self.state.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        _dump(self.state_path, self.state.as_dict())

    def complete_step(self, name, outputs, status="complete"):
        records = {}
        for output in outputs:
            record = artifact_record(self.root, output, producer=name)
            records[record["path"]] = record
        self.state.steps[name] = status
        self.state.artifacts.update(records)
        self.persist()

    def advance(self, stage):
        advance(self.state, stage)
        self.persist()

    def fail(self, name, message):
        self.state.steps[name] = "failed"
        self.state.errors.append({"step": name, "message": str(message)[:500]})
        self.state.status = "failed"
        self.persist()
