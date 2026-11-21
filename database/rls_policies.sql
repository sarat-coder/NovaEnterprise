-- NovaEnterprise — Postgres Row-Level Security policies
-- Apply after schema.sql when using Supabase / Postgres with auth.uid().
-- Requires: supabase auth schema, app_role claim in JWT.
-- SQLite (dev/test) skips RLS; enforcement is in backend/app/core/security.py.

-- Enable RLS on all application tables
ALTER TABLE teams               ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees           ENABLE ROW LEVEL SECURITY;
ALTER TABLE services            ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers           ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_customers  ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE incident_decisions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects            ENABLE ROW LEVEL SECURITY;
ALTER TABLE tickets             ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sessions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests   ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_records      ENABLE ROW LEVEL SECURITY;

-- -------------------------------------------------------------------------
-- Helper: extract role from JWT (Supabase stores it as app_metadata.role)
-- -------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION current_app_role()
RETURNS TEXT LANGUAGE sql STABLE AS $$
  SELECT coalesce(
    current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'role',
    'viewer'
  );
$$;

-- -------------------------------------------------------------------------
-- Domain tables — read by any authenticated user
-- -------------------------------------------------------------------------

CREATE POLICY "read_teams"      ON teams      FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_employees"  ON employees  FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_services"   ON services   FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_customers"  ON customers  FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_incidents"  ON incidents  FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_inc_cust"   ON incident_customers FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_decisions"  ON decisions  FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_inc_dec"    ON incident_decisions FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_projects"   ON projects   FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "read_tickets"    ON tickets    FOR SELECT USING (auth.uid() IS NOT NULL);

-- -------------------------------------------------------------------------
-- Research sessions — owner or admin
-- -------------------------------------------------------------------------

CREATE POLICY "read_own_sessions" ON research_sessions FOR SELECT USING (
    user_id = auth.uid()::text OR current_app_role() = 'admin'
);

CREATE POLICY "insert_sessions" ON research_sessions FOR INSERT WITH CHECK (
    current_app_role() IN ('analyst', 'admin')
);

CREATE POLICY "read_own_events" ON workflow_events FOR SELECT USING (
    session_id IN (
        SELECT id FROM research_sessions
        WHERE user_id = auth.uid()::text OR current_app_role() = 'admin'
    )
);

-- -------------------------------------------------------------------------
-- Documents — read by all authenticated; delete only by admin after approval
-- -------------------------------------------------------------------------

CREATE POLICY "read_documents"   ON documents FOR SELECT USING (auth.uid() IS NOT NULL);
CREATE POLICY "insert_documents" ON documents FOR INSERT WITH CHECK (
    current_app_role() IN ('analyst', 'admin')
);
CREATE POLICY "delete_documents" ON documents FOR DELETE USING (
    current_app_role() = 'admin'
);
CREATE POLICY "read_chunks" ON document_chunks FOR SELECT USING (auth.uid() IS NOT NULL);

-- -------------------------------------------------------------------------
-- Approval requests — admin can read all; requestor reads own
-- -------------------------------------------------------------------------

CREATE POLICY "read_approvals" ON approval_requests FOR SELECT USING (
    requested_by = auth.uid()::text OR current_app_role() = 'admin'
);
CREATE POLICY "insert_approvals" ON approval_requests FOR INSERT WITH CHECK (
    current_app_role() IN ('analyst', 'admin')
);
CREATE POLICY "update_approvals" ON approval_requests FOR UPDATE USING (
    current_app_role() = 'admin'
);

-- -------------------------------------------------------------------------
-- Memory records — analyst reads/writes own; admin reads all
-- -------------------------------------------------------------------------

CREATE POLICY "read_memory" ON memory_records FOR SELECT USING (
    scope = 'organizational'
    OR owner_id = auth.uid()::text
    OR current_app_role() = 'admin'
);
CREATE POLICY "write_memory" ON memory_records FOR INSERT WITH CHECK (
    owner_id = auth.uid()::text OR current_app_role() = 'admin'
);
CREATE POLICY "update_memory" ON memory_records FOR UPDATE USING (
    owner_id = auth.uid()::text OR current_app_role() = 'admin'
);
