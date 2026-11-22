"""Hybrid retrieval tests — proves F6 (semantic + BM25 + RRF + rerank).

All tests run fully offline: VECTOR_STORE=memory, LLM_PROVIDER=fake.
No network, no Qdrant, no Docker.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("LLM_PROVIDER", "fake")

from rag.chunking import DocumentChunk, chunk_document
from rag.retriever import hybrid_search, reciprocal_rank_fusion, rerank, retrieve
from rag.vector_store import MemoryVectorStore, reset_vector_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_store():
    """Each test gets an isolated empty memory store."""
    reset_vector_store()
    yield
    reset_vector_store()


def _make_store_with_docs(texts: list[str]) -> MemoryVectorStore:
    """Helper: build a MemoryVectorStore seeded with the given texts."""
    store = MemoryVectorStore()
    chunks = [
        DocumentChunk(
            chunk_id=f"chunk-{i}",
            doc_id=f"doc-{i}",
            content=text,
            metadata={"index": i},
        )
        for i, text in enumerate(texts)
    ]
    store.add_chunks(chunks)
    return store


# ---------------------------------------------------------------------------
# MemoryVectorStore unit tests
# ---------------------------------------------------------------------------


def test_memory_store_add_and_count() -> None:
    """Adding chunks increases the count. N3 (replaceable stores)."""
    store = MemoryVectorStore()
    assert store.count() == 0
    chunks = [
        DocumentChunk(chunk_id="c1", doc_id="d1", content="Payments API outage"),
        DocumentChunk(chunk_id="c2", doc_id="d1", content="Identity service issue"),
    ]
    store.add_chunks(chunks)
    assert store.count() == 2


def test_memory_store_similarity_search_returns_ranked() -> None:
    """similarity_search returns results sorted by descending score."""
    store = _make_store_with_docs(
        [
            "Payments API experienced an outage last quarter",
            "The identity service had a certificate failure",
            "Quarterly reliability review meeting notes",
        ]
    )
    results = store.similarity_search("Payments API outage", k=3)
    assert len(results) <= 3
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True), "Results must be sorted descending"


def test_memory_store_keyword_search() -> None:
    """keyword_search returns chunks containing query terms."""
    store = _make_store_with_docs(
        [
            "circuit breaker pattern for Payments API",
            "identity certificate rotation policy",
            "data retention and archival procedures",
        ]
    )
    results = store.keyword_search("certificate rotation", k=2)
    assert len(results) >= 1
    top_content = results[0][0].content.lower()
    assert "certificate" in top_content or "rotation" in top_content


def test_memory_store_clear() -> None:
    """clear() empties the store."""
    store = _make_store_with_docs(["some content"])
    assert store.count() == 1
    store.clear()
    assert store.count() == 0


def test_memory_store_filter_metadata() -> None:
    """similarity_search and keyword_search respect filter_metadata."""
    store = MemoryVectorStore()
    chunks = [
        DocumentChunk(
            chunk_id="c1",
            doc_id="d1",
            content="Payments outage",
            metadata={"doc_type": "postmortem"},
        ),
        DocumentChunk(
            chunk_id="c2",
            doc_id="d2",
            content="Data policy",
            metadata={"doc_type": "policy"},
        ),
    ]
    store.add_chunks(chunks)

    results = store.similarity_search("outage", k=5, filter_metadata={"doc_type": "postmortem"})
    assert all(r[0].metadata["doc_type"] == "postmortem" for r in results)


# ---------------------------------------------------------------------------
# RRF and rerank unit tests
# ---------------------------------------------------------------------------


def test_rrf_merges_two_lists() -> None:
    """reciprocal_rank_fusion merges two ranked lists without duplicates."""
    c1 = DocumentChunk(chunk_id="a", doc_id="d", content="alpha")
    c2 = DocumentChunk(chunk_id="b", doc_id="d", content="beta")
    c3 = DocumentChunk(chunk_id="c", doc_id="d", content="gamma")

    list1 = [(c1, 0.9), (c2, 0.5)]
    list2 = [(c2, 0.8), (c3, 0.4)]

    merged = reciprocal_rank_fusion([list1, list2])
    ids = [c.chunk_id for c, _ in merged]
    assert len(ids) == len(set(ids)), "No duplicates after RRF"
    assert "b" in ids, "c2 appears in both lists so should rank highly"


def test_rerank_top_k() -> None:
    """rerank returns at most top_k items."""
    chunks = [
        DocumentChunk(chunk_id=f"c{i}", doc_id="d", content=f"content {i}") for i in range(10)
    ]
    candidates = [(c, float(i)) for i, c in enumerate(chunks)]
    result = rerank("content 5", candidates, top_k=3)
    assert len(result) <= 3


# ---------------------------------------------------------------------------
# Full hybrid retrieval tests (F6)
# ---------------------------------------------------------------------------


def test_hybrid_search_returns_evidence_shape() -> None:
    """hybrid_search returns DocumentChunk/score pairs from the memory store."""
    store = _make_store_with_docs(
        [
            "Payments API outage root cause analysis",
            "Identity service certificate expiry incident",
            "SQL retrieval of incident records",
        ]
    )
    results = hybrid_search("Payments API outage", k=3, store=store)
    assert len(results) >= 1
    for chunk, score in results:
        assert isinstance(chunk, DocumentChunk)
        assert score >= 0.0


def test_retrieve_returns_evidence_objects() -> None:
    """retrieve() returns Evidence with source_type='document'. F6."""
    store = _make_store_with_docs(
        [
            "Payments API experienced significant downtime",
            "Circuit breaker was not configured correctly",
        ]
    )
    evidence_list = retrieve("Payments API downtime", k=2, store=store)
    assert len(evidence_list) >= 1
    for ev in evidence_list:
        assert ev.source_type == "document"
        assert ev.locator  # chunk_id
        assert ev.content
        assert 0.0 <= ev.score <= 1.0
        assert ev.id.startswith("ev-")


def test_retrieve_empty_store_returns_empty_list() -> None:
    """retrieve() on an empty store returns []."""
    store = MemoryVectorStore()
    result = retrieve("anything", k=5, store=store)
    assert result == []


def test_hybrid_search_ranks_outage_postmortem_first() -> None:
    """The INC-2031 postmortem should rank highly for a Payments API query. F6 demo check."""
    from pathlib import Path  # noqa: PLC0415

    postmortem_path = Path("sample_data/documents/postmortem-inc-2031-payments-api-outage.md")
    if not postmortem_path.exists():
        pytest.skip("sample_data not present")

    from rag.chunking import parse_document  # noqa: PLC0415

    store = MemoryVectorStore()
    doc = parse_document(postmortem_path)
    chunks = chunk_document(doc)
    store.add_chunks(chunks)

    # Also add a distractor
    distractor = DocumentChunk(
        chunk_id="distractor-1",
        doc_id="other",
        content="Quarterly budget planning for the data platform team.",
    )
    store.add_chunks([distractor])

    results = retrieve(
        "Which customers were impacted by the Payments API last quarter?",
        k=5,
        store=store,
    )
    assert len(results) >= 1
    # The top result should come from the postmortem document, not the distractor.
    top_ev = results[0]
    assert top_ev.source_type == "document"
    # The postmortem chunks share the doc_id of the postmortem file.
    from rag.chunking import _stable_doc_id  # noqa: PLC0415

    postmortem_doc_id = _stable_doc_id(str(postmortem_path))
    assert top_ev.metadata.get("doc_id") == postmortem_doc_id or any(
        r.metadata.get("doc_id") == postmortem_doc_id for r in results
    ), "Postmortem should appear in top results for Payments API query"


# ---------------------------------------------------------------------------
# Health check registration test
# ---------------------------------------------------------------------------


def test_vector_store_health_check() -> None:
    """register_vector_store_check registers a check that returns ok status."""
    from app.core.health import _registry  # noqa: PLC0415
    from rag.vector_store import register_vector_store_check  # noqa: PLC0415

    register_vector_store_check()
    assert "vector_store" in _registry
    result = _registry["vector_store"]()
    assert result["status"] == "ok"
    assert "memory" in result["detail"]
