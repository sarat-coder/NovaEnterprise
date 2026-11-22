"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { researchApi, ApiError } from "@/lib/api-client";
import type { ResearchSession, WorkflowEvent, Evidence } from "@/lib/types";

const NODE_LABELS: Record<string, string> = {
  analyze_query: "Analysing question",
  assess_complexity: "Assessing complexity",
  decompose: "Decomposing into sub-questions",
  route_retrieval: "Routing retrieval",
  vector_retrieval: "Vector / semantic search",
  sql_retrieval: "SQL records lookup",
  graph_retrieval: "Graph traversal",
  hybrid_retrieval: "Hybrid retrieval",
  collect_evidence: "Collecting evidence",
  check_missing_evidence: "Checking for gaps",
  corrective_retrieval: "Corrective retrieval",
  verify_evidence: "Verifying evidence",
  synthesize_answer: "Synthesising answer",
  verify_citations: "Verifying citations",
};

function SqlCypherPanel({ evidence }: { evidence: Evidence[] }) {
  const sqlItems = evidence.filter((e) => e.source_type === "sql");
  const graphItems = evidence.filter((e) => e.source_type === "graph");

  if (sqlItems.length === 0 && graphItems.length === 0) return null;

  const uniqueSql = Array.from(new Set(sqlItems.map((e) => e.locator)));
  const uniqueCypher = Array.from(new Set(graphItems.map((e) => e.locator)));

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-700 mb-2">Queries executed</h2>
      <div className="space-y-2">
        {uniqueSql.map((q, i) => (
          <div key={i} className="bg-green-50 border border-green-200 rounded-lg p-3">
            <p className="text-xs font-medium text-green-700 mb-1">SQL</p>
            <pre className="text-xs text-green-900 whitespace-pre-wrap font-mono overflow-x-auto">{q}</pre>
          </div>
        ))}
        {uniqueCypher.map((q, i) => (
          <div key={i} className="bg-purple-50 border border-purple-200 rounded-lg p-3">
            <p className="text-xs font-medium text-purple-700 mb-1">Cypher</p>
            <pre className="text-xs text-purple-900 whitespace-pre-wrap font-mono overflow-x-auto">{q}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}

function MemoryScopesPanel({ session }: { session: ResearchSession }) {
  const { memory_scopes } = session;
  if (!memory_scopes) return null;

  const scopes = [
    { key: "organizational", label: "Organizational", cls: "bg-blue-50 border-blue-200 text-blue-700" },
    { key: "conversation", label: "Conversation", cls: "bg-emerald-50 border-emerald-200 text-emerald-700" },
    { key: "session", label: "Session", cls: "bg-amber-50 border-amber-200 text-amber-700" },
    { key: "user", label: "Analyst", cls: "bg-rose-50 border-rose-200 text-rose-700" },
  ] as const;

  const hasAny = scopes.some(
    (s) => Object.keys(memory_scopes[s.key] ?? {}).length > 0,
  );
  if (!hasAny) return null;

  return (
    <section>
      <h2 className="text-sm font-semibold text-slate-700 mb-2">Memory scopes</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {scopes.map(({ key, label, cls }) => {
          const data = memory_scopes[key] ?? {};
          const entries = Object.entries(data);
          return (
            <div key={key} className={`border rounded-lg p-3 ${cls}`}>
              <p className="text-xs font-semibold mb-1">{label}</p>
              {entries.length === 0 ? (
                <p className="text-xs text-slate-400 italic">empty</p>
              ) : (
                <ul className="text-xs text-slate-700 space-y-0.5">
                  {entries.slice(0, 5).map(([k, v]) => (
                    <li key={k}>
                      <span className="font-medium">{k}:</span>{" "}
                      {typeof v === "string" ? v : JSON.stringify(v)}
                    </li>
                  ))}
                  {entries.length > 5 && (
                    <li className="text-slate-400">+{entries.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function ResearchSessionPage({ params }: { params: { id: string } }) {
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const [s, evs] = await Promise.all([
          researchApi.get(params.id),
          researchApi.events(params.id),
        ]);
        setSession(s);
        setEvents(evs);
        if (s.status === "completed" || s.status === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to load");
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [params.id]);

  if (error) return <div className="text-red-600 text-sm">{error}</div>;
  if (!session) return <div className="text-slate-500 text-sm">Loading session…</div>;

  const statusColor =
    session.status === "completed" ? "text-green-700" :
    session.status === "error" ? "text-red-700" : "text-blue-700";

  const verificationRatio =
    session.evidence_count > 0
      ? Math.round((session.citation_count / session.evidence_count) * 100)
      : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link href="/search" className="text-sm text-blue-600 hover:underline shrink-0 mt-0.5">← Search</Link>
        <div>
          <h1 className="text-lg font-bold text-slate-900 leading-snug">{session.question}</h1>
          <p className={`text-sm font-medium mt-0.5 ${statusColor}`}>
            {session.status}
            {session.complexity && ` · ${session.complexity}`}
            {session.strategies_used.length > 0 && ` · ${session.strategies_used.join(", ")}`}
          </p>
        </div>
      </div>

      {/* Sub-questions */}
      {session.sub_questions.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">Sub-questions</h2>
          <div className="space-y-2">
            {session.sub_questions.map((sq) => (
              <div key={sq.id} className="bg-white border border-slate-200 rounded-lg p-3 text-sm">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs text-slate-400">{sq.id}</span>
                  <span className="bg-blue-50 text-blue-700 text-xs px-1.5 py-0.5 rounded">{sq.strategy}</span>
                  <span className={`text-xs ${sq.status === "completed" ? "text-green-600" : sq.status === "error" ? "text-red-600" : "text-slate-400"}`}>
                    {sq.status}
                  </span>
                </div>
                <p className="text-slate-700">{sq.question}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Queries: SQL + Cypher */}
      {session.evidence.length > 0 && (
        <SqlCypherPanel evidence={session.evidence} />
      )}

      {/* Answer */}
      {session.answer && (
        <section>
          <div className="flex items-center gap-3 mb-2">
            <h2 className="text-sm font-semibold text-slate-700">Answer</h2>
            {session.citations_valid != null && (
              <span className={`text-xs font-normal ${session.citations_valid ? "text-green-600" : "text-red-600"}`}>
                {session.citations_valid ? "citations verified" : "citation issues"}
              </span>
            )}
            {verificationRatio != null && (
              <span className="text-xs text-slate-400">
                verification {verificationRatio}% ({session.citation_count}/{session.evidence_count})
              </span>
            )}
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4 text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
            {session.answer}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {session.evidence_count} evidence items · {session.citation_count} citations · {session.corrective_rounds} corrective rounds
          </p>
        </section>
      )}

      {/* Evidence */}
      {session.evidence.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">Evidence ({session.evidence.length})</h2>
          <div className="space-y-2">
            {session.evidence.map((ev) => (
              <div key={ev.id} className="bg-white border border-slate-200 rounded-lg p-3 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-slate-400">[{ev.id}]</span>
                  <span className={`px-1.5 py-0.5 rounded ${ev.source_type === "document" ? "bg-blue-50 text-blue-700" : ev.source_type === "sql" ? "bg-green-50 text-green-700" : "bg-purple-50 text-purple-700"}`}>
                    {ev.source_type}
                  </span>
                  <span className="text-slate-400">score: {ev.score.toFixed(2)}</span>
                </div>
                <p className="text-slate-700 line-clamp-3">{ev.content}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Memory scopes */}
      <MemoryScopesPanel session={session} />

      {/* Event timeline */}
      {events.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-2">Event timeline</h2>
          <div className="space-y-1">
            {events.map((ev) => (
              <div key={ev.id} className="flex items-center gap-3 text-xs text-slate-600">
                <span className="text-slate-400 font-mono w-20 shrink-0">
                  {ev.duration_ms != null ? `${ev.duration_ms.toFixed(0)}ms` : "—"}
                </span>
                <span className="text-slate-700">{NODE_LABELS[ev.node] ?? ev.node}</span>
                <span className="text-slate-400">{ev.event_type}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
