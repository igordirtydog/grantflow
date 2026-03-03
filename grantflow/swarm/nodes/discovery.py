# grantflow/swarm/nodes/discovery.py

from __future__ import annotations

from typing import Any, Dict

from grantflow.core.strategies.factory import DonorFactory
from grantflow.swarm.state_contract import (
    normalize_state_contract,
    set_state_donor_strategy,
    state_donor_id,
    state_donor_strategy,
    state_input_context,
)


def validate_input_richness(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Валидирует входные данные и загружает стратегию донора.
    """
    normalize_state_contract(state)
    donor_id = state_donor_id(state)
    input_context = state_input_context(state)

    if not donor_id:
        state["errors"].append("Missing donor_id/donor")
        return state

    try:
        if state_donor_strategy(state) is None:
            set_state_donor_strategy(state, DonorFactory.get_strategy(donor_id))
    except ValueError as e:
        state["errors"].append(str(e))

    if not input_context.get("project"):
        state["errors"].append("Missing project description in input_context")

    return state
