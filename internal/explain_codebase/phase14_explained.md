# Phase 14 — Research and Knowledge Screens: Plain-Language Explanation

## What problem are we solving?

By Phase 13 we had a web application with a login screen and browse pages for customers, incidents, and decisions. But the two most important screens — asking an AI research question and exploring the knowledge graph — were either empty placeholders or only partially finished.

An analyst could log in, look at lists of data, but could not:

- Watch the AI **think through** a multi-part question step by step in the browser
- Explore **how entities are connected** ("which services did the Payments team own?")
- **Upload a new document** through the web UI
- **Request deletion** of a document with a proper approval trail

Phase 14 completes the platform. It builds the four screens that make NovaEnterprise a working research product, not just a skeleton.

---

## Analogy: fitting out the research lab

Phases 1–13 built the building, the library shelves, and the reception desk. Phase 14 furnishes the actual research rooms:

- The **Search room** (already roughed-in) — now has a "Use canonical question" shortcut and proper form validation.
- The **Research session room** — now shows the entire AI thinking process: which sub-questions it asked, which queries it ran (SQL tables, graph traversals with Cypher), what evidence it found, how the answer was assembled, and a full timeline of every step.
- The **Knowledge graph room** — a live browser of the company's entity network: click a service to see which incidents affected it, which customers were impacted, which team owns it.
- The **Documents room** — now lets analysts upload new documents and request deletion with admin approval.

---

## The four screens in detail

### 1. Search page (`/search`) — the starting point

This page already existed as a stub. Phase 14 confirms it is complete and correct:

- A large text box where the analyst types their question (5–2000 characters).
- A **"Use canonical question"** button that pre-fills the big multi-part Payments API question — handy for demos.
- Role enforcement: viewers see the form but it is disabled; a warning explains they need analyst access.
- When the analyst clicks **Research →**, the question is submitted to the backend and they are immediately redirected to the research session page. The AI engine works in the background.

```
Analyst types question → clicks Research → browser moves to /research/<session-id>
```

### 2. Research session page (`/research/[id]`) — watching the AI think

This is the most complex screen. It polls the backend every **2 seconds** and fills in sections as they appear:

**Sub-questions panel**
- When the AI decomposes the question into parts, each part appears with its assigned strategy badge (SQL / graph / vector / hybrid) and a live status (pending → running → completed).
- Example: `sq1 [graph] Which customers were impacted?` and `sq2 [sql] Which incidents occurred last quarter?`

**Queries executed panel**
- Every SQL query the engine ran is displayed in a green code box. The analyst can read the exact database query.
- Every Cypher graph traversal is displayed in a purple code box — for example: `MATCH (i:Incident)-[:IMPACTED]->(c:Customer) WHERE i.service = 'Payments API' RETURN c`.
- This is the "open retrieval process" the platform promised — nothing is hidden.

**Answer panel**
- The final cited answer, with `[1]`, `[2]`, `[3]` markers.
- A verification badge: "citations verified" in green, or "citation issues" in red.
- A verification ratio: how many evidence items were actually cited vs. the total collected.

**Evidence panel**
- Every piece of evidence the AI gathered, numbered to match the citations.
- Colour-coded by type: blue for documents, green for SQL records, purple for graph relationships.
- Each item shows its source type, relevance score, and a preview of the content.

**Memory scopes panel**
- The four memory areas the AI consulted: Organizational (shared facts like the fiscal calendar), Conversation (prior chat context), Session (what was discovered this session), and Analyst (personal notes).
- Shows what facts each scope held that informed the answer.

**Event timeline**
- A chronological list of every step the AI took, with timings in milliseconds.
- Lets an experienced user see exactly where time was spent.

### 3. Knowledge Graph explorer (`/knowledge-graph`) — the company's entity network

This screen lets any user (even a viewer) explore the company's knowledge graph interactively.

**Stats bar**
- At the top: total node count and total edge count. After seeding, this shows approximately 85 nodes and 260 edges.

**Node browser (left panel)**
- A dropdown filter to narrow by entity type: Service, Incident, Customer, Team, Decision, Employee.
- A scrollable list of matching nodes, each showing its label badge, display name, and internal ID.

