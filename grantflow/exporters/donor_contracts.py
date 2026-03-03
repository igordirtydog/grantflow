from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from grantflow.exporters.template_profile import (
    TEMPLATE_DISPLAY_NAMES,
    build_export_template_profile,
    normalize_export_template_key,
)

DONOR_DOCX_EXPECTED_HEADINGS: dict[str, list[str]] = {
    "usaid": ["USAID Results Framework", "Project Goal", "Development Objectives", "Critical Assumptions"],
    "eu": ["EU Intervention Logic", "Overall Objective", "Specific Objectives", "Expected Outcomes"],
    "worldbank": [
        "World Bank Results Framework",
        "Project Development Objective (PDO)",
        "Objectives",
        "Results Chain",
    ],
}

DONOR_XLSX_REQUIRED_SHEETS: dict[str, list[str]] = {
    "usaid": ["LogFrame", "USAID_RF", "Template Meta"],
    "eu": ["LogFrame", "EU_Intervention", "EU_Assumptions_Risks", "Template Meta"],
    "worldbank": ["LogFrame", "WB_Results", "Template Meta"],
}

DONOR_XLSX_PRIMARY_SHEET: dict[str, str] = {
    "usaid": "USAID_RF",
    "eu": "EU_Intervention",
    "worldbank": "WB_Results",
}

DONOR_XLSX_PRIMARY_HEADERS: dict[str, list[str]] = {
    "usaid": ["DO ID", "DO Description", "IR ID", "IR Description"],
    "eu": ["Level", "ID", "Title", "Description"],
    "worldbank": ["Level", "ID", "Title", "Description"],
}


def evaluate_export_contract(
    *,
    donor_id: str,
    toc_payload: Dict[str, Any],
    workbook_sheetnames: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    donor_key = normalize_export_template_key(donor_id)
    profile = build_export_template_profile(donor_id=donor_id, toc_payload=toc_payload)

    required_sections = list(profile.get("required_sections") or [])
    missing_required_sections = list(profile.get("missing_sections") or [])
    present_required_sections = list(profile.get("present_sections") or [])

    required_sheets = list(DONOR_XLSX_REQUIRED_SHEETS.get(donor_key, []))
    workbook_validation_enabled = workbook_sheetnames is not None
    actual_sheets = [str(x) for x in (workbook_sheetnames or [])] if workbook_validation_enabled else []
    missing_required_sheets = [name for name in required_sheets if name not in actual_sheets] if workbook_validation_enabled else []

    expected_docx_headings = list(DONOR_DOCX_EXPECTED_HEADINGS.get(donor_key, []))
    primary_sheet = DONOR_XLSX_PRIMARY_SHEET.get(donor_key)
    primary_headers = list(DONOR_XLSX_PRIMARY_HEADERS.get(donor_key, []))

    status = "pass" if not missing_required_sections and not missing_required_sheets else "warning"
    warnings: list[str] = []
    if missing_required_sections:
        warnings.append("missing_required_toc_sections")
    if workbook_validation_enabled and missing_required_sheets:
        warnings.append("missing_required_workbook_sheets")

    return {
        "donor_id": str(donor_id or ""),
        "template_key": donor_key,
        "template_display_name": TEMPLATE_DISPLAY_NAMES.get(donor_key, TEMPLATE_DISPLAY_NAMES["generic"]),
        "required_sections": required_sections,
        "present_sections": present_required_sections,
        "missing_required_sections": missing_required_sections,
        "required_sheets": required_sheets,
        "actual_sheets": actual_sheets,
        "missing_required_sheets": missing_required_sheets,
        "expected_docx_headings": expected_docx_headings,
        "expected_primary_sheet": primary_sheet,
        "expected_primary_sheet_headers": primary_headers,
        "workbook_validation_enabled": workbook_validation_enabled,
        "status": status,
        "warnings": warnings,
    }
