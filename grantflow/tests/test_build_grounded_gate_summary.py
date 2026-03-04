from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "build_grounded_gate_summary.py"
    spec = importlib.util.spec_from_file_location("build_grounded_gate_summary", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_summary_markdown_includes_gate_status_and_table():
    module = _load_module()
    summary = module.build_summary_markdown(
        report_payload={
            "suite_label": "grounded-eval",
            "case_count": 2,
            "passed_count": 2,
            "failed_count": 0,
            "all_passed": True,
            "cases": [
                {
                    "donor_id": "usaid",
                    "passed": True,
                    "metrics": {
                        "quality_score": 8.5,
                        "critic_score": 8.0,
                        "citation_confidence_avg": 0.66,
                        "non_retrieval_citation_rate": 0.0,
                        "traceability_gap_citation_rate": 0.0,
                        "fallback_namespace_citation_count": 0,
                    },
                },
                {
                    "donor_id": "eu",
                    "passed": True,
                    "metrics": {
                        "quality_score": 8.75,
                        "critic_score": 8.75,
                        "citation_confidence_avg": 0.7,
                        "non_retrieval_citation_rate": 0.0,
                        "traceability_gap_citation_rate": 0.0,
                        "fallback_namespace_citation_count": 0,
                    },
                },
            ],
            "seeded_corpus": {
                "seeded_total": 8,
                "errors": [],
                "donor_counts": {"usaid": 4, "eu": 4},
            },
        },
        grounded_comparison_payload={"has_regressions": False, "regression_count": 0, "warning_count": 1},
        ab_diff_payload={"guard": {"status": "passed", "failures": []}},
        expected_donors=["usaid", "eu"],
        min_seeded_total=1,
    )
    assert "# Grounded Gate Summary" in summary
    assert "Deterministic grounded gate: **PASS**" in summary
    assert "Seeded corpus gate: **PASS**" in summary
    assert "A/B guard status: **PASSED**" in summary
    assert "Trend regression gate: **PASS**" in summary
    assert "| Donor | Passed/Cases | Avg Quality" in summary
    assert "| usaid | 1/1 | 8.5" in summary


def test_build_summary_markdown_reports_seed_gate_failures():
    module = _load_module()
    summary = module.build_summary_markdown(
        report_payload={
            "suite_label": "grounded-eval",
            "case_count": 1,
            "passed_count": 1,
            "failed_count": 0,
            "all_passed": True,
            "cases": [],
            "seeded_corpus": {
                "seeded_total": 0,
                "errors": ["line 2: ingest failed"],
                "donor_counts": {"usaid": 1},
            },
        },
        ab_diff_payload=None,
        expected_donors=["usaid", "worldbank"],
        min_seeded_total=1,
    )
    assert "Seeded corpus gate: **FAIL**" in summary
    assert "## Seed Gate Errors" in summary
    assert "line 2: ingest failed" in summary
    assert "## Missing Expected Donor Seeds" in summary
    assert "worldbank" in summary
