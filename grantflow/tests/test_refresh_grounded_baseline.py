from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[2]
    script_path = root / "scripts" / "refresh_grounded_baseline.py"
    spec = importlib.util.spec_from_file_location("refresh_grounded_baseline", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_split_csv_args_expands_and_trims_tokens():
    module = _load_module()
    rows = module._split_csv_args([" usaid, eu ", "worldbank", "", "usaid"])
    assert rows == ["usaid", "eu", "worldbank", "usaid"]


def test_refresh_grounded_baseline_writes_snapshot(monkeypatch, tmp_path):
    module = _load_module()
    out_snapshot = tmp_path / "snapshot.json"

    monkeypatch.setattr(
        module,
        "load_eval_cases",
        lambda case_files=None: [{"case_id": "c1", "donor_id": "usaid"}],
    )
    monkeypatch.setattr(module, "filter_eval_cases", lambda cases, donor_ids=None, case_ids=None: cases)
    monkeypatch.setattr(
        module,
        "seed_rag_corpus_from_manifest",
        lambda manifest_path, allowed_donor_ids=None: {"seeded_total": 1, "errors": [], "donor_counts": {"usaid": 1}},
    )
    monkeypatch.setattr(
        module,
        "run_eval_suite",
        lambda cases, suite_label=None, skip_expectations=False: {
            "suite_label": suite_label,
            "all_passed": True,
            "cases": [{"case_id": "c1"}],
        },
    )
    monkeypatch.setattr(
        module,
        "build_regression_baseline_snapshot",
        lambda suite: {"schema_version": 1, "cases": {"c1": {"metrics": {}}}},
    )

    snapshot, seeded = module.refresh_grounded_baseline(
        cases_file=Path("grantflow/eval/cases/grounded_cases.json"),
        out_snapshot=out_snapshot,
        suite_label="grounded-eval",
        seed_rag_manifest=Path("docs/rag_seed_corpus/ingest_manifest.jsonl"),
    )
    assert snapshot["schema_version"] == 1
    assert seeded is not None
    assert out_snapshot.exists()
    loaded = json.loads(out_snapshot.read_text(encoding="utf-8"))
    assert loaded["cases"]["c1"]["metrics"] == {}


def test_refresh_grounded_baseline_fails_when_suite_fails_by_default(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "load_eval_cases",
        lambda case_files=None: [{"case_id": "c1", "donor_id": "usaid"}],
    )
    monkeypatch.setattr(module, "filter_eval_cases", lambda cases, donor_ids=None, case_ids=None: cases)
    monkeypatch.setattr(
        module,
        "run_eval_suite",
        lambda cases, suite_label=None, skip_expectations=False: {
            "suite_label": suite_label,
            "all_passed": False,
            "cases": [],
        },
    )
    monkeypatch.setattr(
        module,
        "build_regression_baseline_snapshot",
        lambda suite: {"schema_version": 1, "cases": {}},
    )

    try:
        module.refresh_grounded_baseline(
            cases_file=Path("grantflow/eval/cases/grounded_cases.json"),
            out_snapshot=tmp_path / "snapshot.json",
            suite_label="grounded-eval",
            seed_rag_manifest=None,
        )
    except RuntimeError as exc:
        assert "Grounded suite failed" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for failing suite")
