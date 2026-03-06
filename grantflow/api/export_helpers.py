from __future__ import annotations

import csv
import gzip
import io
import json
from typing import Any, Dict, Literal, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from grantflow.api.schemas import ExportRequest
from grantflow.swarm.findings import canonicalize_findings, state_critic_findings
from grantflow.swarm.state_contract import normalized_state_copy, state_donor_id


def _hitl_history_csv_text(payload: Dict[str, Any]) -> str:
    raw_events = payload.get("events")
    events: list[Any] = raw_events if isinstance(raw_events, list) else []
    header = [
        "event_id",
        "ts",
        "type",
        "status",
        "from_status",
        "to_status",
        "checkpoint_id",
        "checkpoint_stage",
        "checkpoint_status",
        "resuming_from",
        "approved",
        "feedback",
        "actor",
        "request_id",
        "reason",
        "backend",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in events:
        item = row if isinstance(row, dict) else {}
        writer.writerow(
            [
                item.get("event_id"),
                item.get("ts"),
                item.get("type"),
                item.get("status"),
                item.get("from_status"),
                item.get("to_status"),
                item.get("checkpoint_id"),
                item.get("checkpoint_stage"),
                item.get("checkpoint_status"),
                item.get("resuming_from"),
                item.get("approved"),
                item.get("feedback"),
                item.get("actor"),
                item.get("request_id"),
                item.get("reason"),
                item.get("backend"),
            ]
        )
    return buffer.getvalue()


def _job_events_csv_text(payload: Dict[str, Any]) -> str:
    raw_events = payload.get("events")
    events: list[Any] = raw_events if isinstance(raw_events, list) else []
    base_columns = [
        "event_id",
        "ts",
        "type",
        "status",
        "from_status",
        "to_status",
        "checkpoint_id",
        "checkpoint_stage",
        "checkpoint_status",
        "resuming_from",
        "actor",
        "request_id",
    ]
    header = [*base_columns, "payload_json"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in events:
        item = row if isinstance(row, dict) else {}
        extras = {k: v for k, v in item.items() if k not in base_columns and v is not None}
        writer.writerow(
            [
                item.get("event_id"),
                item.get("ts"),
                item.get("type"),
                item.get("status"),
                item.get("from_status"),
                item.get("to_status"),
                item.get("checkpoint_id"),
                item.get("checkpoint_stage"),
                item.get("checkpoint_status"),
                item.get("resuming_from"),
                item.get("actor"),
                item.get("request_id"),
                (json.dumps(extras, sort_keys=True, ensure_ascii=False) if extras else ""),
            ]
        )
    return buffer.getvalue()


def _job_comments_csv_text(payload: Dict[str, Any]) -> str:
    raw_comments = payload.get("comments")
    comments: list[Any] = raw_comments if isinstance(raw_comments, list) else []
    base_columns = [
        "comment_id",
        "ts",
        "section",
        "status",
        "message",
        "author",
        "version_id",
        "linked_finding_id",
        "linked_finding_severity",
        "resolved_at",
        "reopened_at",
        "actor",
        "request_id",
        "due_at",
        "sla_hours",
    ]
    header = [*base_columns, "payload_json"]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in comments:
        item = row if isinstance(row, dict) else {}
        extras = {k: v for k, v in item.items() if k not in base_columns and v is not None}
        writer.writerow(
            [
                item.get("comment_id"),
                item.get("ts"),
                item.get("section"),
                item.get("status"),
                item.get("message"),
                item.get("author"),
                item.get("version_id"),
                item.get("linked_finding_id"),
                item.get("linked_finding_severity"),
                item.get("resolved_at"),
                item.get("reopened_at"),
                item.get("actor"),
                item.get("request_id"),
                item.get("due_at"),
                item.get("sla_hours"),
                (json.dumps(extras, sort_keys=True, ensure_ascii=False) if extras else ""),
            ]
        )
    return buffer.getvalue()


def _resolve_export_inputs(
    req: ExportRequest,
) -> tuple[dict, dict, str, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    payload = req.payload or {}
    payload_root = payload if isinstance(payload, dict) else {}
    state_payload = payload_root.get("state") if isinstance(payload_root.get("state"), dict) else payload_root
    payload = state_payload if isinstance(state_payload, dict) else {}

    payload_state = dict(normalized_state_copy(payload))
    req_donor = str(req.donor_id or "").strip().lower()
    donor_id = req_donor or state_donor_id(payload_state, default="grantflow")
    toc = req.toc_draft or payload.get("toc_draft") or payload.get("toc") or {}
    logframe = req.logframe_draft or payload.get("logframe_draft") or payload.get("mel") or {}
    citations = payload.get("citations") or []
    state_critic_findings_payload = state_critic_findings(payload_state, default_source="rules")
    critic_findings = req.critic_findings or state_critic_findings_payload or payload_root.get("critic_findings") or []
    review_comments = req.review_comments or payload_root.get("review_comments") or payload.get("review_comments") or []
    quality_summary = payload_root.get("quality_summary") or {}

    if not isinstance(toc, dict):
        toc = {}
    if not isinstance(logframe, dict):
        logframe = {}
    if not isinstance(citations, list):
        citations = []
    if not isinstance(critic_findings, list):
        critic_findings = []
    if not isinstance(review_comments, list):
        review_comments = []
    if not isinstance(quality_summary, dict):
        quality_summary = {}
    citations = [c for c in citations if isinstance(c, dict)]
    critic_findings = canonicalize_findings(critic_findings, state=payload_state, default_source="rules")
    review_comments = [c for c in review_comments if isinstance(c, dict)]
    return toc, logframe, str(donor_id), citations, critic_findings, review_comments, dict(quality_summary)


def _extract_export_grounding_gate(req: ExportRequest) -> Dict[str, Any]:
    payload = req.payload if isinstance(req.payload, dict) else {}
    if not payload:
        return {}

    state_payload = payload.get("state") if isinstance(payload.get("state"), dict) else payload
    if not isinstance(state_payload, dict):
        return {}
    gate = state_payload.get("grounding_gate")
    return gate if isinstance(gate, dict) else {}


def _extract_export_runtime_grounded_quality_gate(req: ExportRequest) -> Dict[str, Any]:
    payload = req.payload if isinstance(req.payload, dict) else {}
    if not payload:
        return {}
    payload_root = payload if isinstance(payload, dict) else {}
    state_payload = payload_root.get("state") if isinstance(payload_root.get("state"), dict) else payload_root
    if not isinstance(state_payload, dict):
        return {}

    runtime_gate = state_payload.get("grounded_quality_gate")
    if isinstance(runtime_gate, dict):
        return runtime_gate

    public_runtime_gate = state_payload.get("grounded_gate")
    if isinstance(public_runtime_gate, dict):
        return public_runtime_gate

    root_runtime_gate = payload_root.get("grounded_quality_gate")
    if isinstance(root_runtime_gate, dict):
        return root_runtime_gate

    root_public_runtime_gate = payload_root.get("grounded_gate")
    if isinstance(root_public_runtime_gate, dict):
        return root_public_runtime_gate
    return {}


def _portfolio_export_response(
    *,
    payload: Dict[str, Any],
    filename_prefix: str,
    donor_id: Optional[str],
    status: Optional[str],
    hitl_enabled: Optional[bool],
    export_format: Literal["csv", "json"],
    gzip_enabled: bool,
    csv_renderer,
) -> StreamingResponse:
    filename_parts = [filename_prefix]
    if donor_id:
        filename_parts.append(donor_id)
    if status:
        filename_parts.append(status)
    if hitl_enabled is not None:
        filename_parts.append(f"hitl_{str(hitl_enabled).lower()}")

    if export_format == "csv":
        body_text = csv_renderer(payload)
        media_type = "text/csv; charset=utf-8"
        extension = "csv"
    elif export_format == "json":
        body_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        media_type = "application/json"
        extension = "json"
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    body_bytes = body_text.encode("utf-8")
    if gzip_enabled:
        body_bytes = gzip.compress(body_bytes)
        extension = f"{extension}.gz"
        media_type = "application/gzip"

    filename = "_".join(filename_parts) + f".{extension}"
    return StreamingResponse(
        io.BytesIO(body_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _dead_letter_queue_csv_text(payload: Dict[str, Any]) -> str:
    raw_items = payload.get("items")
    rows: list[Any] = raw_items if isinstance(raw_items, list) else []
    header = [
        "index",
        "dispatch_id",
        "task_name",
        "job_id",
        "reason",
        "attempt",
        "max_attempts",
        "queued_at",
        "first_failed_at",
        "failed_at",
        "error",
        "metadata_json",
        "payload_json",
        "raw_payload",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        item = row if isinstance(row, dict) else {}
        metadata_value = item.get("metadata")
        metadata_json = json.dumps(metadata_value, ensure_ascii=False) if isinstance(metadata_value, dict) else ""
        payload_value = item.get("payload")
        payload_json = json.dumps(payload_value, ensure_ascii=False) if isinstance(payload_value, dict) else ""
        writer.writerow(
            [
                item.get("index"),
                item.get("dispatch_id"),
                item.get("task_name"),
                item.get("job_id"),
                item.get("reason"),
                item.get("attempt"),
                item.get("max_attempts"),
                item.get("queued_at"),
                item.get("first_failed_at"),
                item.get("failed_at"),
                item.get("error"),
                metadata_json,
                payload_json,
                item.get("raw_payload"),
            ]
        )
    return buffer.getvalue()
