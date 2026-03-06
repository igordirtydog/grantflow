from __future__ import annotations

from grantflow.swarm.retrieval_query import build_stage_query_text, donor_query_preset_terms


def test_donor_query_preset_terms_are_donor_aware():
    wb_terms = donor_query_preset_terms("worldbank")
    eu_terms = donor_query_preset_terms("eu")
    assert "project development objective" in wb_terms.lower()
    assert "results chain" in wb_terms.lower()
    assert "intermediate results indicators" in wb_terms.lower()
    assert "intervention logic" in eu_terms.lower()
    assert "specific objectives" in eu_terms.lower()
    assert "means of verification" in eu_terms.lower()


def test_build_stage_query_text_includes_context_hints_and_toc_clues():
    state = {
        "donor_id": "worldbank",
        "input_context": {
            "project": "Public Service Reform",
            "country": "Uzbekistan",
            "sector": "governance",
            "theme": "service_delivery",
        },
    }
    query = build_stage_query_text(
        state=state,
        stage="architect",
        project="Public Service Reform",
        country="Uzbekistan",
        revision_hint="Strengthen measurability",
        toc_payload={"project_development_objective": "Improve service delivery outcomes"},
    )
    lowered = query.lower()
    assert "architect" in lowered
    assert "public service reform" in lowered
    assert "uzbekistan" in lowered
    assert "strengthen measurability" in lowered
    assert "project development objective" in lowered
    assert "sector: governance" in lowered
    assert "theme: service_delivery" in lowered


def test_build_stage_query_text_includes_eu_and_worldbank_toc_specific_hints():
    eu_query = build_stage_query_text(
        state={"donor_id": "eu", "input_context": {"project": "Digital Governance", "country": "Moldova"}},
        stage="architect",
        project="Digital Governance",
        country="Moldova",
        toc_payload={
            "overall_objective": {
                "title": "Improve digital governance performance",
                "rationale": "Improve service accountability",
            },
            "specific_objectives": [{"title": "Strengthen institutional capacity"}],
            "expected_outcomes": [{"expected_change": "Institutions demonstrate measurable improvements"}],
        },
    )
    wb_query = build_stage_query_text(
        state={
            "donor_id": "worldbank",
            "input_context": {"project": "Public Sector Performance", "country": "Uzbekistan"},
        },
        stage="architect",
        project="Public Sector Performance",
        country="Uzbekistan",
        toc_payload={
            "project_development_objective": "Improve service delivery performance",
            "objectives": [{"title": "Strengthen institutional performance"}],
            "results_chain": [{"description": "Agencies implement workflow improvements"}],
        },
    )

    eu_lower = eu_query.lower()
    wb_lower = wb_query.lower()
    assert "improve digital governance performance" in eu_lower
    assert "strengthen institutional capacity" in eu_lower
    assert "institutions demonstrate measurable improvements" in eu_lower
    assert "improve service delivery performance" in wb_lower
    assert "strengthen institutional performance" in wb_lower
    assert "agencies implement workflow improvements" in wb_lower
