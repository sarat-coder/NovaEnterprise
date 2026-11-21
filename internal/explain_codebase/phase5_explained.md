# Phase 5 — API Contract and Browse API
### Plain-English Explanation for Non-Technical Audiences

---

## What Problem Are We Solving?

Imagine you're building a city. Before the roads and houses go up, everyone — the architects, the
electricians, the plumbers — needs to agree on **a single blueprint** that says exactly where the
doors are, what size the pipes are, and how the electricity flows. If each team invents their own
standard, nothing connects.

In our platform, the **backend** (the brain, powered by Python and FastAPI) and the **frontend**
(the face the user sees, built in Next.js) are two separate teams building two separate halves of
the same house. Phase 5 is when we sat down and drew the blueprint.

---

## The Three Things We Built

### 1. The API Contract (`docs/API_CONTRACT.md`)

Think of this as the **menu at a restaurant**. It lists:

- Every dish available (every URL you can call)
- What ingredients you need to order it (the data you must send)
- Exactly what arrives on your plate (the data you get back)
- What the waiter says if something goes wrong ("404 — that dish doesn't exist")

Before this document existed, the frontend team would guess what the backend returns. Guesses
cause bugs. Now both teams read the same menu.

**Example entry from the contract:**

> `GET /api/v1/incidents` — Returns a list of all incidents.
> Any logged-in user can call this. No login → 401 Unauthorized.

---

### 2. Frontend Assumptions (`docs/FRONTEND_ASSUMPTIONS.md`)

This is the **house rules** document. Beyond the basic menu, it answers questions like:

- "What are the exact names of the steps in the AI workflow?" (So the UI can label them correctly)
- "How often should the browser check for updates?" (Every 2 seconds)
- "If one of the databases is down, does the whole system crash or just slow down?" (It slows down gracefully — called *degraded* mode)

Without this document, the browser and the backend could use different names for the same step and
the progress bar would show gibberish.

---

### 3. Browse API Endpoints — The Filing Cabinet

We built the **reading desk** of the platform: three sets of web endpoints that let any logged-in
user look up real enterprise data.

| What you can browse | Web address | Like asking... |
|---------------------|-------------|----------------|
| Customers | `/api/v1/customers` | "Show me all our clients" |
| A single customer | `/api/v1/customers/3` | "Tell me about client #3" |
| Incidents | `/api/v1/incidents` | "Show me all outages and problems" |
| One incident (with who was hurt and what was decided) | `/api/v1/incidents/1` | "Tell me everything about outage #1" |
| Decisions / ADRs | `/api/v1/decisions` | "Show me all the architectural decisions we made" |
| One decision (linked to the incidents it addressed) | `/api/v1/decisions/2` | "Tell me about decision #2" |

**Key rule:** viewers, analysts, and admins can all *read* this data. Only higher roles can
*change* it. This is the same as a library — everyone can read books, but only librarians shelve them.

---

### 4. Research Schemas — The Answer Form

We also designed the **answer template** that the AI will fill in. Think of it like a standard
form at a hospital — there are specific boxes for the patient's name, symptoms, diagnosis, and
doctor's notes. No matter which doctor fills it out, the form always looks the same.

Our AI research system will fill in this form:

| Field | What it means | Example |
|-------|---------------|---------|
| `question` | What the analyst asked | "Which customers were impacted?" |
| `status` | Is the answer ready yet? | `running` → `completed` |
| `complexity` | How hard was the question? | `complex` |
| `strategies_used` | Which data stores were searched | `["graph", "sql", "vector"]` |
| `evidence` | The raw facts the AI found | A list of database records and document excerpts |
| `answer` | The final cited answer | "Three customers were impacted [1][2][3]." |
| `citations_valid` | Was every [1][2][3] backed by real evidence? | `true` |

The rule that `question` must be **5–2000 characters** was enforced here — too short means no real
question was asked; too long clogs the system.

---

## How It All Connects

```
User types a question in the browser
       │
       ▼
Frontend (Next.js) reads API_CONTRACT.md
to know exactly how to send the question
       │
       ▼
Backend (FastAPI) receives it and validates it
using the ResearchRequest schema (5–2000 chars rule)
       │
       ▼
If the user wants to browse incidents first,
they call GET /api/v1/incidents — data comes back
in the exact shape both sides agreed on
       │
       ▼
When AI answer is ready, it fills in the
ResearchSessionOut template — with citations, evidence, strategy used
       │
       ▼
Frontend renders it, knowing exactly
which field is the answer and which are citations
```

---

## Why Does This Matter?

Before Phase 5, the two halves of our system couldn't be built in parallel — the frontend team
didn't know what the backend would return. After Phase 5:

- **Frontend and backend teams can work simultaneously** — each team uses the contract as a
  shared reference.
- **Bugs from mismatched shapes are eliminated** — Pydantic (our data-shape enforcer) rejects
  anything that doesn't fit the agreed template.
- **Any logged-in user gets data immediately** — the browse endpoints are live and tested.
- **The AI answer structure is locked in** — later phases that build the AI can rely on these
  schemas without redesigning the data shape.

---

## Real-World Analogy

Phase 5 is like the moment in a construction project when the **building inspector approves
the floor plan**. No more "I assumed the door would be there" — everyone now has the same
approved drawing. The floors above (the AI engine, the research screen, the knowledge graph)
can now be safely built on top.
