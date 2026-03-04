from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _parse_csv_tokens(raw: str | None) -> list[str]:
    if raw is None:
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        token = str(part or "").strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)
    return rows


def _seed_gate_summary(
    *,
    report_payload: dict[str, Any],
    expected_donors: list[str],
    min_seeded_total: int,
) -> dict[str, Any]:
    seeded = report_payload.get("seeded_corpus")
    if not isinstance(seeded, dict):
        return {
            "status": "fail",
            "seeded_total": 0,
            "errors": ["seeded_corpus block is missing"],
            "missing_expected_donors": list(expected_donors),
            "donor_counts": {},
        }

    errors_raw = seeded.get("errors")
    errors = [str(item) for item in errors_raw] if isinstance(errors_raw, list) else []
    donor_counts_raw = seeded.get("donor_counts")
    donor_counts = donor_counts_raw if isinstance(donor_counts_raw, dict) else {}
    seeded_total = _as_int(seeded.get("seeded_total"), default=0)

    missing_expected = []
    for donor_id in expected_donors:
        if _as_int(donor_counts.get(donor_id), default=0) <= 0:
            missing_expected.append(donor_id)

    status = "pass"
    if errors or seeded_total < max(0, min_seeded_total) or missing_expected:
        status = "fail"
    return {
        "status": status,
        "seeded_total": seeded_total,
        "errors": errors,
        "missing_expected_donors": missing_expected,
        "donor_counts": donor_counts,
    }


