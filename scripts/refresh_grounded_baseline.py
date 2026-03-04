from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from grantflow.eval.harness import (
    build_regression_baseline_snapshot,
    filter_eval_cases,
    load_eval_cases,
    run_eval_suite,
    seed_rag_corpus_from_manifest,
)


def _split_csv_args(values: list[str] | None) -> list[str]:
    rows: list[str] = []
    for raw in values or []:
        for token in str(raw or "").split(","):
            value = token.strip()
            if value:
                rows.append(value)
    return rows


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def refresh_grounded_baseline(
    *,
    cases_file: Path,
    out_snapshot: Path,
    suite_label: str,
    seed_rag_manifest: Path | None = None,
    allow_seed_errors: bool = False,
    allow_failing_suite: bool = False,
    donor_filters: list[str] | None = None,
    case_filters: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    cases = load_eval_cases(case_files=[cases_file])
    cases = filter_eval_cases(cases, donor_ids=donor_filters or None, case_ids=case_filters or None)
    if not cases:
        raise ValueError("No eval cases matched the provided filters.")

    seeded_summary: dict[str, Any] | None = None
    if seed_rag_manifest is not None:
        donor_ids_for_seed = sorted(
            {str(case.get("donor_id") or "").strip().lower() for case in cases if case.get("donor_id")}
        )
        seeded_summary = seed_rag_corpus_from_manifest(
            seed_rag_manifest,
            allowed_donor_ids=donor_ids_for_seed,
        )
        errors = list(seeded_summary.get("errors") or [])
        if errors and not allow_seed_errors:
            raise RuntimeError("RAG seeding failed: " + "; ".join(str(item) for item in errors))

    suite = run_eval_suite(cases, suite_label=suite_label, skip_expectations=False)
    if not suite.get("all_passed") and not allow_failing_suite:
        raise RuntimeError("Grounded suite failed; refuse to refresh baseline. Re-run with --allow-failing-suite to override.")

    if seeded_summary is not None:
        suite["seeded_corpus"] = seeded_summary

    snapshot = build_regression_baseline_snapshot(suite)
    out_snapshot.parent.mkdir(parents=True, exist_ok=True)
    out_snapshot.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot, seeded_summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh grounded regression baseline snapshot from current grounded suite.")
    parser.add_argument(
        "--confirm-refresh",
        action="store_true",
        help="Explicitly confirm baseline refresh (or set ALLOW_BASELINE_REFRESH=1).",
    )
    parser.add_argument(
        "--cases-file",
        type=Path,
        default=Path("grantflow/eval/cases/grounded_cases.json"),
        help="Grounded cases JSON file.",
    )
    parser.add_argument(
        "--seed-rag-manifest",
        type=Path,
        default=Path("docs/rag_seed_corpus/ingest_manifest.jsonl"),
        help="Manifest used to seed donor namespaces before running grounded suite.",
    )
    parser.add_argument(
        "--no-seed-rag",
        action="store_true",
        help="Skip RAG seeding step.",
    )
    parser.add_argument(
        "--allow-seed-errors",
        action="store_true",
        help="Allow seeding errors and continue (not recommended).",
    )
    parser.add_argument(
        "--allow-failing-suite",
        action="store_true",
        help="Allow writing baseline even when grounded suite has failures (not recommended).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("grantflow/eval/fixtures/grounded_regression_snapshot.json"),
        help="Output snapshot path.",
    )
    parser.add_argument(
        "--suite-label",
        type=str,
        default="grounded-eval",
        help="Suite label to run.",
    )
    parser.add_argument(
        "--donor-id",
        action="append",
        default=[],
        help="Optional donor filter (repeatable, supports comma-separated tokens).",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case filter (repeatable, supports comma-separated tokens).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not (bool(args.confirm_refresh) or _is_truthy(os.getenv("ALLOW_BASELINE_REFRESH"))):
        print("FAILED: baseline refresh requires explicit confirmation. Use --confirm-refresh or ALLOW_BASELINE_REFRESH=1.")
        return 1
    seed_manifest = None if bool(args.no_seed_rag) else Path(args.seed_rag_manifest)
    donor_filters = _split_csv_args(args.donor_id)
    case_filters = _split_csv_args(args.case_id)
    try:
        snapshot, seeded_summary = refresh_grounded_baseline(
            cases_file=Path(args.cases_file),
            seed_rag_manifest=seed_manifest,
            out_snapshot=Path(args.out),
            suite_label=str(args.suite_label),
            allow_seed_errors=bool(args.allow_seed_errors),
            allow_failing_suite=bool(args.allow_failing_suite),
            donor_filters=donor_filters,
            case_filters=case_filters,
        )
    except Exception as exc:
        print(f"FAILED: {exc}")
        return 1

    case_count = len(snapshot.get("cases") or {})
    print(f"Baseline snapshot refreshed: {args.out} (cases={case_count})")
    if seeded_summary is not None:
        print(
            "Seeded corpus: "
            f"seeded_total={int(seeded_summary.get('seeded_total') or 0)} "
            f"errors={len(list(seeded_summary.get('errors') or []))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
