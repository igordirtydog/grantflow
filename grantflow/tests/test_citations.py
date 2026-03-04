from __future__ import annotations

from grantflow.swarm.citations import append_citations, normalize_citation


def test_normalize_citation_normalizes_namespace_and_alias_fields():
    row = normalize_citation(
        {
            "stage": "architect",
            "citation_type": "rag_claim_support",
            "namespace": " Tenant A / USAID ADS 201 ",
            "chunk_id": "chunk-1",
            "rank": "2",
            "citation_confidence": "1.2",
        }
    )
    assert row["namespace"] == "Tenant A / USAID ADS 201"
    assert row["namespace_normalized"] == "tenant_a/usaid_ads_201"
    assert row["doc_id"] == "chunk-1"
    assert row["chunk_id"] == "chunk-1"
    assert row["retrieval_rank"] == 2
    assert row["evidence_rank"] == 2
    assert row["retrieval_confidence"] == 1.0
    assert row["evidence_score"] == 1.0
    assert row["citation_confidence"] == 1.0


def test_normalize_citation_generates_synthetic_doc_id_for_retrieval_grounded_rows():
    row = normalize_citation(
        {
            "stage": "architect",
            "citation_type": "rag_claim_support",
            "namespace": "tenant_a/usaid_ads201",
            "source": "usaid_ads201.pdf",
            "statement_path": "toc.project_goal",
            "used_for": "toc_claim",
            "citation_confidence": 0.8,
        }
    )
    assert str(row.get("doc_id") or "").startswith("synthetic::tenant_a/usaid_ads201::")
    assert row["chunk_id"] == row["doc_id"]
    assert row["doc_id_synthetic"] is True


def test_append_citations_dedupes_by_normalized_namespace_and_prefers_stronger_metadata():
    state = {
        "citations": [
            {
                "stage": "architect",
                "citation_type": "rag_claim_support",
                "namespace": "Tenant A / USAID ADS201",
                "doc_id": "doc-1",
                "source": "policy.pdf",
                "page": 2,
                "used_for": "toc_claim",
                "statement_path": "toc.project_goal",
                "citation_confidence": 0.2,
                "retrieval_rank": 3,
                "retrieval_confidence": 0.2,
            }
        ]
    }

    append_citations(
        state,
        [
            {
                "stage": "architect",
                "citation_type": "rag_claim_support",
                "namespace": "tenant_a/usaid_ads201",
                "doc_id": "doc-1",
                "source": "policy.pdf",
                "page": 2,
                "used_for": "toc_claim",
                "statement_path": "toc.project_goal",
                "citation_confidence": 0.9,
                "retrieval_rank": 1,
                "retrieval_confidence": 0.85,
            }
        ],
    )

    rows = state.get("citations")
    assert isinstance(rows, list)
    assert len(rows) == 1
    row = rows[0]
    assert row["namespace_normalized"] == "tenant_a/usaid_ads201"
    assert row["retrieval_rank"] == 1
    assert row["retrieval_confidence"] == 0.85
    assert row["citation_confidence"] == 0.9
