from __future__ import annotations

import pytest

from grantflow.api.demo_presets import (
    list_generate_legacy_preset_summaries,
    list_ingest_preset_summaries,
    load_generate_legacy_preset,
    load_ingest_preset,
)


def test_list_generate_legacy_preset_summaries_contains_expected_keys():
    rows = list_generate_legacy_preset_summaries()
    assert isinstance(rows, list) and rows
    keys = {str(item.get("preset_key") or "") for item in rows if isinstance(item, dict)}
    assert "usaid_gov_ai_kazakhstan" in keys
    assert "eu_digital_governance_moldova" in keys
    assert "worldbank_public_sector_uzbekistan" in keys


def test_load_generate_legacy_preset_returns_expected_structure():
    payload = load_generate_legacy_preset("usaid_gov_ai_kazakhstan")
    assert payload["preset_key"] == "usaid_gov_ai_kazakhstan"
    assert payload["donor_id"] == "usaid"
    generate_payload = payload.get("generate_payload")
    assert isinstance(generate_payload, dict)
    input_context = generate_payload.get("input_context")
    assert isinstance(input_context, dict)
    assert str(input_context.get("project") or "").strip() != ""
    assert str(input_context.get("country") or "").strip().lower() == "kazakhstan"


def test_load_generate_legacy_preset_raises_for_unknown_key():
    with pytest.raises(ValueError, match="Unknown preset_key"):
        load_generate_legacy_preset("missing-generate-preset")


def test_list_ingest_preset_summaries_contains_expected_keys():
    rows = list_ingest_preset_summaries()
    assert isinstance(rows, list) and rows
    keys = {str(item.get("preset_key") or "") for item in rows if isinstance(item, dict)}
    assert "usaid_gov_ai_kazakhstan" in keys
    assert "eu_digital_governance_moldova" in keys
    assert "worldbank_public_sector_uzbekistan" in keys


def test_load_ingest_preset_returns_expected_structure():
    payload = load_ingest_preset("eu_digital_governance_moldova")
    assert payload["preset_key"] == "eu_digital_governance_moldova"
    assert payload["donor_id"] == "eu"
    assert isinstance(payload.get("metadata"), dict)
    assert isinstance(payload.get("checklist_items"), list)
    assert isinstance(payload.get("recommended_docs"), list)


def test_load_ingest_preset_raises_for_unknown_key():
    with pytest.raises(ValueError, match="Unknown preset_key"):
        load_ingest_preset("missing-preset")
