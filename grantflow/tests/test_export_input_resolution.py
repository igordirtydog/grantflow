from __future__ import annotations

from grantflow.api.app import ExportRequest, _resolve_export_inputs


def test_resolve_export_inputs_reads_critic_findings_from_legacy_state_alias():
    req = ExportRequest(
        payload={
            "state": {
                "donor_id": "usaid",
                "toc_draft": {"toc": {"brief": "sample"}},
                "logframe_draft": {"indicators": []},
                "critic_fatal_flaws": [
                    "Missing baseline and target for indicator.",
                ],
            }
        },
        format="docx",
    )

    toc, logframe, donor_id, citations, critic_findings, review_comments = _resolve_export_inputs(req)

    assert donor_id == "usaid"
    assert toc["toc"]["brief"] == "sample"
    assert logframe["indicators"] == []
    assert citations == []
    assert review_comments == []
    assert len(critic_findings) == 1
    finding = critic_findings[0]
    assert finding["id"] == finding["finding_id"]
    assert finding["code"] == "LEGACY_UNSTRUCTURED_FINDING"
    assert finding["message"].startswith("Missing baseline and target")
