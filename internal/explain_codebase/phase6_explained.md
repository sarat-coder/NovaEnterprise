# Phase 6 — Vector RAG: Plain-English Explanation

> Written for non-technical audiences: recruiters, interviewers, and business stakeholders.

---

## What we built in Phase 6

In Phase 6 we gave the system the ability to **read documents and answer questions from them**.

Before this phase, the platform could manage users, store data in a database, and talk to AI models — but it had no way to actually *search through written documents* like postmortems, policy files, or meeting notes.

Phase 6 adds that capability. It is the first layer of what engineers call **RAG** (Retrieval-Augmented Generation) — a technique where, instead of relying only on what an AI model already "knows," you first search your own documents for the most relevant passages, then hand those passages to the AI as evidence for its answer.

Think of it like this: before answering your question, the AI goes to the library, finds the most relevant pages, and reads them first.

---

## The four things we built

### 1. Document Reader (Parsing)

The system can now **read three types of files**: Markdown (`.md`), plain text (`.txt`), and PDF (`.pdf`).

When a document is loaded, the reader extracts all the text — just like copy-pasting a document into a text editor — and hands it to the chunker.

**Why it matters:** The company's knowledge lives in many file formats. The system must handle all of them.

---

### 2. Document Chunker (Splitting into Searchable Pieces)

A full document is too long to compare directly against a question. So the chunker **splits it into smaller, overlapping pieces** called *chunks* — roughly 512 characters each, with a little overlap at the edges so context is never cut off mid-sentence.

Each chunk gets a **stable ID** (a unique fingerprint) derived from its position in its file, so if the document is re-processed, the same chunks get the same IDs every time. This makes the system predictable and testable.

**Analogy:** Imagine cutting a long newspaper article into sticky notes. Each note contains one idea. When you search for something, you search the sticky notes, not the whole paper.

The 15 sample documents we have produce roughly **70 chunks** — right on target.

---

### 3. Vector Store — The Search Engine (Memory and Qdrant)

Once documents are chunked, we need a way to **find the most relevant chunk for a given question**. That is the vector store's job.

A *vector* is a list of numbers that represents the *meaning* of a piece of text. Similar texts get similar numbers. The system converts every chunk into a vector when it is stored, and converts the question into a vector when searching. It then finds the chunks whose vectors are closest to the question's vector — this is called **semantic search** (search by meaning, not just words).

We built two versions:

- **Memory adapter** — stores everything in RAM. Zero setup, works offline, used in all tests and the demo.
- **Qdrant adapter** — connects to a production-grade vector search engine (Qdrant). Used when real scale is needed.

The system picks which one to use from a single setting (`VECTOR_STORE=memory` or `VECTOR_STORE=qdrant`). **Nothing else in the application knows or cares which one is active** — this is called a *protocol pattern*, and it is key to keeping the system flexible.

A health check endpoint (`/health/ready`) now reports: `vector_store: ok (memory, 70 chunks)`.

---

### 4. Hybrid Retriever — The Smart Searcher

The final piece is the retriever, which is what the AI agent will call when it needs documents to answer a question. It uses **three techniques combined**:

| Technique | What it does | Good at |
|-----------|-------------|---------|
| **Semantic search** | Finds chunks by meaning (vectors) | Paraphrased or vague questions |
| **BM25 keyword search** | Finds chunks containing the exact words | Specific terms, names, incident IDs |
| **RRF (Reciprocal Rank Fusion)** | Merges the two ranked lists into one | Gets the best of both |
| **Rerank** | Re-scores the merged results by relevance | Makes the final order better |

This four-step pipeline is called a **hybrid retriever**. It almost always outperforms either search method alone because real questions are messy — sometimes vague, sometimes very specific.

**Demo proof:** When you ask "Which customers were impacted by the Payments API last quarter?", the postmortem document for incident INC-2031 ranks at the top. That is exactly what we want.

The retriever returns its results in the **Evidence format** — the same shape used by SQL and graph retrieval — so the AI agent can cite any source the same way, with numbered references like `[1]`, `[2]`.

---

## How the pieces connect

```
Your question
     │
     ▼
Hybrid Retriever
     │
     ├── Semantic search (vector similarity)  ──┐
     │                                          ├─► RRF merge ─► Rerank ─► Evidence list
     └── BM25 keyword search                   ──┘
              │
              ▼
        Memory Vector Store  (or Qdrant in production)
              │
              ├── Chunk 1: "On 18 July 2026, all payment operations..."
              ├── Chunk 2: "Root cause: payment processor deprecated /v3..."
              └── ...70 chunks from 15 documents
```

---

## What stays the same no matter what

- The store can be swapped (memory ↔ Qdrant) without changing any other code.
- Every chunk gets the same stable ID on every run — the system is reproducible.
- All 162 tests pass offline — no internet, no API key, no cloud service needed.
- Lint is clean (`ruff check` and `ruff format`).

---

## In one sentence

Phase 6 gives the platform a **smart document search engine** that reads your files, splits them into searchable pieces, finds the most relevant ones for any question (by meaning *and* by keywords), and hands them to the AI as evidence to cite.
