# grantflow/tests/test_vector_store.py

from grantflow.memory_bank.vector_store import VectorStore, vector_store


def test_vector_store_upsert_query():
    """Проверяет basic upsert и query."""
    namespace = "test_namespace"

    # Upsert
    vector_store.upsert(namespace=namespace, documents=["Test document 1", "Test document 2"], ids=["test_1", "test_2"])

    # Query
    results = vector_store.query(namespace, "Test document", top_k=2)
    assert len(results) >= 1
    assert "document" in results[0]


def test_vector_store_stats():
    """Проверяет статистику коллекции."""
    stats = vector_store.get_stats("test_namespace")
    assert "namespace" in stats
    assert "namespace_normalized" in stats
    assert "document_count" in stats
    assert stats["document_count"] >= 2


def test_collection_name_normalizes_namespace_tokens():
    store = VectorStore()
    store.prefix = "grantflow"
    collection = store._collection_name(" Tenant A/USAID ADS 201 :: Phase#1 ")
    assert collection == "grantflow_tenant_a_usaid_ads_201_phase_1"


def test_normalize_namespace_falls_back_to_default():
    assert VectorStore.normalize_namespace("   ") == "default"


def test_namespace_trace_returns_requested_normalized_and_collection():
    store = VectorStore()
    store.prefix = "grantflow"
    trace = store.namespace_trace(" Tenant A/USAID ADS 201 :: Phase#1 ")
    assert trace["namespace"] == "Tenant A/USAID ADS 201 :: Phase#1"
    assert trace["namespace_normalized"] == "tenant_a_usaid_ads_201_phase_1"
    assert trace["collection"] == "grantflow_tenant_a_usaid_ads_201_phase_1"


def test_normalize_namespace_non_ascii_is_stable_and_not_default():
    normalized = VectorStore.normalize_namespace("ТестовыйНеймспейс")
    assert normalized.startswith("ns_")
    assert len(normalized) == 15
    assert normalized != "default"
    assert normalized == VectorStore.normalize_namespace("ТестовыйНеймспейс")


def test_normalize_namespace_truncates_very_long_tokens_deterministically():
    raw = "tenant-" + ("usaid-ads-201-" * 20)
    normalized = VectorStore.normalize_namespace(raw)
    assert len(normalized) <= VectorStore.MAX_NAMESPACE_LENGTH
    assert normalized == VectorStore.normalize_namespace(raw)
    assert normalized.rsplit("_", 1)[-1]
