from __future__ import annotations

from typing import Any, Dict

from grantflow.api.constants import GROUNDING_POLICY_MODES
from grantflow.api.preflight_service import _configured_preflight_grounding_policy_mode
from grantflow.core.config import config
from grantflow.swarm.citations import citation_traceability_status


def _normalize_grounding_policy_mode(raw_mode: Any) -> str:
    mode = str(raw_mode or "warn").strip().lower()
    if mode not in GROUNDING_POLICY_MODES:
        return "warn"
    return mode


def _configured_mel_grounding_policy_mode() -> str:
    mel_mode = getattr(config.graph, "mel_grounding_policy_mode", None)
    if str(mel_mode or "").strip():
        return _normalize_grounding_policy_mode(mel_mode)
    return _configured_preflight_grounding_policy_mode()


def _mel_grounding_policy_thresholds() -> Dict[str, Any]:
    min_mel_citations_raw = getattr(config.graph, "mel_grounding_min_mel_citations", 2)
    min_claim_support_rate_raw = getattr(config.graph, "mel_grounding_min_claim_support_rate", 0.5)
    min_traceability_complete_rate_raw = getattr(config.graph, "mel_grounding_min_traceability_complete_rate", 0.5)
    max_traceability_gap_rate_raw = getattr(config.graph, "mel_grounding_max_traceability_gap_rate", 0.5)

    try:
        min_mel_citations = int(min_mel_citations_raw)
    except (TypeError, ValueError):
        min_mel_citations = 2
    try:
        min_claim_support_rate = float(min_claim_support_rate_raw)
    except (TypeError, ValueError):
        min_claim_support_rate = 0.5
    try:
        min_traceability_complete_rate = float(min_traceability_complete_rate_raw)
    except (TypeError, ValueError):
        min_traceability_complete_rate = 0.5
    try:
        max_traceability_gap_rate = float(max_traceability_gap_rate_raw)
    except (TypeError, ValueError):
        max_traceability_gap_rate = 0.5

    min_mel_citations = max(1, min(min_mel_citations, 1000))
    min_claim_support_rate = max(0.0, min(min_claim_support_rate, 1.0))
    min_traceability_complete_rate = max(0.0, min(min_traceability_complete_rate, 1.0))
    max_traceability_gap_rate = max(0.0, min(max_traceability_gap_rate, 1.0))
    return {
        "min_mel_citations": min_mel_citations,
        "min_claim_support_rate": round(min_claim_support_rate, 4),
        "min_traceability_complete_rate": round(min_traceability_complete_rate, 4),
        "max_traceability_gap_rate": round(max_traceability_gap_rate, 4),
    }


