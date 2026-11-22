"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { incidentsApi, ApiError } from "@/lib/api-client";
import type { IncidentDetail } from "@/lib/types";

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  const [inc, setInc] = useState<IncidentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    incidentsApi
      .get(Number(params.id))
      .then(setInc)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"));
  }, [params.id]);

  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!inc) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="max-w-2xl space-y-4">
      <Link href="/incidents" className="text-sm text-blue-600 hover:underline">← Incidents</Link>

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="font-mono text-xs text-slate-500">{inc.incident_id}</span>
            <h1 className="text-xl font-bold text-slate-900 mt-0.5">{inc.title}</h1>
          </div>
          <span className="text-sm font-semibold text-red-700 bg-red-100 px-2 py-0.5 rounded-full shrink-0">
            {inc.severity}
          </span>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-500">Service</dt>
          <dd className="text-slate-900">{inc.service_name}</dd>
          <dt className="text-slate-500">Status</dt>
          <dd className="text-slate-900 capitalize">{inc.status}</dd>
          <dt className="text-slate-500">Started</dt>
          <dd className="text-slate-900">{new Date(inc.started_at).toLocaleString()}</dd>
          {inc.resolved_at && (
            <>
              <dt className="text-slate-500">Resolved</dt>
              <dd className="text-slate-900">{new Date(inc.resolved_at).toLocaleString()}</dd>
            </>
          )}
        </dl>

        {inc.root_cause && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Root cause</p>
            <p className="text-sm text-slate-700">{inc.root_cause}</p>
          </div>
        )}

        {inc.summary && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Summary</p>
            <p className="text-sm text-slate-700">{inc.summary}</p>
          </div>
        )}

        {inc.impacted_customers.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">Impacted customers</p>
            <div className="flex flex-wrap gap-2">
              {inc.impacted_customers.map((c) => (
                <Link
                  key={c.id}
                  href={`/customers/${c.id}`}
                  className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded hover:bg-blue-100 transition-colors"
                >
                  {c.name}
                </Link>
              ))}
            </div>
          </div>
        )}

        {inc.decisions.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">Related decisions</p>
            <div className="flex flex-wrap gap-2">
              {inc.decisions.map((d) => (
                <Link
                  key={d.id}
                  href={`/decisions/${d.id}`}
                  className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded hover:bg-purple-100 transition-colors"
                >
                  {d.adr_id}: {d.title}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
