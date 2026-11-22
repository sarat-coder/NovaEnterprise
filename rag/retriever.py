"""Hybrid retriever: semantic + BM25 + RRF + rerank (P6-4, F6).

Returns Evidence(source_type="document") — the same shape every other retriever uses.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import Evidence
from rag.chunking import DocumentChunk
from rag.vector_store import VectorStoreService, get_vector_store

# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[Any, float]]],
    k: int = 60,
) -> list[tuple[Any, float]]:
    """Merge multiple ranked lists using RRF.

    k=60 is the standard RRF constant recommended by the original paper.
    Items are identified by their chunk_id.
    """
    scores: dict[str, float] = {}
    items: dict[str, Any] = {}

    for ranked in ranked_lists:
        for rank, (item, _original_score) in enumerate(ranked, start=1):
            key = item.chunk_id
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items[key] = item

    merged = [(items[key], scores[key]) for key in scores]
    merged.sort(key=lambda x: x[1], reverse=True)
    return merged


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


def rerank(
    query: str,
    candidates: list[tuple[DocumentChunk, float]],
    top_k: int = 5,
) -> list[tuple[DocumentChunk, float]]:
    """Rerank candidates by relevance to the query.

    For the offline/fake path: simple term-overlap score so tests are
    deterministic.  With a real cross-encoder it would call the model.
    """
    q_tokens = set(query.lower().split())
    rescored: list[tuple[DocumentChunk, float]] = []
    for chunk, base_score in candidates:
        c_tokens = set(chunk.content.lower().split())
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
        # Blend base RRF score with term overlap for the offline path.
        final_score = 0.7 * base_score + 0.3 * overlap
        rescored.append((chunk, final_score))
    rescored.sort(key=lambda x: x[1], reverse=True)
    return rescored[:top_k]


# ---------------------------------------------------------------------------
# Hybrid retriever
# ---------------------------------------------------------------------------


def hybrid_search(
    query: str,
    k: int = 5,
    store: VectorStoreService | None = None,
    filter_metadata: dict[str, Any] | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Semantic ∪ BM25 → RRF → rerank.

    Returns up to k (chunk, score) pairs scored on [0, 1].
    """
    _store = store or get_vector_store()

    semantic_hits = _store.similarity_search(query, k=k * 2, filter_metadata=filter_metadata)
    keyword_hits = _store.keyword_search(query, k=k * 2, filter_metadata=filter_metadata)

    merged = reciprocal_rank_fusion([semantic_hits, keyword_hits])
    return rerank(query, merged, top_k=k)


def retrieve(
    query: str,
    k: int = 5,
    store: VectorStoreService | None = None,
    filter_metadata: dict[str, Any] | None = None,
) -> list[Evidence]:
    """Public entry point: returns Evidence list (source_type='document').

    Each Evidence item gets a stable ID derived from the chunk_id so
    citation references remain consistent across repeated calls.
    """
    hits = hybrid_search(query, k=k, store=store, filter_metadata=filter_metadata)
    evidence: list[Evidence] = []
    for chunk, score in hits:
        evidence.append(
            Evidence(
                id=_evidence_id(chunk.chunk_id),
                source_type="document",
                locator=chunk.chunk_id,
                content=chunk.content,
                score=min(1.0, max(0.0, score)),
                metadata={**chunk.metadata, "doc_id": chunk.doc_id},
            )
        )
    return evidence


def _evidence_id(chunk_id: str) -> str:
    """Stable evidence id derived from chunk_id."""
    return f"ev-{chunk_id[:8]}"
