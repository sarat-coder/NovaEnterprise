# Phase 13 — Interview Q&A: Console Shell

## Frontend Architecture

**Q: Why did you choose Next.js 15 for the frontend?**

A: Next.js 15 with the App Router is the industry standard for React-based enterprise web applications. It gives us both server-side and client-side rendering in the same framework, a file-based routing system that maps directly to our URL structure, and built-in support for TypeScript, Tailwind, and rewrites. The App Router's layout system made it straightforward to implement the authenticated shell — one `layout.tsx` file guards every page inside the `(app)` route group. It also runs `npm run dev` with Hot Module Replacement, which is essential for rapid UI iteration.

---

**Q: Why is the frontend running on port 3001 instead of the same port as the backend?**

A: In a production deployment, the frontend and backend are always separate services — different containers, different scaling rules, different deployment cycles. We mirror that reality in development by running them on different ports from day one. This avoids developing against an artificial "one process" setup that would need to be untangled before deployment. Port 3001 for the Next.js dev server and 8001 for FastAPI is the standard pairing for this stack.

---

**Q: What are Next.js rewrites and why do you use them?**

A: Rewrites are URL aliasing rules configured in `next.config.ts`. When the browser makes a request to `/api/v1/customers`, Next.js intercepts it and forwards it to `http://localhost:8001/api/v1/customers` before the browser ever sends a cross-origin request. The browser only ever sees one origin — `localhost:3001` — which eliminates CORS configuration entirely in development. In production, a real reverse proxy (Nginx or a cloud load balancer) replaces this role and the Next.js rewrites are removed.

---

**Q: Why is the JWT token stored in `sessionStorage` rather than `localStorage` or a cookie?**

A: `sessionStorage` is the right choice here because it is scoped to a single browser tab and is cleared when the tab closes. This means:
1. On a shared computer, closing the browser tab logs the user out automatically — no token leaks to the next person who opens the browser.
2. Tokens cannot accidentally be read by other browser extensions or scripts that target `localStorage`.
3. No server-side cookie management or CSRF protection is needed.

A `httpOnly` cookie set by the server would be more secure for a production system (it cannot be read by JavaScript at all), but sessionStorage is appropriate for this educational platform.

---

**Q: How does the typed API client enforce the API contract?**

A: The file `frontend/lib/types.ts` mirrors every schema defined in `docs/API_CONTRACT.md` as TypeScript interfaces. The API client in `frontend/lib/api-client.ts` returns these typed interfaces from every call. If the backend changes a field name or adds a required field, TypeScript immediately flags every component that uses the old type as a compile error. The type system acts as an automated contract checker — you cannot ship a build that uses a field that no longer exists. This catches mismatches at development time rather than at runtime in production.

---

**Q: What happens when the backend returns a 429 rate-limit response?**

A: The API client records `_rateLimitUntil = Date.now() + 60_000` — a timestamp 60 seconds in the future stored as a module-level variable. Every subsequent call checks this timestamp before making a network request. If we are still inside the backoff window, the client throws an `ApiError(429)` immediately, without even sending a request to the backend. This prevents a "retry storm" where every component on the page simultaneously floods the server after getting a 429. The 60-second window matches the FRONTEND_ASSUMPTIONS.md requirement. The user sees a human-readable message rather than a network error.

---

## Role-Based Access Control

**Q: How is role-based access implemented in the frontend?**

A: There are two layers. First, the UI layer: the `auth.ts` module exposes helper functions like `canStartResearch(role)` and `canUpload(role)`. Components call these to decide what to render — the Search link in the navigation bar is hidden from viewers, and the Search page shows a permission message instead of the input form. Second, the backend layer: even if a viewer somehow submits a research request (bypassing the UI), the backend returns a 403 Forbidden because `require_role("analyst")` is enforced on the FastAPI route. The UI restriction is a convenience; the backend restriction is the security boundary.

---

**Q: What is the purpose of the `(app)` route group in the Next.js directory structure?**

A: Next.js App Router allows parenthesised folder names like `(app)` to create "route groups" — logical groupings that share a layout but do not appear in the URL. All the pages inside `(app)/` — search, customers, incidents, decisions, documents, knowledge-graph, research — share the authenticated layout (nav bar, health banner, auth guard). The `(app)` folder name itself does not appear in the URL: `/app/customers` does not exist — it is just `/customers`. This keeps URLs clean while allowing a single layout file to protect all authenticated pages.

---

**Q: How does the auth guard work?**

A: The `(app)/layout.tsx` runs client-side because it uses `"use client"`. On first render it calls `isLoggedIn()`, which checks whether a JWT exists in sessionStorage. If not, it immediately calls `router.replace("/login")` — the user is redirected before any page content is rendered. The `if (!isLoggedIn()) return null` line ensures no page content flashes on screen during the redirect. This is a standard client-side auth guard pattern in Next.js App Router.

---

## Browse Pages

**Q: Why do the browse pages load data with `useEffect` rather than server-side fetching?**

A: The browse pages use client-side data fetching because the JWT authentication token is stored in `sessionStorage`, which is only available in the browser — not on the Next.js server. Server-side data fetching would not have access to the user's token. For this architecture, client-side fetching with `useEffect` is the correct pattern. In a production system with a cookie-based auth flow, we could use Next.js server components and fetch data on the server, which would be faster and better for SEO.

