# Phase 6 — Interview Q&A: Vector RAG

> All questions and answers derive from the code built in Phase 6.
> Covers both technical and system-design angles for a range of interview levels.

---

## Conceptual / Introductory

**Q1: What is RAG and why is it useful?**

RAG stands for Retrieval-Augmented Generation. The idea is to retrieve relevant documents *before* asking an AI model to answer. Instead of relying on what the model memorised during training (which may be outdated or wrong), you give it fresh evidence from your own data. The result is answers that are grounded, cited, and verifiable.

---

**Q2: What is a vector and why are they used for search?**

A vector is a list of numbers that represents the *meaning* of a piece of text. Similar texts get numerically similar vectors. If you embed both a question and a document chunk into the same vector space, you can measure how close they are (using cosine similarity). This is called *semantic search* — it finds relevant content even when the exact words differ.

---

**Q3: Why split documents into chunks instead of embedding the whole document?**

For two reasons. First, embedding models have a maximum input length (typically 512–8192 tokens). Second, a dense embedding of a 50-page document averages out all the meaning and loses specificity. Smaller, focused chunks produce more precise embeddings and therefore more precise search results.

---

**Q4: What is BM25 and how is it different from semantic search?**

BM25 is a classic keyword-based ranking algorithm. It scores documents by how often the query terms appear, weighted by how rare those terms are across the whole collection (inverse document frequency). It is deterministic, needs no embedding model, and is excellent at finding chunks containing exact names, IDs, or technical terms. Semantic search is better at understanding paraphrased questions. Combining both (hybrid search) is better than either alone.

---

## Design Decisions

**Q5: Why define a `VectorStoreService` protocol instead of using the vector store directly?**

The protocol pattern (also called Dependency Inversion) decouples the application from the specific store. The agent code, the retriever, and the tests all call the five methods on the protocol — `add_chunks`, `similarity_search`, `keyword_search`, `count`, `clear` — and never care whether the backing store is in-memory or Qdrant. Swapping stores is a one-line config change. This is N3 in the requirements: "replaceable stores."

---

**Q6: Why use a memory adapter as the default instead of always requiring Qdrant?**

The design rule is "offline first" (N1, N4). Every test, the demo, and development must work without Docker, without an API key, and without a network connection. The in-memory adapter runs in the same Python process with no external dependencies. Qdrant is introduced as a production option, validated only under Docker Compose in Phase 15.

---

**Q7: Why are chunk IDs stable (derived from sha256)?**

If you re-run ingestion, you want the same chunk to get the same ID. This matters because Evidence items cite chunks by their `locator` (which is the chunk ID). If IDs changed on each run, old citations would break. Stable IDs make the system idempotent and make tests reproducible.

---

**Q8: Why RRF (Reciprocal Rank Fusion) rather than a weighted average of scores?**

Scores from different systems are not on the same scale. BM25 scores can be in the tens; cosine similarity is 0–1. A weighted average of raw scores would be dominated by the system with higher numbers. RRF sidesteps this by using only the *rank* (position in the list), not the score. The formula `1 / (k + rank)` (k=60) is parameter-free and consistently performs well across domains.

---

**Q9: Why is the return type `Evidence` instead of a raw list of chunks?**

The `Evidence` schema is shared by all three retrieval paths — vector, SQL, and graph. That common type is what makes it possible to have *one numbered citation list* in the final answer (requirement F11). If each retriever returned its own type, the synthesis step would need to handle three different shapes.

---

## Implementation Details

**Q10: How does the PDF parser handle a corrupt or truncated PDF?**

The `_parse_pdf` function wraps `PdfReader` in a `try/except`. If pypdf raises any exception (including `PdfStreamError` for truncated files), the function returns a `ParsedDocument` with empty content and a `parse_error` key in its metadata. The pipeline can then log the error and skip that document rather than crashing.

---

**Q11: How does the chunker handle overlap?**

After appending the current chunk to the list, it carries forward the last `chunk_overlap` characters of that chunk as a prefix for the next chunk. This means adjacent chunks share a small window of text, so a sentence that happens to straddle a boundary is not lost.

---

**Q12: What happens when the query contains no keywords that appear in any document?**

BM25 returns a score of 0 for all documents. Semantic search still returns results (cosine similarity is computed regardless of exact term matches). RRF will then use only the semantic ranking. The hybrid retriever degrades gracefully — it always returns *some* results as long as the store is non-empty.

---

**Q13: How does the health check know how many chunks are stored?**

The health check calls `store.count()`, which is one of the five protocol methods. The `MemoryVectorStore` implements it as `len(self._chunks)`. The result appears in the `/health/ready` response as `"detail": "memory (70 chunks)"`.

---

**Q14: How would you add a cross-encoder reranker for production?**

Replace the `rerank()` function in `retriever.py`. The current implementation uses a cheap term-overlap heuristic. A production version would call a cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) that jointly encodes the query and each candidate chunk. The function signature — `rerank(query, candidates, top_k) → list[(chunk, score)]` — stays the same, so the rest of the pipeline is unaffected.

---

## Testing

**Q15: How do you test a retriever offline when you have no real embeddings?**

The `FakeEmbeddings` class (from Phase 4) produces deterministic unit-normalised vectors derived from the MD5 hash of the text. Different texts always get different vectors; the same text always gets the same vector. This is enough for tests to verify that retrieval returns chunks, that scores are in [0, 1], and that the postmortem document appears in results for a Payments API query — without any API key or network call.

---

**Q16: What does `test_hybrid_search_ranks_outage_postmortem_first` prove?**

It is a demo-equivalent test (the F6 "demo checkpoint" in `PLAN_PHASE.md`). It loads only the INC-2031 postmortem plus one unrelated distractor chunk, then queries for "Which customers were impacted by the Payments API last quarter?" and asserts that the postmortem's doc_id appears in the top results. If the retrieval pipeline were broken — wrong embeddings, wrong RRF logic, wrong rerank — this test would fail.

---

**Q17: Why does the test file set `os.environ` before importing from `rag/`?**

The `rag/vector_store.py` module reads `get_settings()` to decide which adapter to build. `get_settings()` is lru_cached. Setting env vars before the first import ensures the cache is populated with the right values. If we set them after import, the cached settings would already be fixed and the override would be ignored.

---

## System Design

**Q18: How would you scale the vector store to millions of documents?**

Switch `VECTOR_STORE=qdrant` and point `QDRANT_URL` at a Qdrant cluster. Qdrant supports horizontal sharding, payload indexing, and filtered search at scale. The application code does not change — only the env var. This is exactly why the protocol pattern was chosen.

---

**Q19: What would you change if the target chunk size needed to be much larger (e.g., 2048 characters)?**

Change `DEFAULT_CHUNK_SIZE` in `chunking.py`. The chunking algorithm is parameterised; both `chunk_size` and `chunk_overlap` are arguments to `chunk_document()`. The only side effect is that the total chunk count would drop (fewer, longer chunks), which might reduce retrieval precision for specific questions.

---

**Q20: How does Phase 6 fit into the overall research workflow?**

Phase 6 builds the retrieval layer that the AI agents (Phase 11+) will call. When the research agent receives a question like "What decisions were taken after the Payments API outage?", the routing node (Phase 11) will decide to use the hybrid retriever for the parts that need document evidence. `retrieve()` will return a list of `Evidence` items. Those items become the grounding for the answer and the source of the `[n]` citation markers (F11).
