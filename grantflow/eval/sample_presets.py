from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

SAMPLE_PRESET_FILES: dict[str, str] = {
    "rbm-usaid-ai-civil-service-kazakhstan": "docs/samples/rbm-sample-usaid-ai-civil-service-kazakhstan.json",
    "rbm-eu-youth-employment-jordan": "docs/samples/rbm-sample-eu-youth-employment-jordan.json",
}


def _dict_from(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_from(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def available_sample_ids() -> list[str]:
    return sorted(SAMPLE_PRESET_FILES.keys())


def _sample_path(sample_id: str) -> Path:
    relative = SAMPLE_PRESET_FILES[sample_id]
    return REPO_ROOT / relative


def sample_file_path(sample_id: str) -> Path:
    normalized = str(sample_id or "").strip().lower()
    if normalized not in SAMPLE_PRESET_FILES:
        known = ", ".join(available_sample_ids())
        raise ValueError(f"Unknown sample_id '{sample_id}'. Available: {known}")
    return _sample_path(normalized)


def _normalize_sample_ids(sample_ids: list[str]) -> list[str]:
    normalized = [str(item or "").strip().lower() for item in sample_ids if str(item or "").strip()]
    if not normalized:
        return []
    if "all" in normalized:
        return available_sample_ids()
    unknown = [item for item in normalized if item not in SAMPLE_PRESET_FILES]
    if unknown:
        known = ", ".join(available_sample_ids())
        missing = ", ".join(sorted(set(unknown)))
        raise ValueError(f"Unknown sample_id(s): {missing}. Available: {known}")
    seen: set[str] = set()
    ordered: list[str] = []
    for item in normalized:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _format_timeframe(time_horizon: dict[str, Any]) -> str | None:
    implementation_months = time_horizon.get("implementation_months")
    impact_horizon_years = str(time_horizon.get("impact_horizon_years") or "").strip()
    parts: list[str] = []
    if isinstance(implementation_months, int) and implementation_months > 0:
        parts.append(f"{implementation_months} months implementation")
    if impact_horizon_years:
        parts.append(f"impact horizon {impact_horizon_years} years")
    if not parts:
        return None
    return "; ".join(parts)


def _normalized_sample_id(sample_id: str) -> str:
    token = str(sample_id or "").strip().lower()
    if token not in SAMPLE_PRESET_FILES:
        known = ", ".join(available_sample_ids())
        raise ValueError(f"Unknown sample_id '{sample_id}'. Available: {known}")
    return token


def load_sample_payload(sample_id: str) -> dict[str, Any]:
    normalized = _normalized_sample_id(sample_id)
    path = _sample_path(normalized)
    if not path.exists():
        raise ValueError(f"Sample '{normalized}' file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Sample '{normalized}' payload must be an object: {path}")
    return payload


def build_generate_payload(
    sample_id: str,
    *,
    llm_mode: bool = False,
    hitl_enabled: bool = False,
    architect_rag_enabled: bool = False,
    strict_preflight: bool = False,
) -> dict[str, Any]:
    case = load_sample_eval_cases([sample_id])[0]
    return {
        "donor_id": str(case.get("donor_id") or ""),
        "input_context": _dict_from(case.get("input_context")),
        "llm_mode": bool(llm_mode),
        "hitl_enabled": bool(hitl_enabled),
        "architect_rag_enabled": bool(architect_rag_enabled),
        "strict_preflight": bool(strict_preflight),
    }


def list_sample_preset_summaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample_id in available_sample_ids():
        payload = load_sample_payload(sample_id)
        program_context = _dict_from(payload.get("program_context"))
        time_horizon = _dict_from(program_context.get("time_horizon"))
        rows.append(
            {
                "sample_id": sample_id,
                "donor_id": str(payload.get("donor_id") or "").strip().lower() or None,
                "title": str(program_context.get("title") or "").strip() or None,
                "country": str(program_context.get("country") or "").strip() or None,
                "timeframe": _format_timeframe(time_horizon),
                "source_file": SAMPLE_PRESET_FILES[sample_id],
            }
        )
    return rows


def _case_from_sample_payload(sample_id: str, payload: dict[str, Any], *, source_path: Path) -> dict[str, Any]:
    donor_id = str(payload.get("donor_id") or "").strip().lower()
    if not donor_id:
        raise ValueError(f"Sample '{sample_id}' is missing donor_id")

    program_context = _dict_from(payload.get("program_context"))
    theory = _dict_from(payload.get("theory_of_change"))
    logic_model = _dict_from(payload.get("logic_model"))
    time_horizon = _dict_from(program_context.get("time_horizon"))

    project = str(program_context.get("title") or "").strip() or sample_id
    country = str(program_context.get("country") or "").strip()
    problem = str(program_context.get("problem_summary") or "").strip()
    target_population = str(program_context.get("target_population") or "").strip()
    expected_change = str(theory.get("if_then") or "").strip()

    input_context: dict[str, Any] = {"project": project}
    if country:
        input_context["country"] = country
    timeframe = _format_timeframe(time_horizon)
    if timeframe:
        input_context["timeframe"] = timeframe
    if problem:
        input_context["problem"] = problem
    if target_population:
        input_context["target_population"] = target_population
    if expected_change:
        input_context["expected_change"] = expected_change

    activities = [str(item).strip() for item in _list_from(logic_model.get("activities")) if str(item).strip()]
    if activities:
        input_context["key_activities"] = activities

    outcomes = [str(item).strip() for item in _list_from(logic_model.get("outcomes")) if str(item).strip()]
    if outcomes:
        input_context["expected_outcomes"] = outcomes

    inclusion_priorities = [
        str(item).strip() for item in _list_from(program_context.get("inclusion_priorities")) if str(item).strip()
    ]
    if inclusion_priorities:
        input_context["inclusion_priorities"] = inclusion_priorities

    assumptions = [str(item).strip() for item in _list_from(program_context.get("assumptions")) if str(item).strip()]
    key_assumptions = [str(item).strip() for item in _list_from(theory.get("key_assumptions")) if str(item).strip()]
    if assumptions or key_assumptions:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*key_assumptions, *assumptions]:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        input_context["assumptions"] = merged

    expectations = payload.get("expectations")
    if not isinstance(expectations, dict):
        expectations = {
            "toc_schema_valid": True,
            "require_toc_draft": True,
            "require_logframe_draft": True,
            "max_errors": 0,
        }

    case_id = str(payload.get("sample_id") or sample_id).strip() or sample_id
    return {
        "case_id": case_id,
        "donor_id": donor_id,
        "input_context": input_context,
        "llm_mode": bool(payload.get("llm_mode", False)),
        "architect_rag_enabled": bool(payload.get("architect_rag_enabled", False)),
        "expectations": expectations,
        "_fixture_file": source_path.name,
        "_sample_id": sample_id,
    }


def load_sample_eval_cases(sample_ids: list[str]) -> list[dict[str, Any]]:
    resolved_ids = _normalize_sample_ids(sample_ids)
    if not resolved_ids:
        return []
    cases: list[dict[str, Any]] = []
    for sample_id in resolved_ids:
        path = sample_file_path(sample_id)
        payload = load_sample_payload(sample_id)
        cases.append(_case_from_sample_payload(sample_id, payload, source_path=path))
    return cases