def _evaluate_mel_grounding_policy_from_state(state: Any) -> Dict[str, Any]:
    mode = _configured_mel_grounding_policy_mode()
    thresholds = _mel_grounding_policy_thresholds()
    min_mel_citations = int(thresholds["min_mel_citations"])
    min_claim_support_rate = float(thresholds["min_claim_support_rate"])
    min_traceability_complete_rate = float(thresholds["min_traceability_complete_rate"])
    max_traceability_gap_rate = float(thresholds["max_traceability_gap_rate"])

    state_dict = state if isinstance(state, dict) else {}
    raw_citations = state_dict.get("citations")
    citations = [c for c in raw_citations if isinstance(c, dict)] if isinstance(raw_citations, list) else []
    mel_citations = [c for c in citations if str(c.get("stage") or "") == "mel"]
    mel_traceability_statuses = [citation_traceability_status(c) for c in mel_citations]

    claim_support_types = {"rag_result", "rag_support", "rag_claim_support"}
    mel_claim_support_count = sum(1 for c in mel_citations if str(c.get("citation_type") or "") in claim_support_types)
    mel_fallback_count = sum(1 for c in mel_citations if str(c.get("citation_type") or "") == "fallback_namespace")
    mel_citation_count = len(mel_citations)
    mel_claim_support_rate = round(mel_claim_support_count / mel_citation_count, 4) if mel_citation_count else None
    mel_traceability_complete_count = sum(1 for status in mel_traceability_statuses if status == "complete")
    mel_traceability_partial_count = sum(1 for status in mel_traceability_statuses if status == "partial")
    mel_traceability_missing_count = sum(1 for status in mel_traceability_statuses if status == "missing")
    mel_traceability_gap_count = mel_traceability_partial_count + mel_traceability_missing_count
    mel_traceability_complete_rate = (
        round(mel_traceability_complete_count / mel_citation_count, 4) if mel_citation_count else None
    )
    mel_traceability_gap_rate = round(mel_traceability_gap_count / mel_citation_count, 4) if mel_citation_count else None

    reasons: list[str] = []
    risk_level = "low"
    if mel_citation_count == 0:
        reasons.append("no_mel_citations")
        risk_level = "high"
    elif mel_citation_count < min_mel_citations:
        reasons.append("mel_citations_below_min")
        risk_level = "medium"

    if mel_claim_support_rate is None:
        reasons.append("mel_claim_support_rate_unavailable")
        risk_level = "high"
    elif mel_claim_support_rate < min_claim_support_rate:
        reasons.append("mel_claim_support_rate_below_min")
        risk_level = "high"

    if mel_traceability_complete_rate is None:
        reasons.append("mel_traceability_rate_unavailable")
        risk_level = "high"
    elif mel_traceability_complete_rate < min_traceability_complete_rate:
        reasons.append("mel_traceability_complete_rate_below_min")
        risk_level = "high"

    if mel_traceability_gap_rate is None:
        reasons.append("mel_traceability_gap_rate_unavailable")
        risk_level = "high"
    elif mel_traceability_gap_rate > max_traceability_gap_rate:
        reasons.append("mel_traceability_gap_rate_above_max")
        risk_level = "high"

    if mode == "off":
        reasons = []
        risk_level = "low"
        passed = True
        blocking = False
        summary = "policy_off"
    else:
        passed = not reasons
        blocking = mode == "strict" and not passed
        summary = "mel_grounding_signals_ok" if passed else ",".join(reasons)

    return {
        "mode": mode,
        "thresholds": thresholds,
        "mel_citation_count": mel_citation_count,
        "mel_claim_support_citation_count": mel_claim_support_count,
        "mel_fallback_namespace_citation_count": mel_fallback_count,
        "mel_claim_support_rate": mel_claim_support_rate,
        "mel_traceability_complete_citation_count": mel_traceability_complete_count,
        "mel_traceability_partial_citation_count": mel_traceability_partial_count,
        "mel_traceability_missing_citation_count": mel_traceability_missing_count,
        "mel_traceability_gap_citation_count": mel_traceability_gap_count,
        "mel_traceability_complete_rate": mel_traceability_complete_rate,
        "mel_traceability_gap_rate": mel_traceability_gap_rate,
        "risk_level": risk_level,
        "passed": passed,
        "blocking": blocking,
        "go_ahead": not blocking,
        "summary": summary,
        "reasons": reasons,
    }


def _configured_export_grounding_policy_mode() -> str:
    export_mode = getattr(config.graph, "export_grounding_policy_mode", None)
    if str(export_mode or "").strip():
        return _normalize_grounding_policy_mode(export_mode)
    return _configured_preflight_grounding_policy_mode()


def _configured_export_require_grounded_gate_pass() -> bool:
    return bool(getattr(config.graph, "export_require_grounded_gate_pass", False))


def _export_grounding_policy_thresholds() -> Dict[str, Any]:
    min_architect_citations_raw = getattr(config.graph, "export_grounding_min_architect_citations", 3)
    min_claim_support_rate_raw = getattr(config.graph, "export_grounding_min_claim_support_rate", 0.5)
    min_traceability_complete_rate_raw = getattr(
        config.graph,
        "export_grounding_min_traceability_complete_rate",
        0.5,
    )
    max_traceability_gap_rate_raw = getattr(config.graph, "export_grounding_max_traceability_gap_rate", 0.5)

    try:
        min_architect_citations = int(min_architect_citations_raw)
    except (TypeError, ValueError):
        min_architect_citations = 3
    try:
        min_claim_support_rate = float(min_claim_support_rate_raw)
    except (TypeError, ValueError):
        min_claim_support_rate = 0.5
    try:
        min_traceability_complete_rate = float(min_traceability_complete_rate_raw)
    except (TypeError, ValueError):
        min_traceability_complete_rate = 0.5
    try:
        max_traceability_gap_rate = float(max_traceability_gap_rate_raw)
    except (TypeError, ValueError):
        max_traceability_gap_rate = 0.5

    min_architect_citations = max(1, min(min_architect_citations, 1000))
    min_claim_support_rate = max(0.0, min(min_claim_support_rate, 1.0))
    min_traceability_complete_rate = max(0.0, min(min_traceability_complete_rate, 1.0))
    max_traceability_gap_rate = max(0.0, min(max_traceability_gap_rate, 1.0))

    return {
        "min_architect_citations": min_architect_citations,
        "min_claim_support_rate": round(min_claim_support_rate, 4),
        "min_traceability_complete_rate": round(min_traceability_complete_rate, 4),
        "max_traceability_gap_rate": round(max_traceability_gap_rate, 4),
    }


