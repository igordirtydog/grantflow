from __future__ import annotations

from grantflow.eval.sample_presets import (
    available_sample_ids,
    build_generate_payload,
    list_sample_preset_summaries,
    load_sample_payload,
)


def test_sample_presets_available_ids_are_stable():
    sample_ids = available_sample_ids()
    assert "rbm-usaid-ai-civil-service-kazakhstan" in sample_ids
    assert "rbm-eu-youth-employment-jordan" in sample_ids


def test_load_sample_payload_returns_expected_shape():
    payload = load_sample_payload("rbm-usaid-ai-civil-service-kazakhstan")
    assert payload["donor_id"] == "usaid"
    program_context = payload.get("program_context")
    assert isinstance(program_context, dict)
    assert str(program_context.get("title") or "").strip() != ""


def test_build_generate_payload_applies_runtime_flags():
    payload = build_generate_payload(
        "rbm-eu-youth-employment-jordan",
        llm_mode=True,
        hitl_enabled=True,
        architect_rag_enabled=True,
        strict_preflight=True,
    )
    assert payload["donor_id"] == "eu"
    assert payload["llm_mode"] is True
    assert payload["hitl_enabled"] is True
    assert payload["architect_rag_enabled"] is True
    assert payload["strict_preflight"] is True
    input_context = payload.get("input_context")
    assert isinstance(input_context, dict)
    assert str(input_context.get("country") or "").strip().lower() == "jordan"


def test_list_sample_preset_summaries_contains_source_metadata():
    rows = list_sample_preset_summaries()
    assert isinstance(rows, list) and rows
    by_id = {str(item.get("sample_id") or ""): item for item in rows if isinstance(item, dict)}
    usaid = by_id["rbm-usaid-ai-civil-service-kazakhstan"]
    assert usaid["donor_id"] == "usaid"
    assert usaid["source_file"] == "docs/samples/rbm-sample-usaid-ai-civil-service-kazakhstan.json"