**Neighbour panel (right panel)**
- Click any node and the right panel shows:
  - The node's full properties (name, segment, severity, etc.)
  - A list of every directly connected node, labelled with the relationship type (`[AFFECTED]`, `[IMPACTED]`, `[OWNED_BY]`, etc.)
  - Clicking a neighbour selects it and loads its own neighbours — navigation by exploration.

**Cypher console (analysts and admins only)**
- A dark-themed code editor pre-filled with an example query.
- Analysts can write their own read-only Cypher queries and run them.
- Results appear as a formatted table.
- Write operations (CREATE, DELETE, etc.) are rejected by the backend.

```
Example exploration:
  Select "Service" filter → click "Payments API" →
  See: OWNED_BY → Payments Platform team, AFFECTED by INC-2031, INC-2045
```

### 4. Documents page (`/documents`) — file management

**List view**
- All indexed documents with their chunk count, file size, creation date, and status badge (indexed / pending / error).

**Upload form (analysts and admins)**
- A file picker accepting `.md`, `.txt`, and `.pdf` files up to 5 MB.
- After upload, shows the number of chunks created and whether the document was flagged (e.g., the hostile vendor note).

**Delete request button (analysts and admins)**
- Each document row has a "Request delete" button.
- Clicking it asks for confirmation, then submits a deletion request to the backend.
- The document is NOT deleted immediately — it creates an approval request.
- An admin must approve via the approvals API before the document is removed.
- The row shows "Deletion requested — awaiting admin approval" to prevent duplicate requests.

---

## What "typing is for safety" means here

Every API call in the frontend goes through the typed API client (`lib/api-client.ts`). Phase 14 extended this client with:
- `graphApi` — 5 methods for browsing nodes, expanding neighbours, and running Cypher
- `documentsApi.upload` — handles multipart form upload with proper auth headers
- `documentsApi.requestDelete` — sends the deletion request

TypeScript types in `lib/types.ts` were extended with `GraphNode`, `GraphEdge`, `GraphNeighbors`, `CypherResult`, `GraphStats`, `DocumentUploadResponse`, and `ApprovalRequest`.

**Why this matters**: because every piece of data the UI renders has a declared type, TypeScript catches shape mismatches at compile time — before they can silently corrupt the display in production.

---

## Unit tests (P14-5)

Phase 14 adds the first frontend unit tests:

| Test file | What it tests |
|-----------|--------------|
| `lib/auth.test.ts` | 12 tests: all role predicates (`canStartResearch`, `canUpload`, `canRunCypher`, `isAdmin`), token storage and retrieval via `sessionStorage` |
| `lib/api-client.test.ts` | `ApiError` construction, `healthApi.ready`, `researchApi.get` — verifies `Authorization` header is sent and `ApiError` is thrown on 404 |
| `app/(app)/search/search.test.tsx` | Search page as viewer (disabled form), as analyst (form enabled, redirect on success, error on failure) |

Tests use **Jest** with **React Testing Library** and **jsdom** so no real browser or server is needed. They run offline with `npm test`.

---

## The complete user journey (Phase 14)

1. Open `http://localhost:3001` → login as `analyst`
2. Click **Search** in the nav → type the canonical question (or click "Use canonical question")
3. Click **Research →** → redirected to `/research/<id>`
4. Watch sub-questions appear, SQL and Cypher queries fill in, evidence collect, and the final cited answer synthesise
5. Click **Knowledge Graph** in the nav → select "Service" filter → click "Payments API" → see its owning team, affected incidents, and impacted customers
6. Click **Documents** → upload a new `.md` document → watch it appear as `indexed` with chunk count
7. Click "Request delete" on a document → confirm → see "awaiting admin approval" message

---

## Summary

Phase 14 is the moment the platform becomes **complete**. All four major screens work. An analyst can go from question to cited answer, from curious browser to Cypher query, from file upload to deletion request — entirely in the browser. The engineering principles demonstrated:

- **Progressive disclosure** — the research page reveals more detail as the AI progresses
- **Role enforcement at every layer** — backend 403 + UI controls + disabled forms
- **Open retrieval** — every SQL query and Cypher traversal is visible to the analyst
- **Safety by design** — deletions require admin approval; write Cypher is blocked; uploads are validated
- **Typed end to end** — TypeScript types flow from backend schemas through the API client to React components
