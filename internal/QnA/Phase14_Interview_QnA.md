# Phase 14 — Interview Questions and Answers

## Frontend Architecture

**Q: The research session page polls the backend every 2 seconds. Why not use WebSockets or Server-Sent Events?**

A: Polling was chosen deliberately for three reasons. First, it is simpler to implement and debug — a plain `setInterval` with a standard REST `GET` is easier to reason about than a WebSocket connection lifecycle. Second, the backend already writes state to the database after every node and exposes it through a REST endpoint, so no server-side streaming infrastructure is needed. Third, 2-second latency is acceptable for a research workflow that takes ~7 seconds total. WebSockets would add value if the latency became annoying or if many clients needed to track the same session.

---

**Q: How does the frontend know when to stop polling?**

A: The `ResearchSession` object returned by the API has a `status` field that is either `"running"`, `"completed"`, or `"error"`. The polling loop checks this after every response and clears the interval as soon as the status becomes terminal. The polling interval is stored in a `useRef` so it can be cleared from inside the async poll function without causing stale-closure problems.

---

**Q: Why do you derive SQL queries and Cypher from the evidence list rather than from a separate queries endpoint?**

A: The `Evidence` schema already has a `locator` field that holds the query text (SQL statement or Cypher) and a `source_type` field that distinguishes `"sql"` from `"graph"`. Filtering the existing evidence array by source type and extracting unique locators is cheaper than adding a new endpoint, a new repository query, and a new API schema just to show queries separately. The same information is already in the response — the UI just needs to display it differently.

---

**Q: Why does the documents upload use a custom `fetch` call instead of the shared `request<T>` helper?**

A: The shared helper always sets `Content-Type: application/json`. File upload requires `multipart/form-data` with a browser-generated boundary string, which is set automatically by the browser when you pass a `FormData` body — but only if you do NOT explicitly set `Content-Type`. If you set it, the boundary is missing and the backend rejects the request. So the upload function uses a raw `fetch` with only the `Authorization` header, letting the browser set the content type.

---

**Q: What happens if a viewer navigates directly to `/search`?**

A: The search page is accessible to viewers — they can see the form. But `canStartResearch(role)` returns false for a viewer, so the textarea and submit button are disabled. If a viewer bypasses the UI and sends a POST to `/api/v1/research` directly with their viewer JWT, the backend's `require_role(Role.ANALYST)` guard returns a 403 Forbidden. The UI and the API both enforce the same rule, independently.

---

**Q: Dynamic Tailwind classes like `bg-${color}-500` don't work. How did you handle conditional styling?**

A: Tailwind uses a content-scanner at build time to find which class names appear as literal strings in source files. If a class is built from a template literal like `` bg-${color}-500 ``, the scanner cannot see the full class name and purges it. The fix is to use complete, static class strings. For example, instead of a `color` variable, we define a full CSS class string like `"bg-blue-50 border-blue-200 text-blue-700"` per variant and select the whole string. This is a common gotcha in Tailwind projects.

---

**Q: Why is the JWT stored in `sessionStorage` rather than `localStorage`?**

A: `sessionStorage` is scoped to the browser tab and cleared automatically when the tab is closed. This means the token cannot persist across browser restarts or be accessed by other tabs, which reduces the window of risk if a user leaves a machine unattended. `localStorage` persists until explicitly cleared, which is convenient but means a stolen session token would work indefinitely. The tradeoff is that each new tab requires a new login — acceptable for an enterprise internal tool.

---

## Knowledge Graph

**Q: The graph explorer doesn't have a visual canvas (no D3 or Cytoscape). Was that a conscious decision?**

A: Yes. Adding a canvas library would introduce a large dependency, require layout algorithms (force-directed graphs are non-trivial to tune), and potentially make the page inaccessible to screen readers. The text-based explorer achieves the same functional goal — navigate the graph by clicking — with zero dependencies and full accessibility. The tradeoff is that you cannot see the full graph topology at a glance. For the demo use case (following the trail from a service to its incidents to its customers), the text-based approach is sufficient.

---

**Q: How does the Cypher console prevent destructive queries?**

A: The backend rejects any Cypher that contains write clauses (CREATE, MERGE, SET, DELETE, REMOVE, DROP) before the query reaches the graph database. This check lives in `rag/graph_store.py`'s `execute_cypher_readonly` method. The frontend sends the query to `POST /api/v1/graph/cypher`, which calls that method and returns a 422 Unprocessable Entity if the query fails the read-only check. The UI then displays the error message. The enforcement is on the backend; the frontend just forwards the query and renders the result or error.

---

**Q: Why is the Cypher console hidden from viewers?**

