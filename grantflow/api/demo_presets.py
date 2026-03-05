from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEMO_GENERATE_PRESETS_LEGACY: dict[str, dict[str, Any]] = {
    "usaid_gov_ai_kazakhstan": {
        "donor_id": "usaid",
        "title": "AI civil service (KZ)",
        "generate_payload": {
            "donor_id": "usaid",
            "input_context": {
                "project": "Responsible AI Skills for Civil Service Modernization",
                "country": "Kazakhstan",
                "region": "National with pilot cohorts in Astana and Almaty",
                "timeframe": "2026-2027 (24 months)",
                "problem": (
                    "Civil servants have uneven practical skills in safe, ethical, and effective AI use for "
                    "public administration."
                ),
                "target_population": (
                    "Mid-level and senior civil servants in policy, service delivery, and digital transformation units."
                ),
                "expected_change": (
                    "Agencies improve AI readiness, adopt governance guidance, and demonstrate early workflow "
                    "efficiency gains."
                ),
                "key_activities": [
                    "Needs assessment and baseline competency mapping",
                    "Responsible AI curriculum design for public administration",
                    "Cohort-based training and training-of-trainers",
                    "Applied labs for policy and service workflows",
                    "SOP and governance guidance drafting support",
                ],
            },
            "llm_mode": True,
            "hitl_enabled": True,
            "architect_rag_enabled": True,
            "strict_preflight": False,
        },
    },
    "eu_digital_governance_moldova": {
        "donor_id": "eu",
        "title": "Digital governance (MD)",
        "generate_payload": {
            "donor_id": "eu",
            "input_context": {
                "project": "Digital Governance Service Quality and Administrative Capacity",
                "country": "Moldova",
                "region": "National and selected municipalities",
                "timeframe": "2026-2028 (30 months)",
                "problem": "Public institutions face uneven digital service management capacity and inconsistent service quality.",
                "target_population": (
                    "Civil servants and municipal service managers in digital transformation and service delivery units."
                ),
                "expected_change": "Institutions adopt stronger service quality procedures and improve processing efficiency.",
                "key_activities": [
                    "Institutional workflow assessments",
                    "Training on service design and process improvement",
                    "Coaching for agency and municipal teams",
                    "Support for SOPs and service quality dashboards",
                ],
            },
            "llm_mode": True,
            "hitl_enabled": True,
            "architect_rag_enabled": True,
            "strict_preflight": False,
        },
    },
    "worldbank_public_sector_uzbekistan": {
        "donor_id": "worldbank",
        "title": "Public sector performance (UZ)",
        "generate_payload": {
            "donor_id": "worldbank",
            "input_context": {
                "project": "Public Sector Performance and Service Delivery Capacity Strengthening",
                "country": "Uzbekistan",
                "region": "National ministries and selected subnational administrations",
                "timeframe": "2026-2028 (36 months)",
                "problem": (
                    "Public agencies have uneven capabilities in performance management and evidence-based decision-making."
                ),
                "target_population": "Government managers and civil servants in reform, performance, and service delivery functions.",
                "expected_change": (
                    "Participating institutions adopt stronger performance management practices and improve selected services."
                ),
                "key_activities": [
                    "Institutional diagnostics and process mapping",
                    "Capacity development for performance management and data use",
                    "Technical assistance for service improvement plans",
                    "Process optimization pilots and adaptive reviews",
                ],
            },
            "llm_mode": True,
            "hitl_enabled": True,
            "architect_rag_enabled": True,
            "strict_preflight": False,
        },
    },
}

