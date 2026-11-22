"use client";

import { useEffect, useState, useRef } from "react";
import { documentsApi, ApiError } from "@/lib/api-client";
import { canUpload, getRole } from "@/lib/auth";
import type { DocumentRecord, DocumentUploadResponse, ApprovalRequest } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  indexed: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  error: "bg-red-100 text-red-700",
  deleted: "bg-slate-100 text-slate-500",
};

function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<DocumentUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setError(null);
    setResult(null);
    setUploading(true);
    try {
      const r = await documentsApi.upload(file);
      setResult(r);
      if (fileRef.current) fileRef.current.value = "";
      onUploaded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <form onSubmit={handleUpload} className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-3">
      <h2 className="text-sm font-semibold text-blue-800">Upload a document</h2>
      <p className="text-xs text-blue-600">Allowed: .md, .txt, .pdf · Max 5 MB</p>
      <div className="flex gap-3 items-center">
        <input
          ref={fileRef}
          type="file"
          accept=".md,.txt,.pdf"
          className="text-xs text-slate-700 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-blue-100 file:text-blue-700 hover:file:bg-blue-200"
        />
        <button
          type="submit"
          disabled={uploading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors shrink-0"
        >
          {uploading ? "Uploading…" : "Upload"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-1.5 rounded-lg">{error}</p>
      )}
      {result && (
        <div className={`text-xs px-3 py-1.5 rounded-lg ${result.flagged ? "bg-amber-50 border border-amber-200 text-amber-800" : "bg-green-50 border border-green-200 text-green-800"}`}>
          {result.message} · {result.chunk_count} chunks
          {result.flagged && " ⚠ flagged for review"}
        </div>
      )}
    </form>
  );
}

function DeleteButton({
  doc,
  onRequested,
}: {
  doc: DocumentRecord;
  onRequested: (approval: ApprovalRequest) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!window.confirm(`Request deletion of "${doc.filename}"? An admin must approve before it is removed.`)) return;
    setError(null);
    setLoading(true);
    try {
      const approval = await documentsApi.requestDelete(doc.id);
      onRequested(approval);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        onClick={handleDelete}
        disabled={loading}
        className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50 border border-red-200 hover:border-red-400 px-2 py-1 rounded transition-colors"
      >
        {loading ? "…" : "Request delete"}
      </button>
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
    </div>
  );
}

export default function DocumentsPage() {
  const role = getRole();
  const uploadAllowed = canUpload(role);

  const [docs, setDocs] = useState<DocumentRecord[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<Map<string, ApprovalRequest>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function loadDocs() {
    setLoading(true);
    documentsApi
      .list()
      .then(setDocs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadDocs(); }, []);

  function handleDeleteRequested(approval: ApprovalRequest) {
    setPendingApprovals((prev) => {
      const next = new Map(prev);
      next.set(approval.resource_id, approval);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Documents</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {docs.length} document{docs.length !== 1 ? "s" : ""} indexed
        </p>
      </div>

      {uploadAllowed && (
        <UploadForm onUploaded={loadDocs} />
      )}

      {!uploadAllowed && (
        <p className="text-xs text-slate-400 bg-slate-50 border border-slate-200 px-4 py-2 rounded-lg">
          Sign in as analyst or admin to upload documents.
        </p>
      )}

      {loading && <p className="text-slate-500 text-sm">Loading…</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}

      <div className="space-y-2">
        {docs.map((doc) => {
          const pendingDelete = pendingApprovals.has(doc.id);
          return (
            <div
              key={doc.id}
              className="bg-white border border-slate-200 rounded-xl p-4"
            >
              <div className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 text-sm truncate">{doc.filename}</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {doc.chunk_count} chunks · {(doc.size_bytes / 1024).toFixed(1)} KB ·{" "}
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                  {pendingDelete && (
                    <p className="text-xs text-amber-600 mt-1">
                      Deletion requested — awaiting admin approval
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[doc.status] ?? "bg-slate-100 text-slate-600"}`}>
                    {doc.status}
                  </span>
                  {uploadAllowed && !pendingDelete && doc.status !== "deleted" && (
                    <DeleteButton doc={doc} onRequested={handleDeleteRequested} />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