def _donor_rows(report_payload: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for case in report_payload.get("cases") or []:
        if not isinstance(case, dict):
            continue
        donor_id = str(case.get("donor_id") or "unknown").strip().lower()
        row = grouped.setdefault(
            donor_id,
            {
                "donor_id": donor_id,
                "cases_total": 0,
                "cases_passed": 0,
                "quality_scores": [],
                "critic_scores": [],
                "citation_confidence_avg": [],
                "non_retrieval_rate": [],
                "traceability_gap_rate": [],
                "fallback_ns_total": 0,
            },
        )
        row["cases_total"] = _as_int(row.get("cases_total"), default=0) + 1
        if bool(case.get("passed")):
            row["cases_passed"] = _as_int(row.get("cases_passed"), default=0) + 1
        metrics = case.get("metrics") if isinstance(case.get("metrics"), dict) else {}
        row["quality_scores"].append(_as_float(metrics.get("quality_score")))
        row["critic_scores"].append(_as_float(metrics.get("critic_score")))
        row["citation_confidence_avg"].append(_as_float(metrics.get("citation_confidence_avg")))
        row["non_retrieval_rate"].append(_as_float(metrics.get("non_retrieval_citation_rate")))
        row["traceability_gap_rate"].append(_as_float(metrics.get("traceability_gap_citation_rate")))
        row["fallback_ns_total"] = _as_int(row.get("fallback_ns_total"), default=0) + _as_int(
            metrics.get("fallback_namespace_citation_count"),
            default=0,
        )

    rows: list[dict[str, Any]] = []
    for donor_id in sorted(grouped):
        row = grouped[donor_id]
        rows.append(
            {
                "donor_id": donor_id,
                "cases_total": _as_int(row.get("cases_total")),
                "cases_passed": _as_int(row.get("cases_passed")),
                "avg_quality": _avg(list(row.get("quality_scores") or [])),
                "avg_critic": _avg(list(row.get("critic_scores") or [])),
                "avg_citation_confidence": _avg(list(row.get("citation_confidence_avg") or [])),
                "avg_non_retrieval_rate": _avg(list(row.get("non_retrieval_rate") or [])),
                "avg_traceability_gap_rate": _avg(list(row.get("traceability_gap_rate") or [])),
                "fallback_ns_total": _as_int(row.get("fallback_ns_total")),
            }
        )
    return rows


def build_summary_markdown(
    *,
    report_payload: dict[str, Any],
    ab_diff_payload: dict[str, Any] | None = None,
    grounded_comparison_payload: dict[str, Any] | None = None,
    expected_donors: list[str] | None = None,
    min_seeded_total: int = 1,
) -> str:
    expected = [str(item).strip().lower() for item in (expected_donors or []) if str(item).strip()]
    seed_gate = _seed_gate_summary(
        report_payload=report_payload,
        expected_donors=expected,
        min_seeded_total=max(0, min_seeded_total),
    )
    donor_rows = _donor_rows(report_payload)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    suite_label = str(report_payload.get("suite_label") or "grounded-eval")
    case_count = _as_int(report_payload.get("case_count"))
    passed_count = _as_int(report_payload.get("passed_count"))
    failed_count = _as_int(report_payload.get("failed_count"))
    all_passed = bool(report_payload.get("all_passed"))
    gate_status = "PASS" if all_passed else "FAIL"

    lines = [
        "# Grounded Gate Summary",
        "",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Suite: `{suite_label}`",
        f"- Deterministic grounded gate: **{gate_status}** (`{passed_count}/{case_count}` passed, failed=`{failed_count}`)",
        (
            "- Seeded corpus gate: "
            + ("**PASS**" if str(seed_gate.get("status")) == "pass" else "**FAIL**")
            + f" (seeded_total=`{_as_int(seed_gate.get('seeded_total'))}`)"
        ),
    ]

    if ab_diff_payload is not None:
        guard = ab_diff_payload.get("guard") if isinstance(ab_diff_payload.get("guard"), dict) else {}
        guard_status = str(guard.get("status") or "not_configured")
        lines.append(f"- A/B guard status: **{guard_status.upper()}**")
        failures = guard.get("failures")
        if isinstance(failures, list) and failures:
            lines.append("- A/B guard failures:")
            for item in failures:
                if not isinstance(item, dict):
                    continue
                lines.append(f"  - `{item.get('donor_id')}` `{item.get('kind')}` observed=`{item.get('observed')}`")

    if grounded_comparison_payload is not None:
        has_regressions = bool(grounded_comparison_payload.get("has_regressions"))
        regression_count = _as_int(grounded_comparison_payload.get("regression_count"), default=0)
        warning_count = _as_int(grounded_comparison_payload.get("warning_count"), default=0)
        lines.append(
            "- Trend regression gate: "
            + ("**FAIL**" if has_regressions else "**PASS**")
            + f" (regressions=`{regression_count}`, warnings=`{warning_count}`)"
        )

    if donor_rows:
        lines.extend(
            [
                "",
                "## Donor Metrics",
                "",
                "| Donor | Passed/Cases | Avg Quality | Avg Critic | Avg Citation Conf | Avg Non-Retrieval | Avg Traceability Gap | Fallback NS Total |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in donor_rows:
            lines.append(
                "| {donor} | {passed}/{total} | {q} | {c} | {cc} | {nr} | {tg} | {fb} |".format(
                    donor=row.get("donor_id"),
                    passed=_as_int(row.get("cases_passed")),
                    total=_as_int(row.get("cases_total")),
                    q=row.get("avg_quality"),
                    c=row.get("avg_critic"),
                    cc=row.get("avg_citation_confidence"),
                    nr=row.get("avg_non_retrieval_rate"),
                    tg=row.get("avg_traceability_gap_rate"),
                    fb=_as_int(row.get("fallback_ns_total")),
                )
            )

    seed_errors = seed_gate.get("errors")
    if isinstance(seed_errors, list) and seed_errors:
        lines.extend(["", "## Seed Gate Errors"])
        for item in seed_errors:
            lines.append(f"- {item}")

    missing_expected = seed_gate.get("missing_expected_donors")
    if isinstance(missing_expected, list) and missing_expected:
        lines.extend(["", "## Missing Expected Donor Seeds"])
        for donor_id in missing_expected:
            lines.append(f"- {donor_id}")

    return "\n".join(lines) + "\n"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build markdown summary for grounded eval gate artifacts.")
    parser.add_argument("--grounded-json", type=Path, required=True, help="Path to grounded eval report JSON.")
    parser.add_argument(
        "--grounded-comparison-json",
        type=Path,
        default=None,
        help="Optional path to grounded regression comparison JSON.",
    )
    parser.add_argument("--ab-diff-json", type=Path, default=None, help="Optional grounded A/B diff JSON path.")
    parser.add_argument("--out", type=Path, required=True, help="Path to output markdown summary.")
    parser.add_argument(
        "--expected-donors",
        type=str,
        default="",
        help="Comma-separated expected donors for seeded corpus check.",
    )
    parser.add_argument(
        "--min-seeded-total",
        type=int,
        default=1,
        help="Minimum acceptable seeded_corpus.seeded_total value.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    grounded_payload = json.loads(args.grounded_json.read_text(encoding="utf-8"))
    if not isinstance(grounded_payload, dict):
        print("grounded report JSON root must be an object")
        return 2
    ab_payload: dict[str, Any] | None = None
    if args.ab_diff_json is not None:
        loaded = json.loads(args.ab_diff_json.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            ab_payload = loaded
    grounded_comparison_payload: dict[str, Any] | None = None
    if args.grounded_comparison_json is not None:
        loaded = json.loads(args.grounded_comparison_json.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            grounded_comparison_payload = loaded

    markdown = build_summary_markdown(
        report_payload=grounded_payload,
        ab_diff_payload=ab_payload,
        grounded_comparison_payload=grounded_comparison_payload,
        expected_donors=_parse_csv_tokens(args.expected_donors),
        min_seeded_total=max(0, int(args.min_seeded_total)),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote grounded gate summary: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