_DEMO_INGEST_PRESETS: dict[str, dict[str, Any]] = {
    "usaid_gov_ai_kazakhstan": {
        "donor_id": "usaid",
        "title": "AI civil service (KZ)",
        "metadata": {
            "source_type": "donor_guidance",
            "sector": "governance",
            "theme": "responsible_ai_public_sector",
            "country_focus": "Kazakhstan",
            "doc_family": "donor_policy",
        },
        "checklist_items": [
            {"id": "donor_policy", "label": "USAID donor policy / ADS guidance", "source_type": "donor_guidance"},
            {
                "id": "responsible_ai_guidance",
                "label": "Responsible AI / digital governance guidance",
                "source_type": "reference_guidance",
            },
            {
                "id": "country_context",
                "label": "Kazakhstan public administration / digital government context",
                "source_type": "country_context",
            },
            {
                "id": "competency_framework",
                "label": "Civil service competency / training framework",
                "source_type": "training_framework",
            },
        ],
        "recommended_docs": [
            "USAID ADS / policy guidance relevant to digital transformation, governance, or capacity strengthening",
            "Responsible AI / digital governance guidance approved for your organization",
            "Kazakhstan public administration or digital government policy/context documents",
            "Civil service training standards / competency frameworks (if available)",
        ],
    },
    "eu_digital_governance_moldova": {
        "donor_id": "eu",
        "title": "Digital governance (MD)",
        "metadata": {
            "source_type": "donor_guidance",
            "sector": "governance",
            "theme": "digital_service_delivery",
            "country_focus": "Moldova",
            "doc_family": "donor_results_guidance",
        },
        "checklist_items": [
            {
                "id": "donor_results_guidance",
                "label": "EU intervention logic / results framework guidance",
                "source_type": "donor_guidance",
            },
            {
                "id": "digital_governance_guidance",
                "label": "EU digital governance / service delivery references",
                "source_type": "reference_guidance",
            },
            {
                "id": "country_context",
                "label": "Moldova digitization policy / service standards",
                "source_type": "country_context",
            },
            {
                "id": "municipal_process_guidance",
                "label": "Municipal service process / quality guidance",
                "source_type": "implementation_reference",
            },
        ],
        "recommended_docs": [
            "EU intervention logic / results framework guidance relevant to governance and public administration reform",
            "EU digital governance or service delivery reform policy references",
            "Moldova public service digitization strategies / standards",
            "Municipal service quality standards or process management guidance",
        ],
    },
    "worldbank_public_sector_uzbekistan": {
        "donor_id": "worldbank",
        "title": "Public sector performance (UZ)",
        "metadata": {
            "source_type": "donor_guidance",
            "sector": "public_sector_reform",
            "theme": "performance_management_service_delivery",
            "country_focus": "Uzbekistan",
            "doc_family": "donor_results_guidance",
        },
        "checklist_items": [
            {"id": "donor_results_guidance", "label": "World Bank RF / M&E guidance", "source_type": "donor_guidance"},
            {
                "id": "project_reference_docs",
                "label": "World Bank public sector modernization project references",
                "source_type": "reference_guidance",
            },
            {
                "id": "country_context",
                "label": "Uzbekistan public administration reform context",
                "source_type": "country_context",
            },
            {
                "id": "agency_process_docs",
                "label": "Agency service standards / process maps",
                "source_type": "implementation_reference",
            },
        ],
        "recommended_docs": [
            "World Bank results framework / M&E guidance relevant to governance or public sector reform",
            "World Bank public sector modernization / service delivery project documents",
            "Uzbekistan public administration reform strategies / performance frameworks",
            "Agency service standards, process maps, or reform guidance used for pilots",
        ],
    },
}


def list_generate_legacy_preset_summaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for preset_key in sorted(_DEMO_GENERATE_PRESETS_LEGACY.keys()):
        preset = _DEMO_GENERATE_PRESETS_LEGACY[preset_key]
        rows.append(
            {
                "preset_key": preset_key,
                "donor_id": str(preset.get("donor_id") or "").strip().lower() or None,
                "title": str(preset.get("title") or "").strip() or None,
            }
        )
    return rows


def load_generate_legacy_preset(preset_key: str) -> dict[str, Any]:
    token = str(preset_key or "").strip()
    if not token:
        raise ValueError("Missing preset_key")
    if token not in _DEMO_GENERATE_PRESETS_LEGACY:
        known = ", ".join(sorted(_DEMO_GENERATE_PRESETS_LEGACY.keys()))
        raise ValueError(f"Unknown preset_key '{token}'. Available: {known}")
    payload = deepcopy(_DEMO_GENERATE_PRESETS_LEGACY[token])
    payload["preset_key"] = token
    return payload


def list_ingest_preset_summaries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for preset_key in sorted(_DEMO_INGEST_PRESETS.keys()):
        preset = _DEMO_INGEST_PRESETS[preset_key]
        rows.append(
            {
                "preset_key": preset_key,
                "donor_id": str(preset.get("donor_id") or "").strip().lower() or None,
                "title": str(preset.get("title") or "").strip() or None,
            }
        )
    return rows


def load_ingest_preset(preset_key: str) -> dict[str, Any]:
    token = str(preset_key or "").strip()
    if not token:
        raise ValueError("Missing preset_key")
    if token not in _DEMO_INGEST_PRESETS:
        known = ", ".join(sorted(_DEMO_INGEST_PRESETS.keys()))
        raise ValueError(f"Unknown preset_key '{token}'. Available: {known}")
    payload = deepcopy(_DEMO_INGEST_PRESETS[token])
    payload["preset_key"] = token
    return payload
