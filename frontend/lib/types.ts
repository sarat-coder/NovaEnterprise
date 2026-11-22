// ─── Auth ────────────────────────────────────────────────────────────────────

export type Role = "viewer" | "analyst" | "admin";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
}

export interface MeResponse {
  sub: string;
  role: Role;
  user_id: string;
}

// ─── Health ───────────────────────────────────────────────────────────────────

export type HealthStatus = "ok" | "degraded" | "error";

export interface CheckDetail {
  status: HealthStatus;
  detail: string;
}

export interface HealthReady {
  status: HealthStatus;
  checks: {
    app: CheckDetail;
    database: CheckDetail;
    redis: CheckDetail;
    vector_store: CheckDetail;
    graph_store: CheckDetail;
    llm: CheckDetail;
  };
}

// ─── Browse — Customers ───────────────────────────────────────────────────────

export interface CustomerSummary {
  id: number;
  name: string;
  slug: string;
  segment: string;
  industry: string;
  contract_tier: string;
}

// ─── Browse — Incidents ───────────────────────────────────────────────────────

export interface IncidentSummary {
  id: number;
  incident_id: string;
  title: string;
  severity: "SEV1" | "SEV2" | "SEV3";
  status: string;
  service_id: number;
  service_name: string;
  root_cause: string;
  summary: string;
  started_at: string;
  resolved_at: string | null;
}

export interface IncidentDetail extends IncidentSummary {
  impacted_customers: { id: number; name: string; slug: string; segment: string }[];
  decisions: { id: number; adr_id: string; title: string; status: string }[];
}

// ─── Browse — Decisions ───────────────────────────────────────────────────────

export interface DecisionSummary {
  id: number;
  adr_id: string;
  title: string;
  status: string;
  context: string;
  decision_text: string;
  consequences: string;
  decided_at: string;
}

export interface DecisionDetail extends DecisionSummary {
  incidents: { id: number; incident_id: string; title: string; severity: string }[];
}

// ─── Research ─────────────────────────────────────────────────────────────────

export type ResearchStatus = "running" | "completed" | "error";
export type Strategy = "vector" | "sql" | "graph" | "hybrid";
export type Complexity = "simple" | "moderate" | "complex";
export type SubQuestionStatus = "pending" | "running" | "completed" | "error";

export interface ResearchStartResponse {
  session_id: string;
  status: "running";
}

export interface SubQuestion {
  id: string;
  question: string;
  strategy: Strategy;
  status: SubQuestionStatus;
  evidence_ids: string[];
}

export interface Evidence {
  id: string;
  source_type: "document" | "sql" | "graph";
  locator: string;
  content: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface MemoryScopes {
  organizational: Record<string, unknown>;
  conversation: Record<string, unknown>;
  session: Record<string, unknown>;
  user: Record<string, unknown>;
}

export interface ResearchSession {
  session_id: string;
  question: string;
  status: ResearchStatus;
  complexity: Complexity | null;
  strategies_used: Strategy[];
  sub_questions: SubQuestion[];
  evidence: Evidence[];
  answer: string | null;
  citations_valid: boolean | null;
  evidence_count: number;
  citation_count: number;
  corrective_rounds: number;
  memory_scopes: MemoryScopes;
  started_at: string;
  completed_at: string | null;
}

export interface WorkflowEvent {
  id: number;
  node: string;
  event_type: string;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  occurred_at: string;
}

// ─── Documents ────────────────────────────────────────────────────────────────

export interface DocumentRecord {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  doc_id: string;
  filename: string;
  chunk_count: number;
  flagged: boolean;
  message: string;
}

export interface ApprovalRequest {
  id: string;
  resource_type: string;
  resource_id: string;
  action: string;
  requested_by: string;
  status: string;
  note: string | null;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
}

// ─── Knowledge Graph ──────────────────────────────────────────────────────────

export interface GraphNode {
  node_id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  relationship: string;
  properties: Record<string, unknown>;
}

export interface GraphNeighbors {
  node: GraphNode;
  neighbors: GraphNode[];
  edges: GraphEdge[];
}

export interface CypherResult {
  rows: Record<string, unknown>[];
  row_count: number;
  cypher: string;
}

export interface GraphStats {
  node_count: number;
  edge_count: number;
}