---

**Q: Why does the incidents list have a severity filter but customers and decisions do not?**

A: The backend's `GET /api/v1/incidents` endpoint supports `?severity=SEV1` as a query parameter (defined in `API_CONTRACT.md`). Customers and decisions do not have equivalent filter parameters defined in the contract. We only expose filters that the backend supports. Adding a client-side filter that sends `?severity=SEV1` to an endpoint that ignores it would work but wastes bandwidth; adding a pure client-side filter that fetches all records and filters locally would be misleading. We build to the contract.

---

**Q: How do the detail pages link back and forth between incidents, customers, and decisions?**

A: The API contract specifies that `GET /api/v1/incidents/{id}` returns an `impacted_customers` array and a `decisions` array nested in the response. `GET /api/v1/decisions/{id}` returns an `incidents` array. These are plain integer IDs and human-readable labels — the backend assembles them from the database join. The frontend renders each one as a Next.js `<Link>` pointing to the appropriate detail page. No additional API calls are needed; the cross-linking data arrives with the original response.

---

## Research Session Page

**Q: The research session page polls every 2 seconds. What stops it from polling forever?**

A: The `useEffect` hook sets up an `setInterval` that calls `researchApi.get()` and `researchApi.events()` every 2000 milliseconds. After every poll it checks the session status. If the status is `"completed"` or `"error"`, it calls `clearInterval` on the stored interval reference and stops polling. The `useEffect` cleanup function also clears the interval if the component unmounts (the user navigates away). This satisfies the FRONTEND_ASSUMPTIONS.md guarantee: "When `status == 'completed'` or `status == 'error'`, the frontend stops polling."

---

**Q: How does the research session page display node labels without hardcoding them in the backend?**

A: The page contains a `NODE_LABELS` constant that maps the 14 node IDs defined in `FRONTEND_ASSUMPTIONS.md` to human-readable display labels:
```
"analyze_query" → "Analysing question"
"synthesize_answer" → "Synthesising answer"
```
This mapping lives in the frontend, not the backend. The backend sends raw node IDs in the event payload; the frontend translates them into display text. This keeps backend concerns (node execution) separate from presentation concerns (what to call a node in the UI).

---

## Infrastructure and Development

**Q: Can the backend tests be run without the frontend installed?**

A: Yes. The backend test suite (`make test`) is a pure Python pytest suite. It tests the FastAPI endpoints, the LangGraph workflow, the RAG components, and the memory system directly — no browser, no npm, no Node.js required. The frontend is a separate concern. This is intentional: the Phase 1 N1 requirement states the system must run with no external services, and the test suite enforces that. The frontend is tested separately with `npm run lint` (Phase 14 adds unit tests with Phase 14-5).

---

**Q: How do you run both servers at the same time?**

A: In two terminal windows:
- Terminal 1: `make backend` → starts FastAPI on :8001
- Terminal 2: `make frontend` → runs `cd frontend && npm run dev` → starts Next.js on :3001

The Makefile separates these into two targets. There is no process manager (like `concurrently` or `foreman`) added in Phase 13 — that is a convenience that Phase 15 may address when Docker Compose is introduced. For development, two terminals is explicit and debuggable.

---

**Q: What would change about this setup in production?**

A: Several things:
1. **Next.js rewrites removed** — a real reverse proxy (Nginx or cloud load balancer) routes `/api/v1/*` to the FastAPI container and `/` to the Next.js container.
2. **`npm run build` + `npm run start`** replace the dev server — the production build pre-renders pages and uses optimised JavaScript bundles.
3. **sessionStorage still appropriate** — but `httpOnly` cookies set by the server would be more secure.
4. **Environment variables** — `NEXT_PUBLIC_API_BASE_URL` points to the production API URL.
5. **FastAPI CORS settings** — `CORS_ORIGINS` in `.env` would include the production frontend domain.

The architecture does not change — only the runtime configuration.

---

## Tailwind and Styling

**Q: Why Tailwind CSS instead of a component library like Material UI or Ant Design?**

A: Tailwind gives us precise control over every style decision without importing a large component library that imposes its own design language. For an enterprise platform that needs consistent branding and information-dense layouts (evidence lists, event timelines, cross-linked records), utility classes compose better than component abstractions. The resulting bundle is smaller (Tailwind purges unused classes in production), and the styles are co-located with the components — there is no separate stylesheet to maintain. For a demo/teaching platform, Tailwind also makes every design decision legible in the JSX without needing to look up a component library's prop API.

---

**Q: What do the colour-coding systems in the browse pages communicate?**

A: Each colour scheme conveys a specific business meaning:
- **Incident severity:** red (SEV1) → orange (SEV2) → yellow (SEV3) — matches the conventional traffic-light scale
- **Incident status:** green (resolved) → blue (investigating) → red (open)
- **Customer tier:** purple (platinum) → gold → grey (silver) — mirrors typical enterprise tier rankings
- **Customer segment:** blue (enterprise) → green (mid-market) → orange (SMB) — consistent categorical colours
- **Decision status:** green (accepted) → blue (proposed) → grey (superseded/deprecated)

Consistent colour semantics reduce cognitive load — the user learns once that red means "needs attention" and that meaning is consistent across all pages.
