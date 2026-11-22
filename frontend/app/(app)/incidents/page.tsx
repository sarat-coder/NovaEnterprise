"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { incidentsApi, ApiError } from "@/lib/api-client";
import type { IncidentSummary } from "@/lib/types";

const SEV_COLORS: Record<string, string> = {
  SEV1: "bg-red-100 text-red-700",
  SEV2: "bg-orange-100 text-orange-700",
  SEV3: "bg-yellow-100 text-yellow-700",
};

const STATUS_COLORS: Record<string, string> = {
  resolved: "bg-green-100 text-green-700",
  investigating: "bg-blue-100 text-blue-700",
  open: "bg-red-100 text-red-700",
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [severity, setSeverity] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    incidentsApi
      .list(severity ? { severity } : undefined)
      .then(setIncidents)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [severity]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h1 className="text-xl font-bold text-slate-900">Incidents</h1>
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="border border-slate-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All severities</option>
          <option value="SEV1">SEV1</option>
          <option value="SEV2">SEV2</option>
          <option value="SEV3">SEV3</option>
        </select>
      </div>

      {loading && <p className="text-slate-500 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="space-y-2">
        {incidents.map((inc) => (
          <Link
            key={inc.id}
            href={`/incidents/${inc.id}`}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-start gap-4 hover:shadow-md transition-shadow"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="font-mono text-xs text-slate-500">{inc.incident_id}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${SEV_COLORS[inc.severity] ?? "bg-slate-100 text-slate-600"}`}>
                  {inc.severity}
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[inc.status] ?? "bg-slate-100 text-slate-600"}`}>
                  {inc.status}
                </span>
              </div>
              <p className="font-semibold text-slate-900 text-sm truncate">{inc.title}</p>
              <p className="text-xs text-slate-500 mt-0.5">{inc.service_name}</p>
            </div>
            <p className="text-xs text-slate-400 shrink-0">
              {new Date(inc.started_at).toLocaleDateString()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
