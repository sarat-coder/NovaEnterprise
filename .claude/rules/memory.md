---
paths:
  - "memory/**"
---

# Memory conventions (CLAUDE.md §6.4)

- Four separated memory scopes, surfaced per session by `memory/memory_service.py` (F15). One module per scope.
- Scope names are an open question (MEMORY.md Q2) — confirm them before adding a scope module.
- Organizational facts come from `sample_data/organizational_memory.json` (e.g. the fiscal calendar that defines "last quarter").
- Conversation memory lives in Redis (fakeredis when `REDIS_URL` is empty).
- Memory is never mixed with retrieval and never cited as evidence.
- Analysts read and manage only their own memory; admins do not silently read it either.
- Scrub secrets before anything is written to memory.
