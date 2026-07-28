"""Stable domain objects shared by workflow nodes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


WORKFLOW_STAGES = (
    "created", "config_validated", "library_ready", "collection_ready",
    "screening_ready", "audit_ready", "report_ready", "completed",
)
TERMINAL_STAGES = {"completed"}


def now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowState:
    """Durable, resumable state for one end-to-end workflow run."""

    run_id: str
    run_signature: str
    stage: str = "created"
    status: str = "active"
    steps: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def as_dict(self):
        return {
            "schema_version": "2.0",
            "run_id": self.run_id,
            "run_signature": self.run_signature,
            "stage": self.stage,
            "status": self.status,
            "steps": self.steps,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("workflow state must be an object")
        return cls(
            run_id=str(value.get("run_id") or "unknown"),
            run_signature=str(value.get("run_signature") or ""),
            stage=value.get("stage") or _infer_stage(value.get("steps", {})),
            status=value.get("status") or "active",
            steps=dict(value.get("steps") or {}),
            artifacts=dict(value.get("artifacts") or {}),
            errors=list(value.get("errors") or []),
            created_at=value.get("created_at") or now(),
            updated_at=value.get("updated_at") or now(),
        )


def _infer_stage(steps):
    mapping = (
        ("actions", "completed"), ("audit", "report_ready"),
        ("screening_summary", "audit_ready"), ("screening_template", "screening_ready"),
        ("normalization", "collection_ready"), ("collection", "collection_ready"),
        ("import", "library_ready"), ("optimization_contract", "config_validated"),
    )
    for step, stage in mapping:
        if steps.get(step) in {"complete", "reused"}:
            return stage
    return "created"
