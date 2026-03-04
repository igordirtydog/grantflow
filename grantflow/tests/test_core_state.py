from __future__ import annotations

from grantflow.core import state as core_state
from grantflow.swarm import state_contract


def test_core_state_reexports_canonical_state_contract_symbols():
    assert core_state.GrantFlowState is state_contract.GrantFlowState
    assert core_state.GrantFlowStateModel is state_contract.GrantFlowStateModel
    assert core_state.normalize_state_contract is state_contract.normalize_state_contract
    assert core_state.build_graph_state is state_contract.build_graph_state
    assert core_state.state_donor_id is state_contract.state_donor_id
    assert core_state.state_input_context is state_contract.state_input_context


def test_core_state_normalization_path_matches_canonical_behavior():
    state = {
        "donor": "USAID",
        "input": {"project": "AI upskilling", "country": "Kazakhstan"},
        "llm_mode": "true",
    }
    normalized = core_state.normalize_state_contract(state)
    assert normalized["donor_id"] == "usaid"
    assert "donor" not in normalized
    assert normalized["input_context"]["country"] == "Kazakhstan"
    assert "input" not in normalized
    assert normalized["llm_mode"] is True
