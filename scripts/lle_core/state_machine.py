"""State transitions for resumable workflow runs."""
from .models import WORKFLOW_STAGES


def validate_stage(stage):
    if stage not in WORKFLOW_STAGES:
        raise ValueError(f"unknown workflow stage: {stage}")


def can_advance(current, target):
    validate_stage(current); validate_stage(target)
    return WORKFLOW_STAGES.index(target) >= WORKFLOW_STAGES.index(current)


def advance(state, target, status="active"):
    if not can_advance(state.stage, target):
        raise ValueError(f"workflow cannot move backward: {state.stage} -> {target}")
    state.stage = target
    state.status = "completed" if target == "completed" else status
    return state
