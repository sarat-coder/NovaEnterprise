"""VectorStoreService protocol and in-memory adapter (P6-2).

Nothing outside rag/ knows which adapter is active.
The active adapter is selected by VECTOR_STORE in settings and exposed through
get_vector_store() which is called once at startup.
"""

from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable

from rag.chunking import DocumentChunk

# ---------------------------------------------------------------------------
# Protocol (N3 — replaceable stores)
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorStoreService(Protocol):
    """Minimal protocol every vector-store adapter must satisfy."""

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Embed and store a batch of chunks."""
        ...

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Return (chunk, score) pairs, highest score first."""
        ...

    def keyword_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """BM25-style keyword search; return (chunk, score) pairs."""
        ...

    def count(self) -> int:
        """Return the number of stored chunks."""
        ...

    def clear(self) -> None:
        """Remove all stored chunks."""
        ...


# ---------------------------------------------------------------------------
# In-memory adapter (N1 — no external service)
# ---------------------------------------------------------------------------


class MemoryVectorStore:
    """Pure-Python in-memory vector store with cosine similarity and BM25.

    Uses the embedding model from get_embedding_model() to embed chunks at
    add time and queries at search time.  BM25 is computed over stored tokens
    without an index library.
    """

    def __init__(self, embedding_model: Any | None = None) -> None:
        self._chunks: list[DocumentChunk] = []
        self._vectors: list[list[float]] = []
        self._embedding_model = embedding_model or self._default_embeddings()

    # ------------------------------------------------------------------
    # VectorStoreService implementation
    # ------------------------------------------------------------------

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        texts = [c.content for c in chunks]
        vectors = self._embedding_model.embed_documents(texts)
        self._chunks.extend(chunks)
        self._vectors.extend(vectors)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self._chunks:
            return []
        q_vec = self._embedding_model.embed_query(query)
        scored = [
            (chunk, _cosine(q_vec, vec))
            for chunk, vec in zip(self._chunks, self._vectors, strict=False)
            if _matches_filter(chunk, filter_metadata)
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def keyword_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self._chunks:
            return []
        candidates = [c for c in self._chunks if _matches_filter(c, filter_metadata)]
        if not candidates:
            return []
        scored = _bm25(query, candidates)
        return scored[:k]

    def count(self) -> int:
        return len(self._chunks)

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_embeddings() -> Any:
        from app.core.llm import get_embedding_model  # noqa: PLC0415

        return get_embedding_model()


# ---------------------------------------------------------------------------
# Qdrant adapter stub (P6-3 — full impl in qdrant_adapter.py)
# ---------------------------------------------------------------------------


def _make_qdrant_store() -> Any:
    """Instantiate the Qdrant adapter. Import is deferred to avoid hard dependency."""
    from rag.qdrant_adapter import QdrantVectorStore  # noqa: PLC0415

    return QdrantVectorStore()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_instance: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    """Return the singleton vector-store adapter, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = _build_vector_store()
    return _instance


def reset_vector_store() -> None:
    """Reset singleton — used in tests to get a fresh empty store."""
    global _instance
    _instance = None


def _build_vector_store() -> VectorStoreService:
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if settings.vector_store == "qdrant":
        return _make_qdrant_store()  # type: ignore[return-value]
    return MemoryVectorStore()


# ---------------------------------------------------------------------------
# Health check registration
# ---------------------------------------------------------------------------


def register_vector_store_check() -> None:
    """Register vector store readiness check.  Called once during lifespan."""
    from app.core.health import register_check  # noqa: PLC0415

    def _check() -> dict[str, str]:
        try:
            store = get_vector_store()
            n = store.count()
            from app.core.config import get_settings as _gs  # noqa: PLC0415

            detail = f"{_gs().vector_store} ({n} chunks)"
            return {"status": "ok", "detail": detail}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    register_check("vector_store", _check)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _bm25(
    query: str,
    chunks: list[DocumentChunk],
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[DocumentChunk, float]]:
    """Simple BM25 implementation without an index library."""
    import re  # noqa: PLC0415

    def tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return [(c, 0.0) for c in chunks]

    corpus = [tokenize(c.content) for c in chunks]
    avg_dl = sum(len(d) for d in corpus) / max(len(corpus), 1)

    scores: list[tuple[DocumentChunk, float]] = []
    for chunk, doc_tokens in zip(chunks, corpus, strict=False):
        dl = len(doc_tokens)
        tf_map: dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        # Document frequency (approximate across current corpus)
        score = 0.0
        for qt in query_tokens:
            tf = tf_map.get(qt, 0)
            df = sum(1 for d in corpus if qt in d)
            idf = math.log((len(corpus) - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avg_dl)
            score += idf * numerator / max(denominator, 1e-9)
        scores.append((chunk, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def _matches_filter(chunk: DocumentChunk, filter_metadata: dict[str, Any] | None) -> bool:
    if not filter_metadata:
        return True
    return all(chunk.metadata.get(k) == v for k, v in filter_metadata.items())
