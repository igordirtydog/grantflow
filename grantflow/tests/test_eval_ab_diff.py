from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_eval_ab_diff_module():
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "eval_ab_diff.py"
    spec = importlib.util.spec_from_file_location("eval_ab_diff", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_ab_diff_guard_pass_and_fail():
    module = _load_eval_ab_diff_module()

    payload = {
        "donor_summary": {
            "usaid": {"a_non_retrieval_rate_avg": 0.2, "a_retrieval_grounded_rate_avg": 0.8},
            "worldbank": {"a_non_retrieval_rate_avg": 0.5, "a_retrieval_grounded_rate_avg": 0.6},
        }
    }

    passed = module._evaluate_guard(
        payload=payload,
        guard_donors=["usaid"],
        max_a_non_retrieval_rate=0.35,
        min_a_retrieval_grounded_rate=0.7,
    )
    assert passed["status"] == "passed"
    assert passed["failures"] == []

    failed = module._evaluate_guard(
        payload=payload,
        guard_donors=["usaid", "worldbank"],
        max_a_non_retrieval_rate=0.35,
        min_a_retrieval_grounded_rate=0.7,
    )
    assert failed["status"] == "failed"
    assert len(failed["failures"]) == 2
    failure_keys = {(row["donor_id"], row["kind"]) for row in failed["failures"]}
    assert ("worldbank", "max_a_non_retrieval_rate") in failure_keys
    assert ("worldbank", "min_a_retrieval_grounded_rate") in failure_keys


def test_eval_ab_diff_guard_tracks_missing_donors():
    module = _load_eval_ab_diff_module()

    payload = {"donor_summary": {"usaid": {"a_non_retrieval_rate_avg": 0.1, "a_retrieval_grounded_rate_avg": 0.9}}}
    guard = module._evaluate_guard(
        payload=payload,
        guard_donors=["usaid", "giz"],
        max_a_non_retrieval_rate=0.35,
        min_a_retrieval_grounded_rate=0.7,
    )
    assert guard["status"] == "passed"
    assert guard["missing_donors"] == ["giz"]


def test_eval_ab_diff_guard_not_configured_without_thresholds():
    module = _load_eval_ab_diff_module()
    guard = module._evaluate_guard(
        payload={"donor_summary": {"usaid": {"a_non_retrieval_rate_avg": 0.1}}},
        guard_donors=["usaid"],
        max_a_non_retrieval_rate=None,
        min_a_retrieval_grounded_rate=None,
    )
    assert guard["status"] == "not_configured"


def test_eval_ab_diff_parse_guard_donors_deduplicates_and_normalizes():
    module = _load_eval_ab_diff_module()
    rows = module._parse_guard_donors(" USAID,worldbank,usaid, , EU ")
    assert rows == ["usaid", "worldbank", "eu"]
