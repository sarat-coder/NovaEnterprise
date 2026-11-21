---
paths:
  - "frontend/**"
---

# Frontend conventions (CLAUDE.md §10, §11)

- Next.js 15 App Router, TypeScript (strict), Tailwind, port **3001**.
- Reach the backend only through the typed API client in `frontend/lib/`, which mirrors `docs/API_CONTRACT.md`. No ad-hoc `fetch` in components.
- Never hold the Supabase service-role key or any secret; only public env vars (`NEXT_PUBLIC_*`).
- Role-aware UI: viewers never see start-research, upload or Cypher controls. The backend still enforces it (403).
- `/research/[id]` polls every 2 s and stops when the status is terminal. It shows analysis, sub-questions with strategy, SQL and Cypher that ran, evidence, verification ratio, cited answer, memory scopes and the event timeline.
- Node ids rendered must match `docs/FRONTEND_ASSUMPTIONS.md`.
- Show only what the API returns: decisions, queries, evidence, timings — no invented reasoning.
- `npm run lint` must be clean before a PR; tests sit next to components as `*.test.ts(x)`.
