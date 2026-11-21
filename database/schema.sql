-- NovaEnterprise — Postgres DDL
-- Apply with: psql $DATABASE_URL -f database/schema.sql
-- For SQLite the application uses SQLAlchemy create_all() at startup.
-- This file is the authoritative Postgres schema; keep it in sync with app/models/.

-- -------------------------------------------------------------------------
-- Domain tables
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teams (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(120) NOT NULL UNIQUE,
    slug        VARCHAR(80)  NOT NULL UNIQUE,
    description TEXT,
    lead_email  VARCHAR(200),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS employees (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    email      VARCHAR(200) NOT NULL UNIQUE,
    title      VARCHAR(200),
    team_id    INTEGER REFERENCES teams(id),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS services (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL UNIQUE,
    slug          VARCHAR(80)  NOT NULL UNIQUE,
    description   TEXT,
    owner_team_id INTEGER REFERENCES teams(id),
    tier          VARCHAR(20)  NOT NULL DEFAULT 'tier-2',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customers (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    slug          VARCHAR(80)  NOT NULL UNIQUE,
    segment       VARCHAR(40)  NOT NULL,     -- enterprise / mid-market / smb
    industry      VARCHAR(100),
    contract_tier VARCHAR(40),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
    id          SERIAL PRIMARY KEY,
    incident_id VARCHAR(40)  NOT NULL UNIQUE,
    title       VARCHAR(300) NOT NULL,
    severity    VARCHAR(10)  NOT NULL,       -- SEV1 / SEV2 / SEV3
    status      VARCHAR(20)  NOT NULL DEFAULT 'resolved',
    service_id  INTEGER REFERENCES services(id),
    root_cause  TEXT,
    summary     TEXT,
    started_at  TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incident_customers (
    incident_id        INTEGER NOT NULL REFERENCES incidents(id),
    customer_id        INTEGER NOT NULL REFERENCES customers(id),
    impact_description TEXT,
    PRIMARY KEY (incident_id, customer_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id            SERIAL PRIMARY KEY,
    adr_id        VARCHAR(40)  NOT NULL UNIQUE,
    title         VARCHAR(300) NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'accepted',
    context       TEXT,
    decision_text TEXT,
    consequences  TEXT,
    decided_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incident_decisions (
    incident_id INTEGER NOT NULL REFERENCES incidents(id),
    decision_id INTEGER NOT NULL REFERENCES decisions(id),
    PRIMARY KEY (incident_id, decision_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(80)  NOT NULL UNIQUE,
    description TEXT,
    status      VARCHAR(30)  NOT NULL DEFAULT 'active',
    team_id     INTEGER REFERENCES teams(id),
    start_date  TIMESTAMPTZ,
    end_date    TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickets (
    id           SERIAL PRIMARY KEY,
    ticket_id    VARCHAR(40)  NOT NULL UNIQUE,
    title        VARCHAR(300) NOT NULL,
    description  TEXT,
    status       VARCHAR(30)  NOT NULL DEFAULT 'open',
    priority     VARCHAR(20)  NOT NULL DEFAULT 'medium',
    project_id   INTEGER REFERENCES projects(id),
    assignee_id  INTEGER REFERENCES employees(id),
    story_points NUMERIC(5,1),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    closed_at    TIMESTAMPTZ
);

-- -------------------------------------------------------------------------
-- Research / workflow tables
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS research_sessions (
    id              VARCHAR(36)  PRIMARY KEY,
    question        TEXT         NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'running',
    user_id         VARCHAR(200),
    complexity      VARCHAR(20),
    strategies_used TEXT,         -- JSON array
    answer          TEXT,
    evidence_count  INTEGER      NOT NULL DEFAULT 0,
    citation_count  INTEGER      NOT NULL DEFAULT 0,
    corrective_rounds INTEGER    NOT NULL DEFAULT 0,
    error           TEXT,
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(36)  NOT NULL,
    node        VARCHAR(80)  NOT NULL,
    event_type  VARCHAR(40)  NOT NULL DEFAULT 'transition',
    payload     TEXT,                -- JSON
    duration_ms NUMERIC(12,3),
    occurred_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_workflow_events_session ON workflow_events(session_id);

-- -------------------------------------------------------------------------
-- Document management tables
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    id           VARCHAR(36)  PRIMARY KEY,
    filename     VARCHAR(300) NOT NULL,
    source_path  TEXT,
    content_type VARCHAR(80)  NOT NULL DEFAULT 'text/markdown',
    size_bytes   INTEGER      NOT NULL DEFAULT 0,
    status       VARCHAR(30)  NOT NULL DEFAULT 'indexed',
    chunk_count  INTEGER      NOT NULL DEFAULT 0,
    uploaded_by  VARCHAR(200),
    flagged      BOOLEAN      NOT NULL DEFAULT FALSE,
    flag_reason  TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id            VARCHAR(36) PRIMARY KEY,
    document_id   VARCHAR(36) NOT NULL,
    chunk_index   INTEGER     NOT NULL DEFAULT 0,
    content       TEXT        NOT NULL,
    metadata_json TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_document_chunks_document ON document_chunks(document_id);

-- -------------------------------------------------------------------------
-- Approval gate
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS approval_requests (
    id            VARCHAR(36)  PRIMARY KEY,
    action        VARCHAR(80)  NOT NULL,
    resource_type VARCHAR(80),
    resource_id   VARCHAR(200),
    requested_by  VARCHAR(200) NOT NULL,
    reason        TEXT,
    status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
    reviewed_by   VARCHAR(200),
    review_note   TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    reviewed_at   TIMESTAMPTZ
);

-- -------------------------------------------------------------------------
-- Memory
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_records (
    id         VARCHAR(36)  PRIMARY KEY,
    scope      VARCHAR(40)  NOT NULL,
    owner_id   VARCHAR(200),
    key        VARCHAR(200) NOT NULL,
    value      TEXT         NOT NULL,
    source     VARCHAR(200),
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
