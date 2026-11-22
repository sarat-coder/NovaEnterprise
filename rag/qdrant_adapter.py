"""Qdrant vector-store adapter (P6-3).

Requires VECTOR_STORE=qdrant and QDRANT_URL in env.
Fully validated under Docker Compose (Phase 15); offline tests use MemoryVectorStore.
"""

from __future__ import annotations

from typing import Any

from rag.chunking import DocumentChunk


class QdrantVectorStore:
    """Qdrant-backed VectorStoreService adapter.

    Import of qdrant_client is deferred so the app starts without it.
    The collection is created on first add_chunks call if it does not exist.
    """

    COLLECTION = "nova_chunks"
    VECTOR_SIZE = 1536  # matches FakeEmbeddings and OpenAI text-embedding-3-small

    def __init__(self) -> None:
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        if not settings.qdrant_url:
            raise ValueError(
                "QDRANT_URL must be set when VECTOR_STORE=qdrant. "
                "Add it to .env or use VECTOR_STORE=memory for offline work."
            )
        try:
            from qdrant_client import QdrantClient  # noqa: PLC0415
            from qdrant_client.models import Distance, VectorParams  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError("Run: uv add qdrant-client") from exc

        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self._embedding_model = self._get_embeddings()
        self._ensure_collection(VectorParams, Distance)

    def _get_embeddings(self) -> Any:
        from app.core.llm import get_embedding_model  # noqa: PLC0415

        return get_embedding_model()

    def _ensure_collection(self, VectorParams: Any, Distance: Any) -> None:  # noqa: N803
        collections = {c.name for c in self._client.get_collections().collections}
        if self.COLLECTION not in collections:
            self._client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )

    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        from qdrant_client.models import PointStruct  # noqa: PLC0415

        texts = [c.content for c in chunks]
        vectors = self._embedding_model.embed_documents(texts)
        points = [
            PointStruct(
                id=c.chunk_id,
                vector=vec,
                payload={"content": c.content, "doc_id": c.doc_id, **c.metadata},
            )
            for c, vec in zip(chunks, vectors, strict=False)
        ]
        self._client.upsert(collection_name=self.COLLECTION, points=points)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue  # noqa: PLC0415

        q_vec = self._embedding_model.embed_query(query)
        qfilter = None
        if filter_metadata:
            qfilter = Filter(
                must=[
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_metadata.items()
                ]
            )
        hits = self._client.search(
            collection_name=self.COLLECTION,
            query_vector=q_vec,
            limit=k,
            query_filter=qfilter,
        )
        result = []
        for h in hits:
            payload = h.payload or {}
            chunk = DocumentChunk(
                chunk_id=str(h.id),
                doc_id=payload.get("doc_id", ""),
                content=payload.get("content", ""),
                metadata={k: v for k, v in payload.items() if k not in {"content", "doc_id"}},
            )
            result.append((chunk, h.score))
        return result

    def keyword_search(
        self,
        query: str,
        k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        # Qdrant does not support BM25 natively; fall back to scroll + in-process BM25.
        from rag.vector_store import _bm25, _matches_filter  # noqa: PLC0415

        all_chunks = self._scroll_all()
        candidates = [c for c in all_chunks if _matches_filter(c, filter_metadata)]
        return _bm25(query, candidates)[:k]

    def count(self) -> int:
        info = self._client.get_collection(self.COLLECTION)
        return info.points_count or 0

    def clear(self) -> None:
        from qdrant_client.models import Filter  # noqa: PLC0415

        self._client.delete(collection_name=self.COLLECTION, points_selector=Filter(must=[]))

    def _scroll_all(self) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        offset = None
        while True:
            records, next_offset = self._client.scroll(
                collection_name=self.COLLECTION,
                offset=offset,
                limit=100,
                with_payload=True,
            )
            for r in records:
                payload = r.payload or {}
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(r.id),
                        doc_id=payload.get("doc_id", ""),
                        content=payload.get("content", ""),
                        metadata={
                            k: v for k, v in payload.items() if k not in {"content", "doc_id"}
                        },
                    )
                )
            if next_offset is None:
                break
            offset = next_offset
        return chunks
