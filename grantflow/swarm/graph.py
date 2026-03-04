# grantflow/swarm/graph.py

from __future__ import annotations

from typing import Optional

from grantflow.swarm.nodes.architect import draft_toc
from grantflow.swarm.nodes.critic import red_team_critic
from grantflow.swarm.nodes.discovery import validate_input_richness
from grantflow.swarm.nodes.mel_specialist import mel_assign_indicators
from grantflow.swarm.state_contract import normalize_state_contract

_LANGGRAPH_IMPORT_ERROR: Optional[str] = None
try:
    from langgraph.graph import END as _LANGGRAPH_END_IMPORTED, StateGraph as _LANGGRAPH_STATE_GRAPH_IMPORTED
except Exception as exc:  # pragma: no cover - runtime/environment dependent
    _LANGGRAPH_IMPORT_ERROR = str(exc)
    _LANGGRAPH_END_IMPORTED = "__end__"
    _LANGGRAPH_STATE_GRAPH_IMPORTED = None

END = _LANGGRAPH_END_IMPORTED
StateGraph = _LANGGRAPH_STATE_GRAPH_IMPORTED


def _start_node(state: dict) -> dict:
    return state


def _resolve_start_node(state: dict) -> str:
    start_at = str(state.get("_start_at") or "start").strip().lower()
    if start_at in {"start", "discovery"}:
        return "discovery"
    if start_at in {"architect", "mel", "critic"}:
        return start_at
    return "discovery"


def _configured_hitl_stages(state: dict) -> set[str]:
    normalize_state_contract(state)
    if not bool(state.get("hitl_enabled", False)):
        state["hitl_checkpoints"] = []
        return set()

    raw = state.get("hitl_checkpoints")
    tokens: list[str] = []
    if isinstance(raw, str):
        tokens = [part.strip().lower() for part in raw.split(",") if part.strip()]
    elif isinstance(raw, (list, tuple, set)):
        for item in raw:
            token = str(item or "").strip().lower()
            if token:
                tokens.append(token)

    alias_to_stage = {
        "architect": "toc",
        "toc": "toc",
        "mel": "logframe",
        "logframe": "logframe",
    }
    normalized: list[str] = []
    for token in tokens:
        stage = alias_to_stage.get(token)
        if not stage:
            continue
        if stage not in normalized:
            normalized.append(stage)

    if not normalized:
        normalized = ["toc", "logframe"]
    state["hitl_checkpoints"] = normalized
    return set(normalized)


def _set_hitl_pending_state(state: dict, *, stage: str, resume_from: str) -> dict:
    state["hitl_pending"] = True
    state["hitl_checkpoint_stage"] = stage
    state["hitl_resume_from"] = resume_from
    state.pop("hitl_checkpoint_id", None)
    return state


def _toc_hitl_gate(state: dict) -> dict:
    normalize_state_contract(state)
    if "toc" not in _configured_hitl_stages(state):
        state["hitl_pending"] = False
        state.pop("hitl_checkpoint_stage", None)
        state.pop("hitl_resume_from", None)
        state.pop("hitl_checkpoint_id", None)
        return state

    return _set_hitl_pending_state(state, stage="toc", resume_from="mel")


def _route_after_toc_gate(state: dict):
    if bool(state.get("hitl_pending", False)):
        return END
    return "mel"


def _logframe_hitl_gate(state: dict) -> dict:
    normalize_state_contract(state)
    if "logframe" not in _configured_hitl_stages(state):
        state["hitl_pending"] = False
        state.pop("hitl_checkpoint_stage", None)
        state.pop("hitl_resume_from", None)
        state.pop("hitl_checkpoint_id", None)
        return state

    return _set_hitl_pending_state(state, stage="logframe", resume_from="critic")


def _route_after_logframe_gate(state: dict):
    if bool(state.get("hitl_pending", False)):
        return END
    return "critic"


def _route_after_critic(state: dict):
    if state.get("needs_revision"):
        return "architect"
    return END


class _FallbackCompiledGraph:
    """Minimal sequential fallback when langgraph is unavailable at import/runtime."""

    def __init__(self, *, import_error: Optional[str] = None) -> None:
        self.import_error = import_error

    def invoke(self, state: dict) -> dict:
        if not isinstance(state, dict):
            return {}

        current = _resolve_start_node(state)
        state["graph_backend"] = "fallback_sequential"
        if self.import_error:
            state["graph_backend_reason"] = self.import_error

        while True:
            if current == "discovery":
                state = validate_input_richness(state)
                current = "architect"
                continue

            if current == "architect":
                state = draft_toc(state)
                state = _toc_hitl_gate(state)
                route = _route_after_toc_gate(state)
                if route == END:
                    return state
                current = "mel"
                continue

            if current == "mel":
                state = mel_assign_indicators(state)
                state = _logframe_hitl_gate(state)
                route = _route_after_logframe_gate(state)
                if route == END:
                    return state
                current = "critic"
                continue

            if current == "critic":
                state = red_team_critic(state)
                route = _route_after_critic(state)
                if route == END:
                    return state
                current = "architect"
                continue

            return state


def build_graph():
    if StateGraph is None:
        return _FallbackCompiledGraph(import_error=_LANGGRAPH_IMPORT_ERROR)

    g = StateGraph(dict)

    g.add_node("start", _start_node)
    g.add_node("discovery", validate_input_richness)
    g.add_node("architect", draft_toc)
    g.add_node("toc_hitl_gate", _toc_hitl_gate)
    g.add_node("mel", mel_assign_indicators)
    g.add_node("logframe_hitl_gate", _logframe_hitl_gate)
    g.add_node("critic", red_team_critic)

    g.set_entry_point("start")
    g.add_conditional_edges(
        "start",
        _resolve_start_node,
        {
            "discovery": "discovery",
            "architect": "architect",
            "mel": "mel",
            "critic": "critic",
        },
    )

    g.add_edge("discovery", "architect")
    g.add_edge("architect", "toc_hitl_gate")
    g.add_conditional_edges(
        "toc_hitl_gate",
        _route_after_toc_gate,
        {
            "mel": "mel",
            END: END,
        },
    )

    g.add_edge("mel", "logframe_hitl_gate")
    g.add_conditional_edges(
        "logframe_hitl_gate",
        _route_after_logframe_gate,
        {
            "critic": "critic",
            END: END,
        },
    )

    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {
            "architect": "architect",
            END: END,
        },
    )

    return g.compile()


def build_grantflow_graph():
    return build_graph()


grantflow_graph = build_graph()
