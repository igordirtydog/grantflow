from __future__ import annotations

from grantflow.eval.summary import build_eval_summary_markdown, donor_rows_from_report


def test_donor_rows_from_report_uses_structured_breakdown_when_present() -> None:
    payload = {
        "donor_quality_breakdown": {
            "usaid": {
                "cases_total": 2,
                "cases_passed": 1,
                "avg_quality_score": 7.25,
                "avg_critic_score": 7.0,
                "avg_retrieval_grounded_citation_rate": 0.7,
                "avg_non_retrieval_citation_rate": 0.3,
                "avg_traceability_gap_citation_rate": 0.15,
                "high_severity_fatal_flaws_total": 1,
            }
        }
    }
    rows = donor_rows_from_report(payload)
    assert len(rows) == 1
    assert rows[0]["donor_id"] == "usaid"
    assert rows[0]["cases_total"] == 2
    assert rows[0]["avg_high_severity_fatal_flaws_per_case"] == 0.5


def test_build_eval_summary_markdown_renders_gate_and_failed_cases() -> None:
    report = {
        "suite_label": "llm-eval-grounded-strict",
        "case_count": 2,
        "passed_count": 1,
        "failed_count": 1,
        "cases": [
            {
                "case_id": "ok1",
                "donor_id": "usaid",
                "passed": True,
                "metrics": {
                    "quality_score": 7.5,
                    "critic_score": 7.5,
                    "retrieval_grounded_citation_rate": 0.8,
                    "non_retrieval_citation_rate": 0.2,
                    "traceability_gap_citation_rate": 0.1,
                    "high_severity_fatal_flaw_count": 0,
                },
            },
            {
                "case_id": "bad1",
                "donor_id": "eu",
                "passed": False,
                "failed_checks": [{"name": "min_quality_score", "actual": 4.0, "expected": 6.0}],
                "metrics": {
                    "quality_score": 4.0,
                    "critic_score": 4.0,
                    "retrieval_grounded_citation_rate": 0.3,
                    "non_retrieval_citation_rate": 0.7,
                    "traceability_gap_citation_rate": 0.4,
                    "high_severity_fatal_flaw_count": 2,
                },
            },
        ],
    }
    comparison = {"regression_count": 1, "warning_count": 0, "has_regressions": True}
    gate = {
        "status": "fail",
        "reason": "1 donor gate checks failed",
        "failures": [
            {"donor_id": "eu", "name": "min_avg_quality_score", "expected": 6.0, "actual": 4.0},
        ],
    }
    md = build_eval_summary_markdown(
        report,
        title="LLM Grounded Strict Summary",
        comparison_payload=comparison,
        gate_payload=gate,
    )
    assert "## LLM Grounded Strict Summary" in md
    assert "Baseline comparison: regressions=`1`, warnings=`0`, has_regressions=`True`" in md
    assert "Donor gate: **FAIL**" in md
    assert "### Failed Cases" in md
    assert "`bad1` (eu)" in md
    assert "### Donor Gate Failures" in md
