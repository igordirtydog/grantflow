from __future__ import annotations

"""Compatibility layer for the canonical GrantFlow graph state contract.

Source of truth lives in `grantflow.swarm.state_contract`.
`grantflow.core.state` is retained as a stable import path for consumers.
"""

from grantflow.swarm.state_contract import (
    GrantFlowState,
    GrantFlowStateModel,
    build_graph_state,
    normalize_donor_token,
    normalize_input_context,
    normalize_rag_namespace,
    normalize_state_contract,
    normalized_state_copy,
    set_state_donor_strategy,
    set_state_iteration,
    state_donor_id,
    state_donor_strategy,
    state_input_context,
    state_iteration,
    state_llm_mode,
    state_max_iterations,
    state_rag_namespace,
    state_revision_hint,
)

__all__ = [
    "GrantFlowState",
    "GrantFlowStateModel",
    "build_graph_state",
    "normalize_donor_token",
    "normalize_input_context",
    "normalize_rag_namespace",
    "normalize_state_contract",
    "normalized_state_copy",
    "set_state_donor_strategy",
    "set_state_iteration",
    "state_donor_id",
    "state_donor_strategy",
    "state_input_context",
    "state_iteration",
    "state_llm_mode",
    "state_max_iterations",
    "state_rag_namespace",
    "state_revision_hint",
]
