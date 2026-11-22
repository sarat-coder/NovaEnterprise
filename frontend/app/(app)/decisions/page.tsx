"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { decisionsApi, ApiError } from "@/lib/api-client";
import type { DecisionSummary } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  accepted: "bg-green-100 text-green-700",
  proposed: "bg-blue-100 text-blue-700",
  superseded: "bg-slate-100 text-slate-500",
  deprecated: "bg-red-100 text-red-600",
};

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<DecisionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    decisionsApi
      .list()
      .then(setDecisions)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">Decisions (ADRs)</h1>

      {loading && <p className="text-slate-500 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="space-y-2">
        {decisions.map((d) => (
          <Link
            key={d.id}
            href={`/decisions/${d.id}`}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-start gap-4 hover:shadow-md transition-shadow"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-xs text-slate-500">{d.adr_id}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[d.status] ?? "bg-slate-100 text-slate-600"}`}>
                  {d.status}
                </span>
              </div>
              <p className="font-semibold text-slate-900 text-sm">{d.title}</p>
              {d.context && (
                <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{d.context}</p>
              )}
            </div>
            <p className="text-xs text-slate-400 shrink-0">
              {new Date(d.decided_at).toLocaleDateString()}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
