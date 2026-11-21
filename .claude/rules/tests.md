---
paths:
  - "tests/**"
  - "frontend/**/*.test.ts"
  - "frontend/**/*.test.tsx"
---

# Test conventions

- Every test runs offline: `LLM_PROVIDER=fake`, `VECTOR_STORE=memory`, `GRAPH_STORE=memory`, SQLite, fakeredis. No network, no API key, no Docker.
- Folders: `tests/unit/` (validators, rules, guardrails, providers), `tests/api/` (HTTP + auth/RBAC), `tests/rag/` (retrieval, traversals), `tests/workflow/` (end-to-end graph runs), `tests/evaluation/` (metrics over `datasets/eval_cases.json`), `tests/deployment/` (hygiene).
- One behaviour per test. Name it after what it proves; mention the PRD row (F1–F17, N1–N9) in the docstring.
- Use shared fixtures from `tests/conftest.py`; do not build clients or settings inline. Clear the `get_settings()` cache when a test changes env vars.
- Assert on status codes and response shape for API tests; a `viewer` must get 403 on analyst actions.
- Never weaken an evaluation threshold to make a test pass.
- Run targeted tests with `uv run pytest <path>`; the full suite with `make test` once it exists.
- Frontend tests sit next to the component as `*.test.ts(x)`.
