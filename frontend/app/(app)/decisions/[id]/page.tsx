"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { decisionsApi, ApiError } from "@/lib/api-client";
import type { DecisionDetail } from "@/lib/types";

export default function DecisionDetailPage({ params }: { params: { id: string } }) {
  const [d, setD] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    decisionsApi
      .get(Number(params.id))
      .then(setD)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"));
  }, [params.id]);

  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!d) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="max-w-2xl space-y-4">
      <Link href="/decisions" className="text-sm text-blue-600 hover:underline">← Decisions</Link>

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
        <div>
          <span className="font-mono text-xs text-slate-500">{d.adr_id}</span>
          <h1 className="text-xl font-bold text-slate-900 mt-0.5">{d.title}</h1>
          <p className="text-xs text-slate-400 mt-1">{new Date(d.decided_at).toLocaleDateString()}</p>
        </div>

        {d.context && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Context</p>
            <p className="text-sm text-slate-700">{d.context}</p>
          </div>
        )}

        {d.decision_text && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Decision</p>
            <p className="text-sm text-slate-700">{d.decision_text}</p>
          </div>
        )}

        {d.consequences && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-1">Consequences</p>
            <p className="text-sm text-slate-700">{d.consequences}</p>
          </div>
        )}

        {d.incidents.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 mb-2">Related incidents</p>
            <div className="flex flex-wrap gap-2">
              {d.incidents.map((inc) => (
                <Link
                  key={inc.id}
                  href={`/incidents/${inc.id}`}
                  className="text-xs bg-red-50 text-red-700 px-2 py-1 rounded hover:bg-red-100 transition-colors"
                >
                  {inc.incident_id}: {inc.title}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
