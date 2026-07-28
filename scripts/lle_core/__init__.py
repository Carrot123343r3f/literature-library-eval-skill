"""Architecture kernel for the literature-library-eval workflow.

The package is intentionally small and dependency-free.  CLI scripts remain
the public entry points, while this package owns domain states, contracts,
artifact lineage, and durable workflow state.
"""

from .contracts import STAGE_CONTRACTS, validate_run_config_contract, validate_stage_inputs, validate_stage_outputs
from .models import WORKFLOW_STAGES, WorkflowState
from .runtime import WorkflowContext

__all__ = [
    "STAGE_CONTRACTS", "WORKFLOW_STAGES", "WorkflowContext",
    "WorkflowState", "validate_run_config_contract", "validate_stage_inputs", "validate_stage_outputs",
]
