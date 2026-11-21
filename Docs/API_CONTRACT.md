# API Contract — NovaEnterprise

> **Source of truth for all API endpoints.**
> When an endpoint, field, or status code changes, update this file, `backend/app/schemas/`, and the
> frontend types **in the same commit**.
>
> Base URL: `http://localhost:8001`
> All routes under `/api/v1` require a JWT Bearer token unless stated otherwise.
> Every response carries `X-Request-ID`.
> Errors always use `{ "detail": string }`.

---

## Authentication

### POST /api/v1/auth/login

Obtain a JWT for one of the three demo roles.

**Request**
```json
{ "username": "viewer|analyst|admin", "password": "viewer123|analyst123|admin123" }
```

**Response 200**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "role": "viewer|analyst|admin"
}
```

**Errors**
| Code | Condition |
|------|-----------|
| 401  | Wrong credentials |

---

### GET /api/v1/auth/me

Return the caller's identity from the JWT.

**Response 200**
```json
{ "sub": "analyst", "role": "analyst", "user_id": "" }
```

**Errors**
| Code | Condition |
|------|-----------|
| 401  | No/invalid/expired token |

---

## Health

Health routes are **not** under `/api/v1` and require no token.

### GET /health

```json
{ "status": "ok" }
```

### GET /health/live

```json
{ "status": "ok" }
```

### GET /health/ready

```json
{
  "status": "ok|degraded|error",
  "checks": {
    "app":          { "status": "ok", "detail": "fastapi" },
    "database":     { "status": "ok", "detail": "sqlite|postgresql" },
    "redis":        { "status": "ok", "detail": "fakeredis|real" },
    "vector_store": { "status": "ok", "detail": "memory (N chunks)|qdrant" },
    "graph_store":  { "status": "ok", "detail": "memory|neo4j" },
    "llm":          { "status": "ok", "detail": "fake|openai|anthropic|..." }
  }
}
```

Overall `status` is `"degraded"` when any check is degraded but none errored; `"error"` when any check
errored. Frontend must treat `degraded` as still usable.

---

## Browse API — Customers

All browse endpoints are readable by **any authenticated role** (viewer, analyst, admin).

### GET /api/v1/customers

List all customers.

**Response 200**
```json
[
  {
    "id": 1,
    "name": "Acme Corp",
    "slug": "acme-corp",
    "segment": "enterprise",
    "industry": "Technology",
    "contract_tier": "platinum"
  }
]
```

### GET /api/v1/customers/{customer_id}

Retrieve a single customer by integer id.

**Response 200** — same shape as one element above.

**Errors**
| Code | Condition |
|------|-----------|
| 404  | Customer not found |

---

## Browse API — Incidents

### GET /api/v1/incidents

List all incidents.

**Response 200**
```json
[
  {
    "id": 1,
    "incident_id": "INC-2031",
    "title": "Payments API Outage — Q3",
    "severity": "SEV1",
    "status": "resolved",
    "service_id": 1,
    "service_name": "Payments API",
    "root_cause": "...",
    "summary": "...",
    "started_at": "2024-07-15T02:30:00",
    "resolved_at": "2024-07-15T07:45:00"
  }
]
```

**Query parameters**
| Param      | Type   | Description |
|------------|--------|-------------|
| severity   | string | Filter by severity (`SEV1`, `SEV2`, `SEV3`) |
| service_id | int    | Filter by service |

### GET /api/v1/incidents/{incident_id}

Retrieve a single incident by integer id.

**Response 200** — same shape as one element above, plus:
```json
{
  "...",
  "impacted_customers": [
    { "id": 3, "name": "Beta Industries", "slug": "beta-industries", "segment": "enterprise" }
  ],
  "decisions": [
    { "id": 2, "adr_id": "ADR-0012", "title": "...", "status": "accepted" }
  ]
}
```

**Errors**
| Code | Condition |
|------|-----------|
| 404  | Incident not found |

---

## Browse API — Decisions

### GET /api/v1/decisions

List all decisions (ADRs).

**Response 200**
```json
[
  {
    "id": 1,
    "adr_id": "ADR-0001",
    "title": "Adopt circuit breaker for Payments API",
    "status": "accepted",
    "context": "...",
    "decision_text": "...",
    "consequences": "...",
    "decided_at": "2024-08-01T00:00:00"
  }
]
```

### GET /api/v1/decisions/{decision_id}

Retrieve a single decision by integer id.

**Response 200** — same shape as one element above, plus:
```json
{
  "...",
  "incidents": [
    { "id": 1, "incident_id": "INC-2031", "title": "...", "severity": "SEV1" }
  ]
}
```

**Errors**
| Code | Condition |
|------|-----------|
| 404  | Decision not found |

---

## Research

Research is **analyst and admin only** (viewer → 403).

### POST /api/v1/research

Start a research session. Returns immediately (**202**); the run happens in a background task.

**Request**
```json
{ "question": "Which customers were impacted by the Payments API last quarter?" }
```

Validation: `question` must be 5–2000 characters.

**Response 202**
```json
{
  "session_id": "<uuid>",
  "status": "running"
}
```

**Errors**
| Code | Condition |
|------|-----------|
| 401  | No/invalid token |
| 403  | Viewer role |
| 422  | Validation error (question too short/long) |

---

### GET /api/v1/research/{session_id}

Poll the state of a running or completed session.

**Response 200**
```json
{
  "session_id": "<uuid>",
  "question": "...",
  "status": "running|completed|error",
  "complexity": "simple|moderate|complex|null",
  "strategies_used": ["vector", "sql", "graph"],
  "sub_questions": [
    {
      "id": "sq1",
      "question": "...",
      "strategy": "graph|sql|vector|hybrid",
      "status": "pending|running|completed|error",
      "evidence_ids": ["e1", "e2"]
    }
  ],
  "evidence": [
    {
      "id": "e1",
      "source_type": "document|sql|graph",
      "locator": "<chunk_id|query_id|traversal_id>",
      "content": "...",
      "score": 0.95,
      "metadata": {}
    }
  ],
  "answer": "...",
  "citations_valid": true,
  "evidence_count": 9,
  "citation_count": 4,
  "corrective_rounds": 0,
  "memory_scopes": {
    "organizational": {},
    "conversation": {},
    "session": {},
    "user": {}
  },
  "started_at": "2024-07-15T10:00:00",
  "completed_at": "2024-07-15T10:00:07"
}
```

**Errors**
| Code | Condition |
|------|-----------|
| 401  | No/invalid token |
| 404  | Session not found |

---

### GET /api/v1/research/{session_id}/events

Stream all workflow events for the session (node transitions, queries, timings).

**Response 200**
```json
[
  {
    "id": 1,
    "node": "analyze_query",
    "event_type": "transition",
    "payload": {},
    "duration_ms": 42.1,
    "occurred_at": "2024-07-15T10:00:00.123"
  }
]
```

---

## Documents

### GET /api/v1/documents

List all indexed documents (any authenticated role).

**Response 200**
```json
[
  {
    "id": "<uuid>",
    "filename": "postmortem-inc-2031-payments-api-outage.md",
    "content_type": "text/markdown",
    "size_bytes": 4096,
    "status": "indexed",
    "chunk_count": 8,
    "flagged": false,
    "flag_reason": null,
    "created_at": "2024-07-15T10:00:00"
  }
]
```

### POST /api/v1/documents

Upload a document for ingestion. **Analyst or admin only.**

**Request** — multipart/form-data: `file` field.

Validation:
- Max size: `MAX_UPLOAD_MB` (default 5 MB) → 413
- Allowed extensions: `.md`, `.txt`, `.pdf` → 415

**Response 202**
```json
{ "document_id": "<uuid>", "status": "indexing" }
```

**Errors**
| Code | Condition |
|------|-----------|
| 403  | Viewer role |
| 413  | File too large |
| 415  | Unsupported extension |

### DELETE /api/v1/documents/{document_id}

Request document deletion. **Admin only.** Creates an approval request; the document is deleted
only after a recorded admin approval.

**Response 202**
```json
{ "approval_id": "<uuid>", "status": "pending" }
```

**Errors**
| Code | Condition |
|------|-----------|
| 403  | Non-admin role |
| 404  | Document not found |

---

## Knowledge Graph

### GET /api/v1/graph/nodes

List all graph nodes (any authenticated role).

**Response 200**
```json
[
  { "id": "service:payments-api", "label": "Payments API", "type": "Service", "properties": {} }
]
```

**Query parameters**
| Param | Type   | Description |
|-------|--------|-------------|
| type  | string | Filter by node type (`Service`, `Team`, `Incident`, `Customer`, `Decision`) |

### GET /api/v1/graph/nodes/{node_id}/expand

Expand a node: return its direct neighbours and connecting edges.

**Response 200**
```json
{
  "node": { "id": "...", "label": "...", "type": "...", "properties": {} },
  "edges": [
    { "from": "incident:inc-2031", "to": "service:payments-api", "relation": "AFFECTED" }
  ],
  "neighbours": [
    { "id": "...", "label": "...", "type": "...", "properties": {} }
  ]
}
```

---

## Memory

### GET /api/v1/memory

Return memory scopes for the authenticated user. **Analyst or admin only.**

**Response 200**
```json
{
  "organizational": { "fiscal_quarter_q3_start": "2024-07-01" },
  "conversation": {},
  "session": {},
  "user": {}
}
```

---

## Common response conventions

| Pattern | Detail |
|---------|--------|
| `X-Request-ID` header | Present on every response (echoed when sent, UUID generated otherwise) |
| Error body | `{ "detail": string }` only — no stack traces, no chain-of-thought |
| Datetime format | ISO 8601 (`2024-07-15T10:00:00`) |
| Pagination | Not in v1; all list endpoints return the full set |
| Rate limit exceeded | 429 with `{ "detail": "rate limit exceeded" }` |