A: Running arbitrary Cypher (even read-only) is a more powerful capability than browsing pre-defined node lists. A carefully crafted Cypher query could scan the entire graph, extract large volumes of data, or reveal relationships that pre-defined traversals intentionally don't expose. Restricting it to analyst+ matches the backend's `require_role(Role.ANALYST)` guard on `POST /api/v1/graph/cypher`.

---

## Documents and Approvals

**Q: Why does document deletion go through an approval workflow instead of happening immediately?**

A: This is requirement F17 from the PRD: "Approval gate on destructive admin actions (document delete)." Documents are retrieved as evidence during research; deleting one could silently change future research results. Having an audit trail of who requested deletion and who approved it is important for compliance and reproducibility. The two-step flow also prevents accidental deletions — an analyst clicking the wrong button doesn't immediately remove data.

---

**Q: What prevents an analyst from requesting deletion of the same document twice?**

A: The UI tracks pending approval requests in a `Map<string, ApprovalRequest>` keyed by `resource_id` (the document ID). Once a deletion request is recorded in this map, the row hides the "Request delete" button and shows "Awaiting admin approval" instead. This is a client-side guard only — a determined user could still send a second DELETE request directly to the API. The backend's approval service would create a second approval request (or could be extended to check for existing pending requests and return a 409 Conflict — a gap worth noting).

---

## Testing

**Q: Why do you test `canStartResearch` and the other role predicates as unit tests rather than integration tests?**

A: They are pure functions — given a role string, they return a boolean with no side effects, no network calls, no DOM. Pure functions are the ideal target for unit tests because they are deterministic and fast. The integration test for role enforcement (a viewer getting 403 on the research endpoint) already exists in `tests/api/test_api.py::test_auth_required_and_rbac` on the backend. Testing the same rule at three levels (pure function, component, API) would be redundant.

---

**Q: Why mock `next/navigation` in the search page tests?**

A: `useRouter()` from `next/navigation` only works inside the Next.js runtime because it needs the router context that Next.js injects. In a Jest + jsdom environment, there is no Next.js runtime, so calling `useRouter()` throws. The mock replaces it with a plain object containing a `push` spy so the test can assert that the page navigates to `/research/<id>` without actually running a router.

---

**Q: What's the difference between `setupFiles` and `setupFilesAfterEnv` in Jest?**

A: `setupFiles` runs before the test framework is installed. `setupFilesAfterEnv` runs after the test framework is installed, which means Jest's global functions (`describe`, `it`, `expect`) are already available. `@testing-library/jest-dom` extends `expect` with matchers like `toBeInTheDocument`, which requires the testing framework to already exist. That is why it goes in `setupFilesAfterEnv` and not `setupFiles`.

---

## TypeScript

**Q: Why extend `lib/types.ts` for graph and document types rather than defining them inline in the page files?**

A: `lib/types.ts` is the single source of truth for all API shapes, mirroring `docs/API_CONTRACT.md`. Putting a type in the page file means it cannot be reused if another page or component needs the same type. It also makes it harder to verify that the frontend type matches the backend Pydantic schema — there is only one place to look. This is the same reason all API calls go through `lib/api-client.ts` rather than being scattered through components.

---

**Q: What is a `Record<string, unknown>` and why is it used for `properties` in `GraphNode`?**

A: `Record<string, unknown>` is TypeScript's way of saying "an object with string keys and values of any type." It is used for `properties` because different node types (Service, Incident, Customer, Team) have different sets of properties — a Service has `name` and `status`, an Incident has `severity` and `root_cause`, and so on. Rather than defining a union of all possible property shapes (which would couple the frontend to every graph node schema), `Record<string, unknown>` accepts any property bag. The UI code then accesses specific keys like `node.properties.name as string` and handles the case where they may be absent.

---

## General

**Q: What is the significance of `params.id` in the research session page, and why is it typed as a plain string in the page component?**

A: In Next.js 15 App Router, dynamic route segments like `[id]` are passed to the page component as `params: { id: string }`. The page uses this to construct the API URLs for polling — `researchApi.get(params.id)` and `researchApi.events(params.id)`. It is typed as `{ id: string }` because URL segments are always strings; it is the caller's responsibility to validate the format (the backend returns 404 if the UUID is malformed or not found).

---

**Q: If the backend is down when the page loads, what does the user see?**

A: The health banner component polls `/health/ready` once on mount. If that call fails (network error or non-OK status), the banner shows a degraded or error state. The individual API calls in each page catch errors and show inline error messages — for example, the knowledge graph page shows a red error box if `GET /graph/nodes` fails. The research session page stops polling and shows an error message if either the session or events endpoint fails. The app never crashes silently.
