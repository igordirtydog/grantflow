from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable

from grantflow.swarm.state_contract import normalize_rag_namespace

RETRIEVAL_GROUNDED_CITATION_TYPES = frozenset(
    {
        "rag_result",
        "rag_support",
        "rag_claim_support",
        "rag_low_confidence",
    }
)
STRATEGY_REFERENCE_CITATION_TYPES = frozenset({"strategy_reference", "strategy_namespace"})
FALLBACK_NAMESPACE_CITATION_TYPES = frozenset({"fallback_namespace"})


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _coerce_probability(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    bounded = max(0.0, min(1.0, parsed))
    return round(bounded, 4)


def _stable_synthetic_doc_id(record: Dict[str, Any]) -> str:
    namespace_normalized = normalize_rag_namespace(record.get("namespace_normalized") or record.get("namespace"))
    source = str(record.get("source") or "").strip()
    page = str(record.get("page") or "").strip()
    page_start = str(record.get("page_start") or "").strip()
    page_end = str(record.get("page_end") or "").strip()
    statement_path = str(record.get("statement_path") or "").strip()
    used_for = str(record.get("used_for") or "").strip()
    label = str(record.get("label") or "").strip()
    excerpt = str(record.get("excerpt") or "").strip()[:120]
    seed = "|".join(
        [
            namespace_normalized,
            source,
            page,
            page_start,
            page_end,
            statement_path,
            used_for,
            label,
            excerpt,
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    ns_part = namespace_normalized or "unknown"
    return f"synthetic::{ns_part}::{digest}"


def normalize_citation(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in record.items():
        normalized[str(key)] = _jsonable(value)

    namespace = str(normalized.get("namespace") or "").strip()
    namespace_normalized = normalize_rag_namespace(
        str(normalized.get("namespace_normalized") or "").strip() or namespace
    )
    if namespace:
        normalized["namespace"] = namespace
    elif namespace_normalized:
        normalized["namespace"] = namespace_normalized
    if namespace_normalized:
        normalized["namespace_normalized"] = namespace_normalized

    doc_id = str(normalized.get("doc_id") or "").strip()
    chunk_id = str(normalized.get("chunk_id") or "").strip()
    if not doc_id and chunk_id:
        normalized["doc_id"] = chunk_id
    elif doc_id and not chunk_id:
        normalized["chunk_id"] = doc_id

    retrieval_rank = (
        _coerce_positive_int(normalized.get("retrieval_rank"))
        or _coerce_positive_int(normalized.get("rank"))
        or _coerce_positive_int(normalized.get("evidence_rank"))
    )
    if retrieval_rank is not None:
        normalized["retrieval_rank"] = retrieval_rank
        normalized.setdefault("evidence_rank", retrieval_rank)

    retrieval_confidence = (
        _coerce_probability(normalized.get("retrieval_confidence"))
        or _coerce_probability(normalized.get("citation_confidence"))
        or _coerce_probability(normalized.get("evidence_score"))
    )
    if retrieval_confidence is not None:
        normalized["retrieval_confidence"] = retrieval_confidence
        normalized.setdefault("evidence_score", retrieval_confidence)

    citation_confidence = _coerce_probability(normalized.get("citation_confidence"))
    if citation_confidence is not None:
        normalized["citation_confidence"] = citation_confidence

    if is_retrieval_grounded_citation_type(normalized.get("citation_type")) and not citation_has_doc_id(normalized):
        synthetic_doc_id = _stable_synthetic_doc_id(normalized)
        normalized["doc_id"] = synthetic_doc_id
        normalized.setdefault("chunk_id", synthetic_doc_id)
        normalized["doc_id_synthetic"] = True

    return normalized


def citation_type_token(record: Dict[str, Any]) -> str:
    return str(record.get("citation_type") or "").strip().lower()


def is_fallback_namespace_citation_type(citation_type: Any) -> bool:
    return str(citation_type or "").strip().lower() in FALLBACK_NAMESPACE_CITATION_TYPES


def is_strategy_reference_citation_type(citation_type: Any) -> bool:
    return str(citation_type or "").strip().lower() in STRATEGY_REFERENCE_CITATION_TYPES


def is_retrieval_grounded_citation_type(citation_type: Any) -> bool:
    return str(citation_type or "").strip().lower() in RETRIEVAL_GROUNDED_CITATION_TYPES


def is_non_retrieval_citation_type(citation_type: Any) -> bool:
    token = str(citation_type or "").strip().lower()
    return token in STRATEGY_REFERENCE_CITATION_TYPES or token in FALLBACK_NAMESPACE_CITATION_TYPES


def citation_has_doc_id(record: Dict[str, Any]) -> bool:
    return bool(str(record.get("doc_id") or record.get("chunk_id") or "").strip())


def citation_has_retrieval_rank(record: Dict[str, Any]) -> bool:
    raw: Any = record.get("retrieval_rank")
    if raw in (None, ""):
        raw = record.get("rank")
    if raw in (None, ""):
        return False
    try:
        return int(raw) > 0
    except (TypeError, ValueError):
        return False


def citation_has_retrieval_confidence(record: Dict[str, Any]) -> bool:
    raw: Any = record.get("retrieval_confidence")
    if raw in (None, ""):
        raw = record.get("citation_confidence")
    if raw in (None, ""):
        return False
    try:
        float(raw)
    except (TypeError, ValueError):
        return False
    return True


def citation_has_retrieval_metadata(record: Dict[str, Any]) -> bool:
    return (
        citation_has_doc_id(record)
        and citation_has_retrieval_rank(record)
        and citation_has_retrieval_confidence(record)
    )


def _citation_key(record: Dict[str, Any]) -> tuple[Any, ...]:
    namespace_key = str(record.get("namespace_normalized") or "").strip().lower()
    if not namespace_key:
        namespace_key = normalize_rag_namespace(record.get("namespace"))
    return (
        record.get("stage"),
        record.get("citation_type"),
        namespace_key,
        record.get("doc_id"),
        record.get("source"),
        record.get("page"),
        record.get("page_start"),
        record.get("page_end"),
        record.get("chunk"),
        record.get("chunk_id"),
        record.get("used_for"),
        record.get("statement_path"),
        record.get("label"),
    )


def _traceability_weight(record: Dict[str, Any]) -> int:
    status = citation_traceability_status(record)
    if status == "complete":
        return 2
    if status == "partial":
        return 1
    return 0


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_or_default(value: Any, default: int = 999) -> int:
    try:
        token = int(value)
    except (TypeError, ValueError):
        return default
    return token if token > 0 else default


def _citation_quality_key(record: Dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(_traceability_weight(record)),
        _float_or_default(record.get("citation_confidence"), default=0.0),
        _float_or_default(record.get("retrieval_confidence"), default=0.0),
        -float(_int_or_default(record.get("retrieval_rank"), default=999)),
    )


def _merge_citation_records(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    current_key = _citation_quality_key(current)
    incoming_key = _citation_quality_key(incoming)
    preferred = dict(incoming) if incoming_key >= current_key else dict(current)
    fallback = current if incoming_key >= current_key else incoming
    for key, value in fallback.items():
        if preferred.get(key) in (None, "") and value not in (None, ""):
            preferred[key] = value
    return preferred


def append_citations(state: Dict[str, Any], citations: Iterable[Dict[str, Any]], max_items: int = 200) -> None:
    incoming = [normalize_citation(c) for c in citations if isinstance(c, dict)]
    if not incoming:
        return

    existing = state.get("citations")
    if not isinstance(existing, list):
        existing = []

    normalized_existing = [normalize_citation(c) for c in existing if isinstance(c, dict)]
    merged = list(normalized_existing)
    seen: dict[tuple[Any, ...], int] = {}
    for idx, row in enumerate(merged):
        seen[_citation_key(row)] = idx

    for record in incoming:
        key = _citation_key(record)
        existing_idx = seen.get(key)
        if existing_idx is None:
            seen[key] = len(merged)
            merged.append(record)
            continue
        merged[existing_idx] = _merge_citation_records(merged[existing_idx], record)

    if len(merged) > max_items:
        merged = merged[-max_items:]
    state["citations"] = merged


def citation_traceability_status(record: Dict[str, Any]) -> str:
    status = str(record.get("traceability_status") or "").strip().lower()
    if status in {"complete", "partial", "missing"}:
        return status

    doc_id = str(record.get("doc_id") or record.get("chunk_id") or "").strip()
    source = str(record.get("source") or "").strip()
    page = record.get("page")
    page_start = record.get("page_start")
    page_end = record.get("page_end")
    chunk = record.get("chunk")

    if doc_id and source:
        return "complete"
    if doc_id or source or page is not None or page_start is not None or page_end is not None or chunk is not None:
        return "partial"
    return "missing"
