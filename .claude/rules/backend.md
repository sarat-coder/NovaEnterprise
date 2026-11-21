---
paths:
  - "backend/**"
---

# Backend conventions (CLAUDE.md §4.2, §9, §11)

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2. Dependencies via `uv add`, never `pip install`.
- Layers, one-way imports: `api → services → repositories → models`. `core/` is the bottom layer and never imports `agents/`, `rag/` or `memory/`.
  - `api/`: HTTP shape, auth (`require_role`), validation, status codes. No business logic.
  - `services/`: orchestration (run graph, persist, approvals, seed). No HTTP types.
  - `repositories/`: all SQL via SQLAlchemy. Agents never import them directly.
- Routers under `/api/v1`; health unprefixed (`/health`, `/health/live`, `/health/ready`). Each store registers its own readiness check with a `detail` naming the real backing store.
- Errors: `{ "detail": string }` with the correct status code.
- Long work (research runs) goes in a background task; the request returns 202. Never run the graph inside a request.
- Settings only through `get_settings()` (lru_cached). Every new setting gets a placeholder in `.env.example`.
- Endpoint change → update `docs/API_CONTRACT.md`, `backend/app/schemas/` and the frontend types **in the same change**.
- Middleware order: request-id → rate limit → audit. Every response carries `X-Request-ID`.
- Logs are JSON and include the request id; never log secrets, tokens or chain-of-thought.