def _evaluate_export_grounding_policy(citations: list[dict[str, Any]]) -> Dict[str, Any]:
    mode = _configured_export_grounding_policy_mode()
    thresholds = _export_grounding_policy_thresholds()
    min_architect_citations = int(thresholds["min_architect_citations"])
    min_claim_support_rate = float(thresholds["min_claim_support_rate"])
    min_traceability_complete_rate = float(thresholds["min_traceability_complete_rate"])
    max_traceability_gap_rate = float(thresholds["max_traceability_gap_rate"])

    architect_citations = [c for c in citations if isinstance(c, dict) and str(c.get("stage") or "") == "architect"]
    architect_traceability_statuses = [citation_traceability_status(c) for c in architect_citations]
    architect_citation_count = len(architect_citations)
    architect_claim_support_count = sum(
        1 for c in architect_citations if str(c.get("citation_type") or "") == "rag_claim_support"
    )
    architect_fallback_count = sum(
        1 for c in architect_citations if str(c.get("citation_type") or "") == "fallback_namespace"
    )
    architect_claim_support_rate = (
        round(architect_claim_support_count / architect_citation_count, 4) if architect_citation_count else None
    )
    architect_traceability_complete_count = sum(1 for status in architect_traceability_statuses if status == "complete")
    architect_traceability_partial_count = sum(1 for status in architect_traceability_statuses if status == "partial")
    architect_traceability_missing_count = sum(1 for status in architect_traceability_statuses if status == "missing")
    architect_traceability_gap_count = architect_traceability_partial_count + architect_traceability_missing_count
    architect_traceability_complete_rate = (
        round(architect_traceability_complete_count / architect_citation_count, 4) if architect_citation_count else None
    )
    architect_traceability_gap_rate = (
        round(architect_traceability_gap_count / architect_citation_count, 4) if architect_citation_count else None
    )

    reasons: list[str] = []
    risk_level = "low"
    if architect_citation_count == 0:
        reasons.append("no_architect_citations")
        risk_level = "high"
    elif architect_citation_count < min_architect_citations:
        reasons.append("architect_citations_below_min")
        risk_level = "medium"

    if architect_claim_support_rate is None:
        reasons.append("claim_support_rate_unavailable")
        risk_level = "high"
    elif architect_claim_support_rate < min_claim_support_rate:
        reasons.append("claim_support_rate_below_min")
        risk_level = "high"

    if architect_traceability_complete_rate is None:
        reasons.append("traceability_rate_unavailable")
        risk_level = "high"
    elif architect_traceability_complete_rate < min_traceability_complete_rate:
        reasons.append("traceability_complete_rate_below_min")
        risk_level = "high"

    if architect_traceability_gap_rate is None:
        reasons.append("traceability_gap_rate_unavailable")
        risk_level = "high"
    elif architect_traceability_gap_rate > max_traceability_gap_rate:
        reasons.append("traceability_gap_rate_above_max")
        risk_level = "high"

    passed = not reasons
    blocking = mode == "strict" and not passed
    summary = "export_grounding_signals_ok" if passed else ",".join(reasons)
    return {
        "mode": mode,
        "thresholds": thresholds,
        "architect_citation_count": architect_citation_count,
        "architect_claim_support_citation_count": architect_claim_support_count,
        "architect_fallback_namespace_citation_count": architect_fallback_count,
        "architect_claim_support_rate": architect_claim_support_rate,
        "architect_traceability_complete_citation_count": architect_traceability_complete_count,
        "architect_traceability_partial_citation_count": architect_traceability_partial_count,
        "architect_traceability_missing_citation_count": architect_traceability_missing_count,
        "architect_traceability_gap_citation_count": architect_traceability_gap_count,
        "architect_traceability_complete_rate": architect_traceability_complete_rate,
        "architect_traceability_gap_rate": architect_traceability_gap_rate,
        "risk_level": risk_level,
        "passed": passed,
        "blocking": blocking,
        "go_ahead": not blocking,
        "summary": summary,
        "reasons": reasons,
    }
