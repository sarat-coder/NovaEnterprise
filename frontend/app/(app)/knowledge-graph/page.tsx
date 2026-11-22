"use client";

import { useEffect, useState, useCallback } from "react";
import { graphApi, ApiError } from "@/lib/api-client";
import { canRunCypher, getRole } from "@/lib/auth";
import type { GraphNode, GraphNeighbors, CypherResult, GraphStats } from "@/lib/types";

const LABEL_COLORS: Record<string, string> = {
  Service: "bg-blue-100 text-blue-800",
  Incident: "bg-red-100 text-red-800",
  Customer: "bg-emerald-100 text-emerald-800",
  Team: "bg-purple-100 text-purple-800",
  Decision: "bg-amber-100 text-amber-800",
  Employee: "bg-slate-100 text-slate-700",
};

function labelColor(label: string) {
  return LABEL_COLORS[label] ?? "bg-slate-100 text-slate-700";
}

function NodeCard({
  node,
  selected,
  onClick,
}: {
  node: GraphNode;
  selected: boolean;
  onClick: () => void;
}) {
  const name =
    (node.properties.name as string) ??
    (node.properties.title as string) ??
    (node.properties.incident_id as string) ??
    node.node_id;

  return (
    <button
      onClick={onClick}
      className={`w-full text-left border rounded-lg p-3 text-sm transition-colors ${
        selected
          ? "border-blue-500 bg-blue-50"
          : "border-slate-200 bg-white hover:border-blue-300"
      }`}
    >
      <div className="flex items-center gap-2 mb-0.5">
        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${labelColor(node.label)}`}>
          {node.label}
        </span>
      </div>
      <p className="font-medium text-slate-900 truncate">{name}</p>
      <p className="text-xs text-slate-400 font-mono truncate">{node.node_id}</p>
    </button>
  );
}

function NeighborPanel({
  neighbors,
  onSelectNode,
}: {
  neighbors: GraphNeighbors;
  onSelectNode: (node: GraphNode) => void;
}) {
  const { node, neighbors: nbrs, edges } = neighbors;
  const name =
    (node.properties.name as string) ??
    (node.properties.title as string) ??
    node.node_id;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-4">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${labelColor(node.label)}`}>
            {node.label}
          </span>
        </div>
        <h3 className="font-bold text-slate-900">{name}</h3>
        <p className="text-xs text-slate-400 font-mono">{node.node_id}</p>
        {Object.keys(node.properties).length > 0 && (
          <dl className="mt-2 text-xs space-y-0.5">
            {Object.entries(node.properties).slice(0, 6).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="text-slate-500 shrink-0">{k}:</dt>
                <dd className="text-slate-800 truncate">{String(v)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {nbrs.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-600 mb-2">
            {nbrs.length} neighbour{nbrs.length !== 1 ? "s" : ""}
          </p>
          <div className="space-y-2">
            {nbrs.map((n) => {
              const edge = edges.find(
                (e) =>
                  (e.source_id === node.node_id && e.target_id === n.node_id) ||
                  (e.target_id === node.node_id && e.source_id === n.node_id),
              );
              const nname =
                (n.properties.name as string) ??
                (n.properties.title as string) ??
                n.node_id;
              return (
                <button
                  key={n.node_id}
                  onClick={() => onSelectNode(n)}
                  className="w-full text-left flex items-center gap-2 border border-slate-100 rounded-lg px-3 py-2 hover:border-blue-300 transition-colors"
                >
                  {edge && (
                    <span className="text-xs text-slate-400 font-mono shrink-0">
                      [{edge.relationship}]
                    </span>
                  )}
                  <span className={`text-xs px-1.5 py-0.5 rounded ${labelColor(n.label)}`}>
                    {n.label}
                  </span>
                  <span className="text-sm text-slate-900 truncate">{nname}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {nbrs.length === 0 && (
        <p className="text-xs text-slate-400 italic">No neighbours found.</p>
      )}
    </div>
  );
}

function CypherConsole() {
  const [cypher, setCypher] = useState("MATCH (n) RETURN n LIMIT 10");
  const [result, setResult] = useState<CypherResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const r = await graphApi.runCypher(cypher);
      setResult(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Cypher error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-slate-700">Cypher console</h2>
      <div className="bg-slate-900 rounded-xl p-4 space-y-3">
        <textarea
          value={cypher}
          onChange={(e) => setCypher(e.target.value)}
          rows={4}
          className="w-full bg-slate-800 text-green-400 font-mono text-xs rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-green-500 resize-none"
        />
        <button
          onClick={run}
          disabled={loading || !cypher.trim()}
          className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-lg transition-colors"
        >
          {loading ? "Running…" : "Run Cypher"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">{error}</p>
      )}

      {result && (
        <div className="text-xs">
          <p className="text-slate-500 mb-2">{result.row_count} row{result.row_count !== 1 ? "s" : ""}</p>
          {result.rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr>
                    {Object.keys(result.rows[0]).map((col) => (
                      <th key={col} className="border border-slate-200 bg-slate-50 px-2 py-1 text-slate-600 font-semibold">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((val, j) => (
                        <td key={j} className="border border-slate-200 px-2 py-1 text-slate-800 font-mono max-w-xs truncate">
                          {JSON.stringify(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const LABELS = ["", "Service", "Incident", "Customer", "Team", "Decision", "Employee"];

export default function KnowledgeGraphPage() {
  const role = getRole();
  const analystAccess = canRunCypher(role);

  const [stats, setStats] = useState<GraphStats | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [labelFilter, setLabelFilter] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [neighbors, setNeighbors] = useState<GraphNeighbors | null>(null);
  const [loadingNodes, setLoadingNodes] = useState(true);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    graphApi.stats().then(setStats).catch(() => {});
  }, []);

  const loadNodes = useCallback(
    (label: string) => {
      setLoadingNodes(true);
      setError(null);
      graphApi
        .listNodes({ label: label || undefined, limit: 100 })
        .then(setNodes)
        .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load nodes"))
        .finally(() => setLoadingNodes(false));
    },
    [],
  );

  useEffect(() => {
    loadNodes(labelFilter);
  }, [labelFilter, loadNodes]);

  async function handleSelectNode(node: GraphNode) {
    setSelectedNode(node);
    setNeighbors(null);
    setLoadingNeighbors(true);
    try {
      const n = await graphApi.getNeighbors(node.node_id, "both");
      setNeighbors(n);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load neighbours");
    } finally {
      setLoadingNeighbors(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Knowledge Graph</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Browse entities and their relationships.
          </p>
        </div>
        {stats && (
          <div className="flex gap-4 text-center shrink-0">
            <div>
              <p className="text-2xl font-bold text-blue-600">{stats.node_count}</p>
              <p className="text-xs text-slate-500">nodes</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-600">{stats.edge_count}</p>
              <p className="text-xs text-slate-500">edges</p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 px-4 py-2 rounded-lg">{error}</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Node list */}
        <div className="lg:col-span-1 space-y-3">
          <div className="flex gap-2">
            <select
              value={labelFilter}
              onChange={(e) => setLabelFilter(e.target.value)}
              className="flex-1 border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {LABELS.map((l) => (
                <option key={l} value={l}>{l || "All labels"}</option>
              ))}
            </select>
          </div>

          {loadingNodes && (
            <p className="text-slate-500 text-sm">Loading nodes…</p>
          )}
          <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
            {nodes.map((n) => (
              <NodeCard
                key={n.node_id}
                node={n}
                selected={selectedNode?.node_id === n.node_id}
                onClick={() => handleSelectNode(n)}
              />
            ))}
            {!loadingNodes && nodes.length === 0 && (
              <p className="text-slate-400 text-sm italic">No nodes found.</p>
            )}
          </div>
        </div>

        {/* Detail / neighbor panel */}
        <div className="lg:col-span-2 space-y-4">
          {selectedNode && (
            <>
              {loadingNeighbors && (
                <p className="text-slate-500 text-sm">Loading neighbours…</p>
              )}
              {neighbors && (
                <NeighborPanel
                  neighbors={neighbors}
                  onSelectNode={handleSelectNode}
                />
              )}
            </>
          )}
          {!selectedNode && (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center">
              <p className="text-slate-400 text-sm">Select a node to explore its connections.</p>
            </div>
          )}
        </div>
      </div>

      {/* Cypher console — analysts only */}
      {analystAccess && (
        <div className="border-t border-slate-200 pt-6">
          <CypherConsole />
        </div>
      )}
      {!analystAccess && (
        <p className="text-xs text-slate-400 border-t border-slate-200 pt-4">
          Sign in as analyst or admin to run Cypher queries.
        </p>
      )}
    </div>
  );
}
