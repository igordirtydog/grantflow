#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PRESET_KEYS = (
    "usaid_gov_ai_kazakhstan",
    "eu_digital_governance_moldova",
    "worldbank_public_sector_uzbekistan",
)


def _json_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _bytes_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
) -> bytes:
    headers: dict[str, str] = {}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _slugify(value: str) -> str:
    token = "".join(ch if ch.isalnum() else "-" for ch in value.strip().lower())
    while "--" in token:
        token = token.replace("--", "-")
    return token.strip("-") or "case"


def _wait_for_terminal_status(
    base_url: str,
    job_id: str,
    *,
    api_key: str | None,
    timeout_s: float,
    poll_interval_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _json_request("GET", f"{base_url}/status/{job_id}", api_key=api_key)
        token = str(status.get("status") or "").strip().lower()
        if token in {"done", "error", "pending_hitl"}:
            return status
        time.sleep(poll_interval_s)
    raise RuntimeError(f"Timed out waiting for terminal status for job {job_id}")


def _drain_hitl_to_done(
    base_url: str,
    job_id: str,
    *,
    api_key: str | None,
    initial_status: dict[str, Any],
    timeout_s: float,
    poll_interval_s: float,
    max_cycles: int = 6,
) -> dict[str, Any]:
    status = initial_status
    for _ in range(max_cycles):
        if str(status.get("status") or "").strip().lower() == "done":
            return status
        if str(status.get("status") or "").strip().lower() != "pending_hitl":
            raise RuntimeError(f"Unexpected HITL status for job {job_id}: {status.get('status')}")
        checkpoint_id = str(status.get("checkpoint_id") or "").strip()
        checkpoint_stage = str(status.get("checkpoint_stage") or "").strip().lower()
        if not checkpoint_id:
            raise RuntimeError(f"Missing checkpoint_id for pending HITL job {job_id}")

        _json_request(
            "POST",
            f"{base_url}/hitl/approve",
            payload={
                "checkpoint_id": checkpoint_id,
                "approved": True,
                "feedback": f"Auto-approved by demo-pack at {checkpoint_stage or 'checkpoint'} stage",
            },
            api_key=api_key,
        )
        _json_request("POST", f"{base_url}/resume/{job_id}", payload={}, api_key=api_key)
        status = _wait_for_terminal_status(
            base_url,
            job_id,
            api_key=api_key,
            timeout_s=timeout_s,
            poll_interval_s=poll_interval_s,
        )
    raise RuntimeError(f"HITL job {job_id} did not reach done within {max_cycles} cycles")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_summary(root: Path, rows: list[dict[str, Any]], *, llm_mode: bool, hitl_preset_key: str | None) -> str:
    lines: list[str] = []
    lines.append(f"# Demo Pack — {root.name}")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Scope")
    lines.append(f"- Mode: `llm_mode={'true' if llm_mode else 'false'}`")
    lines.append("- Source: live API run via `scripts/demo_pack.py`")
    if hitl_preset_key:
        lines.append(f"- Auto-HITL case: `{hitl_preset_key}`")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.append("| Preset | Donor | Job ID | Status | Quality | Critic | Citations | HITL |")
    lines.append("|---|---|---|---|---:|---:|---:|---|")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.get('preset_key')}`",
                    f"`{row.get('donor_id')}`",
                    f"`{row.get('job_id')}`",
                    str(row.get("status")),
                    str(row.get("quality_score")),
                    str(row.get("critic_score")),
                    str(row.get("citation_count")),
                    "yes" if row.get("hitl_enabled") else "no",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Files")
    for row in rows:
        case_slug = str(row.get("case_dir") or "")
        lines.append(
            f"- `{case_slug}/generate-request.json`, `{case_slug}/generate-response.json`, "
            f"`{case_slug}/status.json`, `{case_slug}/quality.json`, `{case_slug}/critic.json`"
        )
        lines.append(
            f"- `{case_slug}/citations.json`, `{case_slug}/versions.json`, `{case_slug}/events.json`, "
            f"`{case_slug}/export-payload.json`, `{case_slug}/review-package.zip`"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("- This bundle is intended for demos and pilot evaluation, not final donor submission.")
    lines.append("- Grounding and citation quality remain dependent on corpus quality when RAG is enabled.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a reproducible GrantFlow demo bundle from a live API.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default="build/demo-pack")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--preset-keys", default=",".join(DEFAULT_PRESET_KEYS))
    parser.add_argument("--hitl-preset-key", default=DEFAULT_PRESET_KEYS[0])
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=0.25)
    parser.add_argument("--llm-mode", action="store_true")
    parser.add_argument("--architect-rag-enabled", action="store_true")
    args = parser.parse_args()

    base_url = str(args.api_base).rstrip("/")
    api_key = str(args.api_key).strip() or None
    output_dir = Path(str(args.output_dir)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    preset_keys = [token.strip() for token in str(args.preset_keys).split(",") if token.strip()]
    if not preset_keys:
        raise SystemExit("No preset keys configured")

    hitl_preset_key = str(args.hitl_preset_key).strip() or None
    if hitl_preset_key and hitl_preset_key not in preset_keys:
        raise SystemExit("--hitl-preset-key must be included in --preset-keys")

    summary_rows: list[dict[str, Any]] = []

    for preset_key in preset_keys:
        preset_detail = _json_request("GET", f"{base_url}/generate/presets/{preset_key}", api_key=api_key)
        generate_payload = dict(preset_detail.get("generate_payload") or {})
        donor_id = str(generate_payload.get("donor_id") or preset_detail.get("donor_id") or "").strip()
        if not donor_id:
            raise RuntimeError(f"Could not resolve donor_id for preset {preset_key}")

        hitl_enabled = bool(hitl_preset_key and preset_key == hitl_preset_key)
        request_payload = {
            "preset_key": preset_key,
            "preset_type": "auto",
            "llm_mode": bool(args.llm_mode),
            "hitl_enabled": hitl_enabled,
            "architect_rag_enabled": bool(args.architect_rag_enabled),
        }

        case_dir_name = f"{_slugify(donor_id)}-{_slugify(preset_key)}"
        case_dir = output_dir / case_dir_name
        case_dir.mkdir(parents=True, exist_ok=True)
        _write_json(case_dir / "preset-detail.json", preset_detail)
        _write_json(case_dir / "generate-request.json", request_payload)

        generate_response = _json_request(
            "POST",
            f"{base_url}/generate/from-preset",
            payload=request_payload,
            api_key=api_key,
        )
        _write_json(case_dir / "generate-response.json", generate_response)

        job_id = str(generate_response.get("job_id") or "").strip()
        if not job_id:
            raise RuntimeError(f"Missing job_id for preset {preset_key}")

        status = _wait_for_terminal_status(
            base_url,
            job_id,
            api_key=api_key,
            timeout_s=float(args.timeout_seconds),
            poll_interval_s=float(args.poll_interval_seconds),
        )
        if str(status.get("status") or "").strip().lower() == "pending_hitl":
            status = _drain_hitl_to_done(
                base_url,
                job_id,
                api_key=api_key,
                initial_status=status,
                timeout_s=float(args.timeout_seconds),
                poll_interval_s=float(args.poll_interval_seconds),
            )

        endpoints = {
            "status.json": f"{base_url}/status/{job_id}",
            "quality.json": f"{base_url}/status/{job_id}/quality",
            "critic.json": f"{base_url}/status/{job_id}/critic",
            "citations.json": f"{base_url}/status/{job_id}/citations",
            "versions.json": f"{base_url}/status/{job_id}/versions",
            "metrics.json": f"{base_url}/status/{job_id}/metrics",
            "events.json": f"{base_url}/status/{job_id}/events",
            "hitl-history.json": f"{base_url}/status/{job_id}/hitl/history",
            "export-payload.json": f"{base_url}/status/{job_id}/export-payload",
        }
        fetched: dict[str, dict[str, Any]] = {}
        for filename, url in endpoints.items():
            payload = _json_request("GET", url, api_key=api_key)
            fetched[filename] = payload
            _write_json(case_dir / filename, payload)

        export_payload = dict(fetched["export-payload.json"].get("payload") or {})
        for export_format, filename in (
            ("both", "review-package.zip"),
            ("docx", "toc-review-package.docx"),
            ("xlsx", "logframe-review-package.xlsx"),
        ):
            content = _bytes_request(
                "POST",
                f"{base_url}/export",
                payload={"payload": export_payload, "format": export_format},
                api_key=api_key,
            )
            (case_dir / filename).write_bytes(content)

        quality_payload = fetched["quality.json"]
        citations_payload = fetched["citations.json"]
        final_status_payload = fetched["status.json"]
        final_donor_id = str(
            (final_status_payload.get("state") or {}).get("donor_id")
            or (final_status_payload.get("state") or {}).get("donor")
            or donor_id
        ).strip()

        summary_rows.append(
            {
                "preset_key": preset_key,
                "donor_id": final_donor_id,
                "job_id": job_id,
                "status": final_status_payload.get("status"),
                "quality_score": quality_payload.get("quality_score"),
                "critic_score": quality_payload.get("critic_score"),
                "citation_count": citations_payload.get("citation_count"),
                "hitl_enabled": hitl_enabled,
                "case_dir": case_dir_name,
            }
        )

    _write_json(output_dir / "benchmark-results.json", summary_rows)
    (output_dir / "summary.md").write_text(
        _build_summary(
            output_dir,
            summary_rows,
            llm_mode=bool(args.llm_mode),
            hitl_preset_key=hitl_preset_key,
        ),
        encoding="utf-8",
    )
    print(f"demo pack saved to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
