#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_TRACE_FILES = (
    "status.json",
    "quality.json",
    "critic.json",
    "citations.json",
    "versions.json",
    "events.json",
    "export-payload.json",
    "metrics.json",
)

REQUIRED_EXPORT_FILES = (
    "toc-review-package.docx",
    "logframe-review-package.xlsx",
    "review-package.zip",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _fmt(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


@dataclass
class CaseScorecard:
    case_dir: str
    preset_key: str
    donor_id: str
    status: str
    hitl_enabled: bool
    quality_score: float | None
    critic_score: float | None
    trace_complete: bool
    export_complete: bool
    hitl_history_present: bool
    baseline_present: bool
    missing_trace_files: list[str]
    missing_export_files: list[str]


def _load_baseline_presence(metrics_csv_path: Path) -> dict[str, bool]:
    if not metrics_csv_path.exists():
        return {}

    baseline_presence: dict[str, bool] = {}
    with metrics_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            case_dir = str(row.get("case_dir") or "").strip()
            if not case_dir:
                continue
            baseline_presence[case_dir] = any(
                str(row.get(key) or "").strip()
                for key in (
                    "baseline_time_to_first_draft_seconds",
                    "baseline_time_to_terminal_seconds",
                    "baseline_review_loops",
                    "baseline_notes",
                )
            )
    return baseline_presence


def _missing_files(case_path: Path, required_files: tuple[str, ...]) -> list[str]:
    return [name for name in required_files if not (case_path / name).exists()]


def _load_case_scorecards(
    pilot_pack_dir: Path,
    benchmark_rows: list[dict[str, Any]],
    baseline_presence: dict[str, bool],
) -> list[CaseScorecard]:
    cases: list[CaseScorecard] = []
    live_runs_dir = pilot_pack_dir / "live-runs"
    for row in benchmark_rows:
        case_dir = str(row.get("case_dir") or "").strip()
        if not case_dir:
            raise SystemExit(f"Missing case_dir in benchmark row: {row}")
        case_path = live_runs_dir / case_dir
        if not case_path.exists():
            raise SystemExit(f"Missing case directory: {case_path}")

        quality_path = case_path / "quality.json"
        quality_payload = _read_json(quality_path) if quality_path.exists() else {}
        missing_trace_files = _missing_files(case_path, REQUIRED_TRACE_FILES)
        missing_export_files = _missing_files(case_path, REQUIRED_EXPORT_FILES)
        hitl_history_present = (case_path / "hitl-history.json").exists()

        cases.append(
            CaseScorecard(
                case_dir=case_dir,
                preset_key=str(row.get("preset_key") or "").strip(),
                donor_id=str(row.get("donor_id") or "").strip(),
                status=str(row.get("status") or "").strip(),
                hitl_enabled=bool(row.get("hitl_enabled")),
                quality_score=_safe_float(quality_payload.get("quality_score", row.get("quality_score"))),
                critic_score=_safe_float(quality_payload.get("critic_score", row.get("critic_score"))),
                trace_complete=not missing_trace_files,
                export_complete=not missing_export_files,
                hitl_history_present=hitl_history_present,
                baseline_present=baseline_presence.get(case_dir, False),
                missing_trace_files=missing_trace_files,
                missing_export_files=missing_export_files,
            )
        )
    return cases


def _gate_status(passed: bool, *, conditional: bool = False) -> str:
    if passed:
        return "pass"
    if conditional:
        return "conditional"
    return "fail"


def _build_scorecard(
    cases: list[CaseScorecard],
    *,
    pilot_pack_name: str,
    min_avg_quality: float,
    min_avg_critic: float,
    min_terminal_done_rate: float,
) -> str:
    total_cases = len(cases)
    done_cases = sum(1 for case in cases if case.status.lower() == "done")
    trace_complete_cases = sum(1 for case in cases if case.trace_complete)
    export_complete_cases = sum(1 for case in cases if case.export_complete)
    baseline_cases = sum(1 for case in cases if case.baseline_present)
    hitl_cases = sum(1 for case in cases if case.hitl_enabled)
    hitl_history_cases = sum(1 for case in cases if case.hitl_enabled and case.hitl_history_present)

    avg_quality = _avg([case.quality_score for case in cases])
    avg_critic = _avg([case.critic_score for case in cases])
    done_rate = _pct(done_cases, total_cases)
    baseline_rate = _pct(baseline_cases, total_cases)

    fail_reasons: list[str] = []
    conditional_reasons: list[str] = []

    if done_rate < min_terminal_done_rate:
        fail_reasons.append(
            f"terminal completion below threshold ({done_cases}/{total_cases}, target >= {min_terminal_done_rate:.0%})"
        )
    if avg_quality is None or avg_quality < min_avg_quality:
        fail_reasons.append(
            f"average quality score below threshold ({_fmt(avg_quality)}, target >= {_fmt(min_avg_quality)})"
        )
    if avg_critic is None or avg_critic < min_avg_critic:
        fail_reasons.append(
            f"average critic score below threshold ({_fmt(avg_critic)}, target >= {_fmt(min_avg_critic)})"
        )
    if trace_complete_cases < total_cases:
        fail_reasons.append(f"trace artifact coverage incomplete ({trace_complete_cases}/{total_cases} cases)")
    if export_complete_cases < total_cases:
        fail_reasons.append(f"export artifact coverage incomplete ({export_complete_cases}/{total_cases} cases)")
    if hitl_cases and hitl_history_cases < hitl_cases:
        fail_reasons.append(f"HITL history missing for enabled cases ({hitl_history_cases}/{hitl_cases})")

    if baseline_cases < total_cases:
        conditional_reasons.append(
            f"baseline comparison not yet captured for all cases ({baseline_cases}/{total_cases})"
        )
    if hitl_cases == 0:
        conditional_reasons.append("no HITL evidence captured in this pack")

    if fail_reasons:
        verdict = "Not ready"
        readiness = "red"
    elif conditional_reasons:
        verdict = "Proceed with conditions"
        readiness = "amber"
    else:
        verdict = "Proceed to bounded pilot"
        readiness = "green"

    gate_rows = [
        (
            "Terminal completion",
            _gate_status(done_rate >= min_terminal_done_rate),
            f"{done_cases}/{total_cases} done",
            f"target >= {min_terminal_done_rate:.0%}",
        ),
        (
            "Average quality score",
            _gate_status(avg_quality is not None and avg_quality >= min_avg_quality),
            _fmt(avg_quality),
            f"target >= {_fmt(min_avg_quality)}",
        ),
        (
            "Average critic score",
            _gate_status(avg_critic is not None and avg_critic >= min_avg_critic),
            _fmt(avg_critic),
            f"target >= {_fmt(min_avg_critic)}",
        ),
        (
            "Trace artifact coverage",
            _gate_status(trace_complete_cases == total_cases),
            f"{trace_complete_cases}/{total_cases}",
            "status/quality/critic/citations/versions/events/export-payload/metrics",
        ),
        (
            "Export artifact coverage",
            _gate_status(export_complete_cases == total_cases),
            f"{export_complete_cases}/{total_cases}",
            "docx/xlsx/zip for every case",
        ),
        (
            "Baseline comparison coverage",
            _gate_status(baseline_cases == total_cases, conditional=True),
            f"{baseline_cases}/{total_cases}",
            "capture before buyer go/no-go review",
        ),
    ]

    lines: list[str] = []
    lines.append("# Pilot Scorecard")
    lines.append("")
    lines.append(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- Pilot pack: `{pilot_pack_name}`")
    lines.append("")
    lines.append("## Executive Verdict")
    lines.append(f"- Verdict: `{verdict}`")
    lines.append(f"- Readiness: `{readiness}`")
    lines.append("")
    lines.append("## Evidence Snapshot")
    lines.append(f"- Cases reviewed: `{total_cases}`")
    lines.append(f"- Terminal done cases: `{done_cases}/{total_cases}`")
    lines.append(f"- Average quality score: `{_fmt(avg_quality)}`")
    lines.append(f"- Average critic score: `{_fmt(avg_critic)}`")
    lines.append(f"- Trace-complete cases: `{trace_complete_cases}/{total_cases}`")
    lines.append(f"- Export-complete cases: `{export_complete_cases}/{total_cases}`")
    lines.append(f"- Cases with HITL enabled: `{hitl_cases}`")
    lines.append(
        f"- HITL-enabled cases with history: `{hitl_history_cases}/{hitl_cases}`"
        if hitl_cases
        else "- HITL-enabled cases with history: `0/0`"
    )
    lines.append(f"- Baseline-complete cases: `{baseline_cases}/{total_cases}` ({baseline_rate:.0%})")
    lines.append("")
    lines.append("## Gate Summary")
    lines.append("")
    lines.append("| Gate | Result | Actual | Expectation |")
    lines.append("|---|---|---|---|")
    for gate_name, status, actual, expectation in gate_rows:
        lines.append(f"| {gate_name} | `{status}` | {actual} | {expectation} |")
    lines.append("")
    lines.append("## Case Coverage")
    lines.append("")
    lines.append("| Preset | Donor | Status | HITL | Quality | Critic | Trace | Export | Baseline |")
    lines.append("|---|---|---|---|---:|---:|---|---|---|")
    for case in cases:
        lines.append(
            f"| `{case.preset_key}` | `{case.donor_id}` | {case.status} | "
            f"{'yes' if case.hitl_enabled else 'no'} | {_fmt(case.quality_score)} | {_fmt(case.critic_score)} | "
            f"{'complete' if case.trace_complete else 'missing'} | "
            f"{'complete' if case.export_complete else 'missing'} | "
            f"{'yes' if case.baseline_present else 'no'} |"
        )
    lines.append("")
    if fail_reasons:
        lines.append("## Blockers")
        for reason in fail_reasons:
            lines.append(f"- {reason}")
        lines.append("")
    if conditional_reasons:
        lines.append("## Conditions Before Buyer Decision")
        for reason in conditional_reasons:
            lines.append(f"- {reason}")
        lines.append("")
    lines.append("## Recommended Next Action")
    if verdict == "Not ready":
        lines.append("1. Fix failed gates and regenerate the pilot pack.")
        lines.append("2. Re-run `make pilot-scorecard-refresh` before sharing externally.")
    elif verdict == "Proceed with conditions":
        lines.append("1. Capture baseline metrics in `pilot-metrics.csv` for each case.")
        lines.append("2. Re-run `make pilot-scorecard` to refresh the decision memo.")
        lines.append("3. Use this scorecard with `buyer-brief.md` for the pilot go/no-go conversation.")
    else:
        lines.append("1. Use this scorecard and `buyer-brief.md` as the bounded pilot decision packet.")
        lines.append("2. Expand from demo presets to real customer proposal cases with baseline capture.")
    lines.append("")
    lines.append("## Notes")
    lines.append("- This scorecard evaluates demo/pilot evidence, not final donor submission quality.")
    lines.append("- Human compliance review remains mandatory before external submission.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a go/no-go pilot scorecard from an existing GrantFlow pilot pack."
    )
    parser.add_argument("--pilot-pack-dir", default="build/pilot-pack")
    parser.add_argument("--output", default="")
    parser.add_argument("--min-avg-quality", type=float, default=7.0)
    parser.add_argument("--min-avg-critic", type=float, default=7.0)
    parser.add_argument("--min-terminal-done-rate", type=float, default=1.0)
    args = parser.parse_args()

    pilot_pack_dir = Path(str(args.pilot_pack_dir)).resolve()
    benchmark_path = pilot_pack_dir / "live-runs" / "benchmark-results.json"
    if not benchmark_path.exists():
        raise SystemExit(f"Missing pilot benchmark results: {benchmark_path}")

    benchmark_rows = _read_json(benchmark_path)
    if not isinstance(benchmark_rows, list) or not benchmark_rows:
        raise SystemExit("pilot pack live-runs/benchmark-results.json must contain a non-empty list")

    baseline_presence = _load_baseline_presence(pilot_pack_dir / "pilot-metrics.csv")
    cases = _load_case_scorecards(pilot_pack_dir, benchmark_rows, baseline_presence)
    output_path = (
        Path(str(args.output)).resolve() if str(args.output).strip() else pilot_pack_dir / "pilot-scorecard.md"
    )
    output_path.write_text(
        _build_scorecard(
            cases,
            pilot_pack_name=pilot_pack_dir.name,
            min_avg_quality=args.min_avg_quality,
            min_avg_critic=args.min_avg_critic,
            min_terminal_done_rate=args.min_terminal_done_rate,
        ),
        encoding="utf-8",
    )
    print(f"pilot scorecard saved to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
