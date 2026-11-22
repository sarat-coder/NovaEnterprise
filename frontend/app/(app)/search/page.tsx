"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { researchApi, ApiError } from "@/lib/api-client";
import { canStartResearch, getRole } from "@/lib/auth";

const EXAMPLE = "Which customers were impacted by the Payments API last quarter, what incidents occurred, which teams own those services, and what decisions were taken to prevent recurrence?";

export default function SearchPage() {
  const router = useRouter();
  const role = getRole();
  const allowed = canStartResearch(role);

  const [question, setQuestion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await researchApi.start(question);
      router.push(`/research/${res.session_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 pt-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Research a question</h1>
        <p className="text-slate-500 text-sm mt-1">
          Ask anything about customers, incidents, services, or decisions. The platform retrieves
          evidence from documents, the database, and the knowledge graph, then synthesises a cited
          answer.
        </p>
      </div>

      {!allowed && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg text-sm">
          Viewers cannot start research. Sign in as <strong>analyst</strong> or <strong>admin</strong> to use this feature.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!allowed}
          rows={4}
          minLength={5}
          maxLength={2000}
          placeholder={allowed ? "Type your question here…" : "Sign in as analyst or admin to start research."}
          className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
        />
        <div className="flex items-center justify-between">
          <button
            type="button"
            disabled={!allowed}
            onClick={() => setQuestion(EXAMPLE)}
            className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-30"
          >
            Use canonical question
          </button>
          <button
            type="submit"
            disabled={!allowed || loading || question.length < 5}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
          >
            {loading ? "Starting…" : "Research →"}
          </button>
        </div>
      </form>
    </div>
  );
}
