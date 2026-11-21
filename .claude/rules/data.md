---
paths:
  - "database/**"
  - "sample_data/**"
---

# Database and sample data conventions (CLAUDE.md §5)

- Sample data is the test fixture for the whole project. Changing counts or ids breaks eval and workflow tests — update the tests and `PLAN_PHASE.md` numbers in the same change.
- Expected counts: 6 teams, 20 employees, 8 services, 10 customers, 12 incidents (three quarters), 8 decisions, 6 projects, 15 tickets, 15 documents.
- `documents/postmortem-inc-2031-payments-api-outage.md` is the SEV1 behind the canonical question.
- `documents/vendor-note-processor-update.md` contains a deliberate prompt-injection attempt. Keep it; never "clean" it.
- Graph relationships needed at minimum: `(Incident)-[:AFFECTED]->(Service)`, `(Incident)-[:IMPACTED]->(Customer)`, `(Service)-[:OWNED_BY]->(Team)`, decision ↔ incident.
- `database/schema.sql`, `rls_policies.sql`, `seed.sql` and `migrations/` must agree with the SQLAlchemy models. A schema change ships with a migration.
- Tables and columns used by SQL retrieval must be on the `validate_sql()` allowlist.
- `data/` and `*.db` are local and git-ignored; never commit them.
