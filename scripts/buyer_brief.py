#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float | int | None]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _format_num(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _build_brief(
    rows: list[dict[str, Any]],
    *,
    pilot_pack_name: str,
    include_productization_memo: bool,
) -> str:
    done_count = sum(1 for row in rows if str(row.get("status") or "").strip().lower() == "done")
    hitl_count = sum(1 for row in rows if bool(row.get("hitl_enabled")))
    avg_quality = _avg([_safe_float(row.get("quality_score")) for row in rows])
    avg_critic = _avg([_safe_float(row.get("critic_score")) for row in rows])
    avg_citations = _avg([_safe_int(row.get("citation_count")) for row in rows])

    donors = sorted({str(row.get("donor_id") or "").strip() for row in rows if str(row.get("donor_id") or "").strip()})

    lines: list[str] = []
    lines.append("# GrantFlow Buyer Brief")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(
        "GrantFlow is a proposal operations backend for institutional funding workflows. "
        "This brief summarizes a pilot-ready evidence bundle generated from live runs and export artifacts."
    )
    lines.append("")
    lines.append("## Current Evidence Snapshot")
    lines.append(f"- Pilot pack: `{pilot_pack_name}`")
    lines.append(f"- Cases reviewed: `{len(rows)}`")
    lines.append(f"- Terminal done cases: `{done_count}/{len(rows)}`")
    lines.append(f"- Donors represented: {', '.join(f'`{donor}`' for donor in donors) if donors else '-' }")
    lines.append(f"- Cases with HITL review path: `{hitl_count}`")
    lines.append(f"- Average quality score: `{_format_num(avg_quality)}`")
    lines.append(f"- Average critic score: `{_format_num(avg_critic)}`")
    lines.append(f"- Average citation count: `{_format_num(avg_citations)}`")
    lines.append("")
    lines.append("## What This Demonstrates")
    lines.append("- Structured draft generation through a controlled pipeline, not one-shot text output.")
    lines.append(
        "- Reviewable traces available per case: status, quality, critic findings, citations, versions, events."
    )
    lines.append("- Optional human checkpoint flow with approve/resume behavior.")
    lines.append("- Exportable review artifacts for downstream proposal workflow.")
    lines.append("")
    lines.append("## Why This Matters To Proposal Teams")
    lines.append("- Reduces review chaos by keeping draft state and evidence in one workflow.")
    lines.append("- Improves evaluability of draft quality before formal compliance sign-off.")
    lines.append("- Creates reusable proposal operations infrastructure instead of ad-hoc drafting.")
    lines.append("")
    lines.append("## Recommended Pilot Scope")
    lines.append("- Start with `2-3` donors and `5-10` representative proposal cases.")
    lines.append("- Capture baseline cycle-time and review-loop metrics before pilot start.")
    lines.append("- Use evidence from `live-runs/` plus `pilot-evaluation-checklist.md` for go/no-go review.")
    lines.append("")
    lines.append("## Important Constraints")
    lines.append("- These materials are pilot artifacts, not final donor submissions.")
    lines.append("- Grounding quality remains corpus-dependent when retrieval is enabled.")
    lines.append("- Final compliance responsibility remains with human reviewers.")
    if include_productization_memo:
        lines.append(
            "- Productization and enterprise-readiness gaps are documented separately in `productization-gaps-memo.md`."
        )
    lines.append("")
    lines.append("## Suggested Next Conversation")
    lines.append("1. Choose target donors and real proposal cases for a bounded pilot.")
    lines.append("2. Define pilot success metrics and review owners.")
    lines.append("3. Run a pilot bundle and compare process outcomes against baseline.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a short buyer-facing executive brief from a GrantFlow pilot pack."
    )
    parser.add_argument("--pilot-pack-dir", default="build/pilot-pack")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    pilot_pack_dir = Path(str(args.pilot_pack_dir)).resolve()
    benchmark_path = pilot_pack_dir / "live-runs" / "benchmark-results.json"
    if not benchmark_path.exists():
        raise SystemExit(f"Missing pilot benchmark results: {benchmark_path}")

    rows = _read_json(benchmark_path)
    if not isinstance(rows, list) or not rows:
        raise SystemExit("pilot pack live-runs/benchmark-results.json must contain a non-empty list")

    output_path = Path(str(args.output)).resolve() if str(args.output).strip() else pilot_pack_dir / "buyer-brief.md"
    include_productization_memo = (pilot_pack_dir / "productization-gaps-memo.md").exists()
    output_path.write_text(
        _build_brief(
            rows,
            pilot_pack_name=pilot_pack_dir.name,
            include_productization_memo=include_productization_memo,
        ),
        encoding="utf-8",
    )
    print(f"buyer brief saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
