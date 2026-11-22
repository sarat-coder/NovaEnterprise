/**
 * Typed API client — mirrors docs/API_CONTRACT.md exactly.
 * All backend calls go through this module; never use ad-hoc fetch in components.
 */

import { getToken } from "./auth";
import type {
  LoginRequest,
  LoginResponse,
  MeResponse,
  HealthReady,
  CustomerSummary,
  IncidentSummary,
  IncidentDetail,
  DecisionSummary,
  DecisionDetail,
  ResearchStartResponse,
  ResearchSession,
  WorkflowEvent,
  DocumentRecord,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let _rateLimitUntil = 0;

async function request<T>(
  path: string,
  options: RequestInit = {},
  skipAuth = false,
): Promise<T> {
  if (Date.now() < _rateLimitUntil) {
    const wait = Math.ceil((_rateLimitUntil - Date.now()) / 1000);
    throw new ApiError(429, `Rate limited — retry in ${wait}s`);
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (!skipAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const requestId = res.headers.get("X-Request-ID") ?? undefined;

  if (res.status === 429) {
    _rateLimitUntil = Date.now() + 60_000;
    throw new ApiError(429, "Rate limited — backing off 60 s", requestId);
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore parse failure */
    }
    throw new ApiError(res.status, detail, requestId);
  }

  return res.json() as Promise<T>;
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (data: LoginRequest) =>
    request<LoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }, true),

  me: () => request<MeResponse>("/api/v1/auth/me"),
};

// ─── Health ───────────────────────────────────────────────────────────────────

export const healthApi = {
  ready: () => request<HealthReady>("/health/ready", {}, true),
};

// ─── Customers ────────────────────────────────────────────────────────────────

export const customersApi = {
  list: () => request<CustomerSummary[]>("/api/v1/customers"),
  get: (id: number) => request<CustomerSummary>(`/api/v1/customers/${id}`),
};

// ─── Incidents ────────────────────────────────────────────────────────────────

export const incidentsApi = {
  list: (params?: { severity?: string; service_id?: number }) => {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.service_id) qs.set("service_id", String(params.service_id));
    const q = qs.toString();
    return request<IncidentSummary[]>(`/api/v1/incidents${q ? `?${q}` : ""}`);
  },
  get: (id: number) => request<IncidentDetail>(`/api/v1/incidents/${id}`),
};

// ─── Decisions ────────────────────────────────────────────────────────────────

export const decisionsApi = {
  list: () => request<DecisionSummary[]>("/api/v1/decisions"),
  get: (id: number) => request<DecisionDetail>(`/api/v1/decisions/${id}`),
};

// ─── Research ─────────────────────────────────────────────────────────────────

export const researchApi = {
  start: (question: string) =>
    request<ResearchStartResponse>("/api/v1/research", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  get: (sessionId: string) =>
    request<ResearchSession>(`/api/v1/research/${sessionId}`),
  events: (sessionId: string) =>
    request<WorkflowEvent[]>(`/api/v1/research/${sessionId}/events`),
};

// ─── Documents ────────────────────────────────────────────────────────────────

export const documentsApi = {
  list: () => request<DocumentRecord[]>("/api/v1/documents"),
};

export { ApiError };
