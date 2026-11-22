# Phase 13 — Console Shell: Plain-Language Explanation

## What problem are we solving?

By Phase 12 we had built a fully working research engine. You could send it a question through a command line and it would go off, search documents, query a database, traverse a knowledge graph, and return a cited answer. The whole engine was running.

But there was no front door.

A recruiter could not log in and see the platform. An analyst could not type a question into a web page and watch the AI think through the answer step by step. Everything lived inside a server that only a programmer talking to raw HTTP endpoints could reach.

Phase 13 builds the **front door**: a real web application that any person can open in a browser, log in, and start using the platform immediately.

---

## Analogy: opening a restaurant

Imagine Phases 1–12 built a world-class restaurant kitchen. The chefs are trained, the ingredients are stocked, the recipes are perfect. But there is no dining room, no front desk, no menu.

Phase 13 builds the dining room:

- The **login page** is the front desk where you say who you are.
- The **navigation bar** is the menu board — it shows only the items your role allows.
- The **browse pages** are the starters — you can explore every customer, every incident, every decision right away.
- The **search page** is where you place your main order — type a question and the kitchen (the AI engine) prepares your answer.

---

## The four things Phase 13 adds

### 1. App shell and navigation (P13-1)

This is the skeleton of the entire web application. It uses **Next.js 15**, which is the same technology that powers major websites like Vercel, Hulu, and parts of GitHub.

The shell provides:

- **A navigation bar** at the top of every page. It shows "Customers", "Incidents", "Decisions", "Documents", "Knowledge Graph", and "Search". The Search link only appears if you are an analyst or admin — viewers see the data but cannot start research.
- **A health banner** — if any part of the backend is degraded (say, the graph database is unavailable), a subtle amber warning appears at the top of every page so the user knows some results may be partial.
- **Port 3001** — the front end runs on a different port from the backend (8001). This mirrors how real production deployments separate the UI from the API server.

```
Browser on :3001  →  Next.js app  →  API calls to :8001
```

### 2. Typed API client (P13-2)

Every time the browser needs data from the backend, it goes through one central file: `frontend/lib/api-client.ts`.

Think of this as the **universal translator** between the web page and the server. It:

- Knows every endpoint in the system (login, customers, incidents, decisions, research, documents).
- Automatically adds the user's login token to every request so the backend knows who is asking.
- Handles rate limiting: if the server says "slow down" (HTTP 429), the client waits 60 seconds before trying again.
- Returns proper TypeScript types so the UI code always knows exactly what shape of data to expect.

**Why does this matter to a recruiter?** In many projects, API calls are scattered all over the code with no consistency — different people write them differently. Having one typed client means every part of the app speaks the same language. This is a professional engineering practice.

### 3. Login and role-aware layout (P13-3)

The platform has three roles — **viewer**, **analyst**, and **admin** — that were defined in the backend in Phase 3. Phase 13 makes the front end aware of these roles so the UI adapts to who is logged in.

**The login page:**
- Shows three demo account buttons so a recruiter can click one and immediately sign in.
- Calls the backend's login endpoint and stores the returned JWT (a secure digital badge) in the browser session.
- Redirects the user to the Search page once logged in.

**Role-aware behaviour:**
- A `viewer` sees the navigation without the Search link, and the Search page shows a message explaining they need analyst access.
- An `analyst` or `admin` sees the full navigation and can submit research questions.
- Role badges appear in the top-right corner so the user always knows which level they are operating at.

**The auth guard:**
- Every page under the app layout checks whether the user is logged in. If not, they are redirected to the login page immediately. This mirrors how every real enterprise application works.

### 4. Browse pages (P13-4)

Three sets of pages let any authenticated user (even a viewer) explore the company's data:

**Customers page (`/customers`)**
- Shows all 10 companies in a card grid.
- Each card displays the company name, industry, segment (enterprise / mid-market / SMB), and contract tier (platinum / gold / silver) with colour coding.
- Clicking a card opens a detail page with the full record.

**Incidents page (`/incidents`)**
- Lists all 12 incidents in a timeline view.
- A filter dropdown lets the user narrow by severity (SEV1 / SEV2 / SEV3).
- Each incident shows its ID, severity badge, title, and service name.
- The detail page shows root cause, summary, impacted customers (with links), and related decisions (with links). This is the cross-referencing that makes the data useful — one click from an incident takes you to every company that was affected.

**Decisions page (`/decisions`)**
- Lists all 8 architecture decision records (ADRs) — the documented choices the engineering teams made in response to incidents.
- Each decision shows its ID, title, status badge, and a summary of the context.
- The detail page shows the full context, decision, and consequences, plus links to the incidents that prompted each decision.

---

## How the pages connect to the research engine

The browse pages are the "read-only" window into the data. For deeper analysis — "which customers were impacted by the Payments API last quarter?" — the user goes to the Search page.

The Search page submits the question to the backend's research endpoint (`POST /api/v1/research`), which responds instantly with a session ID. The user is then taken to the research session page (`/research/[id]`), which polls the backend every 2 seconds showing:

- Which sub-questions the engine is investigating.
- Which retrieval strategy it is using for each (SQL, graph, vector, hybrid).
- The evidence it has collected.
- The final cited answer once complete.

This design — submit immediately, poll for results — is what allows long-running AI analysis without the browser timing out.

---

## The technology choices

| Choice | What it is | Why we use it |
|--------|-----------|---------------|
| Next.js 15 App Router | React framework for web apps | Industry standard, supports server and client components |
| TypeScript | JavaScript with type safety | Catch mistakes before they reach users |
| Tailwind CSS | Utility CSS framework | Fast consistent styling without writing custom CSS |
| sessionStorage for JWT | Browser's per-tab memory | Token clears when you close the tab — secure by default |
| Rate-limit back-off | Wait 60 s on HTTP 429 | Respects the backend's rate limit without crashing |
| Next.js rewrites | Proxy `/api/v1` to `:8001` | No CORS issues; looks like one server to the browser |

---

## What the analyst sees when they log in

1. Open `http://localhost:3001` → redirected to `/login`
2. Click "analyst / analyst123" → signed in → redirected to `/search`
3. Navigation bar shows: Search · Customers · Incidents · Decisions · Documents · Knowledge Graph
4. Click "Use canonical question" → submits the big multi-part question
5. Redirected to `/research/<id>` → watches sub-questions appear, evidence collect, answer synthesise
6. Navigate to `/incidents` → filters to SEV1 → clicks the Payments API outage → sees impacted customers and decisions linked

The whole journey, from login to cited answer, happens in the browser with no command-line interaction required.

---

## Summary

Phase 13 is the moment the platform becomes a **real product** rather than a collection of server components. It demonstrates:

- Professional frontend engineering (typed API client, role-aware routing, clean separation of concerns)
- Good security practice (JWT in sessionStorage, auth guard on every page, role enforcement at both layers)
- Good UX (health degradation banner, demo accounts, role badges, rate-limit feedback)
- A complete user journey from login to cited AI answer

The backend engine was always powerful. Phase 13 makes it accessible.
