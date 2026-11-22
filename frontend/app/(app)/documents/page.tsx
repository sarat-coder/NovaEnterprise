"use client";

import { useEffect, useState } from "react";
import { documentsApi, ApiError } from "@/lib/api-client";
import type { DocumentRecord } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  indexed: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  error: "bg-red-100 text-red-700",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    documentsApi
      .list()
      .then(setDocs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">Documents</h1>

      {loading && <p className="text-slate-500 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="space-y-2">
        {docs.map((doc) => (
          <div
            key={doc.id}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-center gap-4"
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-900 text-sm truncate">{doc.filename}</p>
              <p className="text-xs text-slate-400 mt-0.5">
                {doc.chunk_count} chunks · {(doc.size_bytes / 1024).toFixed(1)} KB
              </p>
            </div>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${STATUS_COLORS[doc.status] ?? "bg-slate-100 text-slate-600"}`}>
              {doc.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
