"""GraphStoreService protocol and in-memory adapter (P7-1).

Nothing outside rag/ knows which adapter is active.
The active adapter is selected by GRAPH_STORE in settings and exposed through
get_graph_store() which is called once at startup.

Typed traversals (P7-2) live here as well.  Every traversal method returns
a list[Evidence] where source_type="graph" and also exposes the Cypher
query it represents — satisfying F8.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.schemas.common import Evidence  # noqa: TCH001

# ---------------------------------------------------------------------------
# Domain types shared by all adapters
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A node in the knowledge graph."""

    node_id: str
    label: str  # e.g. "Team", "Service", "Incident", "Customer"
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge between two nodes."""

    source_id: str
    target_id: str
    relationship: str  # e.g. "OWNED_BY", "AFFECTED", "IMPACTED"
    properties: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol (N3 — replaceable stores)
# ---------------------------------------------------------------------------


@runtime_checkable
class GraphStoreService(Protocol):
    """Minimal protocol every graph-store adapter must satisfy."""

    def add_node(self, node: GraphNode) -> None:
        """Upsert a node into the graph."""
        ...

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed relationship between two nodes."""
        ...

    def get_node(self, node_id: str) -> GraphNode | None:
        """Return a node by its id, or None."""
        ...

    def get_neighbors(
        self,
        node_id: str,
        relationship: str | None = None,
        direction: str = "out",
    ) -> list[GraphNode]:
        """Return neighbouring nodes, optionally filtered by relationship type.

        direction: "out" (default) follows edges source→target,
                   "in" follows edges target→source.
        """
        ...

    # ------------------------------------------------------------------
    # Typed traversals (F8) — each returns Evidence + Cypher
    # ------------------------------------------------------------------

    def traverse_impacted_customers(
        self,
        service_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Evidence]:
        """Graph path: (Service)<-[:AFFECTED]-(Incident)-[:IMPACTED]->(Customer).

        Returns Evidence(source_type="graph") items; metadata["cypher"] carries
        the equivalent Cypher string.
        """
        ...

    def traverse_owning_teams(self, service_name: str) -> list[Evidence]:
        """Graph path: (Service)-[:OWNED_BY]->(Team).

        Returns one Evidence item per service match.
        """
        ...

    def traverse_related_decisions(self, incident_id: str) -> list[Evidence]:
        """Graph path: (Decision)-[:ADDRESSES]->(Incident).

        Returns Evidence items for every decision linked to the incident.
        """
        ...

    def execute_cypher_readonly(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a user-supplied Cypher statement after a read-only check.

        Raises ValueError if the statement contains write clauses.
        In-memory adapter evaluates a subset via pattern matching.
        """
        ...

    def count_nodes(self) -> int:
        """Return the total number of nodes."""
        ...

    def count_edges(self) -> int:
        """Return the total number of edges."""
        ...

    def clear(self) -> None:
        """Remove all nodes and edges."""
        ...


# ---------------------------------------------------------------------------
# Read-only Cypher validation (P7-3 — shared by both adapters)
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL)\b",
    re.IGNORECASE,
)


def is_readonly_cypher(cypher: str) -> bool:
    """Return True when the Cypher statement contains no write clauses."""
    return _WRITE_KEYWORDS.search(cypher) is None


def assert_readonly_cypher(cypher: str) -> None:
    """Raise ValueError if the statement is not read-only."""
    if not is_readonly_cypher(cypher):
        match = _WRITE_KEYWORDS.search(cypher)
        keyword = match.group(0).upper() if match else "unknown"
        raise ValueError(
            f"Write operation '{keyword}' is not permitted in user-supplied Cypher. "
            "Only MATCH / RETURN / WHERE / WITH / ORDER BY / LIMIT / SKIP are allowed."
        )


# ---------------------------------------------------------------------------
# In-memory adapter (N1 — no external service)
# ---------------------------------------------------------------------------


class MemoryGraphStore:
    """Pure-Python in-memory graph store.

    Stores nodes in a dict keyed by node_id.
    Stores edges as a list; two indices (by source, by target) for fast lookup.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        # out-edges index: source_id → list[int] (indices into _edges)
        self._out: dict[str, list[int]] = {}
        # in-edges index: target_id → list[int]
        self._in: dict[str, list[int]] = {}

    # ------------------------------------------------------------------
    # GraphStoreService implementation
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        idx = len(self._edges)
        self._edges.append(edge)
        self._out.setdefault(edge.source_id, []).append(idx)
        self._in.setdefault(edge.target_id, []).append(idx)

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_neighbors(
        self,
        node_id: str,
        relationship: str | None = None,
        direction: str = "out",
    ) -> list[GraphNode]:
        if direction == "out":
            indices = self._out.get(node_id, [])
            candidates = [self._edges[i] for i in indices]
            if relationship:
                candidates = [e for e in candidates if e.relationship == relationship]
            return [self._nodes[e.target_id] for e in candidates if e.target_id in self._nodes]
        else:  # "in"
            indices = self._in.get(node_id, [])
            candidates = [self._edges[i] for i in indices]
            if relationship:
                candidates = [e for e in candidates if e.relationship == relationship]
            return [self._nodes[e.source_id] for e in candidates if e.source_id in self._nodes]

    # ------------------------------------------------------------------
    # Typed traversals (F8)
    # ------------------------------------------------------------------

    def traverse_impacted_customers(
        self,
        service_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Evidence]:
        """MATCH (svc:Service {name:$service})<-[:AFFECTED]-(inc:Incident)
              -[:IMPACTED]->(c:Customer)
        WHERE  inc.started_at >= $start AND inc.started_at <= $end
        RETURN inc, c
        """
        # Build representative Cypher string shown to users
        date_filter = ""
        if start_date or end_date:
            clauses = []
            if start_date:
                clauses.append(f"inc.started_at >= '{start_date}'")
            if end_date:
                clauses.append(f"inc.started_at <= '{end_date}'")
            date_filter = "\nWHERE  " + " AND ".join(clauses)
        cypher = (
            f"MATCH (svc:Service {{name: '{service_name}'}})"
            f"<-[:AFFECTED]-(inc:Incident)"
            f"-[:IMPACTED]->(c:Customer)"
            f"{date_filter}\n"
            f"RETURN svc, inc, c"
        )

        # Traverse
        service_node = self._find_node_by_label_property("Service", "name", service_name)
        if service_node is None:
            return []

        # Incidents that AFFECTED this service (in-edges from incidents)
        incidents = self.get_neighbors(service_node.node_id, "AFFECTED", direction="in")

        # Optionally filter by date range
        if start_date or end_date:
            incidents = _filter_nodes_by_date(incidents, start_date, end_date)

        evidence_list: list[Evidence] = []
        seen_customers: set[str] = set()
        for incident in incidents:
            customers = self.get_neighbors(incident.node_id, "IMPACTED", direction="out")
            for customer in customers:
                if customer.node_id in seen_customers:
                    continue
                seen_customers.add(customer.node_id)
                content = (
                    f"Customer '{customer.properties.get('name', customer.node_id)}' "
                    f"was impacted by incident "
                    f"'{incident.properties.get('incident_id', incident.node_id)}' "
                    f"({incident.properties.get('title', '')}) "
                    f"which affected service '{service_name}'."
                )
                evidence_list.append(
                    Evidence(
                        id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                        source_type="graph",
                        locator=f"{incident.node_id}->{customer.node_id}",
                        content=content,
                        score=1.0,
                        metadata={
                            "cypher": cypher,
                            "traversal": "impacted_customers",
                            "service": service_name,
                            "incident_id": incident.properties.get("incident_id"),
                            "customer_id": customer.properties.get("id"),
                            "customer_name": customer.properties.get("name"),
                        },
                    )
                )
        return evidence_list

    def traverse_owning_teams(self, service_name: str) -> list[Evidence]:
        """MATCH (svc:Service {name:$service})-[:OWNED_BY]->(t:Team)
        RETURN svc, t
        """
        cypher = (
            f"MATCH (svc:Service {{name: '{service_name}'}})-[:OWNED_BY]->(t:Team)\nRETURN svc, t"
        )

        service_node = self._find_node_by_label_property("Service", "name", service_name)
        if service_node is None:
            return []

        teams = self.get_neighbors(service_node.node_id, "OWNED_BY", direction="out")
        evidence_list: list[Evidence] = []
        for team in teams:
            content = (
                f"Service '{service_name}' is owned by team "
                f"'{team.properties.get('name', team.node_id)}'."
            )
            evidence_list.append(
                Evidence(
                    id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                    source_type="graph",
                    locator=f"{service_node.node_id}->{team.node_id}",
                    content=content,
                    score=1.0,
                    metadata={
                        "cypher": cypher,
                        "traversal": "owning_teams",
                        "service": service_name,
                        "team_id": team.properties.get("id"),
                        "team_name": team.properties.get("name"),
                    },
                )
            )
        return evidence_list

    def traverse_related_decisions(self, incident_id: str) -> list[Evidence]:
        """MATCH (d:Decision)-[:ADDRESSES]->(inc:Incident {incident_id:$id})
        RETURN d, inc
        """
        cypher = (
            f"MATCH (d:Decision)-[:ADDRESSES]->"
            f"(inc:Incident {{incident_id: '{incident_id}'}})\n"
            f"RETURN d, inc"
        )

        incident_node = self._find_node_by_label_property("Incident", "incident_id", incident_id)
        if incident_node is None:
            return []

        decisions = self.get_neighbors(incident_node.node_id, "ADDRESSES", direction="in")
        evidence_list: list[Evidence] = []
        for decision in decisions:
            content = (
                f"Decision '{decision.properties.get('adr_id', decision.node_id)}' "
                f"({decision.properties.get('title', '')}) "
                f"addresses incident '{incident_id}'."
            )
            evidence_list.append(
                Evidence(
                    id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                    source_type="graph",
                    locator=f"{decision.node_id}->{incident_node.node_id}",
                    content=content,
                    score=1.0,
                    metadata={
                        "cypher": cypher,
                        "traversal": "related_decisions",
                        "incident_id": incident_id,
                        "adr_id": decision.properties.get("adr_id"),
                        "decision_title": decision.properties.get("title"),
                        "decided_at": decision.properties.get("decided_at"),
                    },
                )
            )
        return evidence_list

    def execute_cypher_readonly(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Validate Cypher is read-only, then run a simple MATCH/RETURN pattern.

        The in-memory implementation supports a narrow subset of Cypher
        (node label + property equality filters) sufficient for analyst exploration.
        For full Cypher support, use the Neo4j adapter.
        """
        assert_readonly_cypher(cypher)
        return _execute_simple_match(self, cypher, params or {})

    def count_nodes(self) -> int:
        return len(self._nodes)

    def count_edges(self) -> int:
        return len(self._edges)

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()
        self._out.clear()
        self._in.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_node_by_label_property(
        self, label: str, prop_key: str, prop_value: Any
    ) -> GraphNode | None:
        for node in self._nodes.values():
            if node.label == label and node.properties.get(prop_key) == prop_value:
                return node
        return None

    def find_nodes_by_label(self, label: str) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.label == label]


# ---------------------------------------------------------------------------
# Simple MATCH interpreter for the in-memory adapter
# ---------------------------------------------------------------------------


def _execute_simple_match(
    store: MemoryGraphStore,
    cypher: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate a minimal MATCH (n:Label {prop: value}) RETURN n query."""
    # Pattern: MATCH (alias:Label {key: 'value'}) RETURN alias
    match_re = re.compile(
        r"MATCH\s+\((\w+):(\w+)(?:\s*\{([^}]*)\})?\)\s+RETURN",
        re.IGNORECASE,
    )
    m = match_re.search(cypher)
    if not m:
        # Fall back: return all nodes that match the RETURN clause label hint
        return [
            {"node_id": n.node_id, "label": n.label, **n.properties} for n in store._nodes.values()
        ]

    _alias, label, props_str = m.group(1), m.group(2), m.group(3) or ""
    # Parse simple key: 'value' or key: $param pairs
    prop_filter: dict[str, Any] = {}
    for kv in re.findall(r"(\w+)\s*:\s*(?:'([^']*)'|\$(\w+))", props_str):
        key, literal, param_name = kv
        value = params.get(param_name) if param_name else literal
        prop_filter[key] = value

    results = []
    for node in store._nodes.values():
        if node.label != label:
            continue
        if all(node.properties.get(k) == v for k, v in prop_filter.items()):
            results.append({"node_id": node.node_id, "label": node.label, **node.properties})
    return results


# ---------------------------------------------------------------------------
# Date filtering helper
# ---------------------------------------------------------------------------


def _filter_nodes_by_date(
    nodes: list[GraphNode],
    start_date: str | None,
    end_date: str | None,
) -> list[GraphNode]:
    filtered = []
    for node in nodes:
        started_at = node.properties.get("started_at")
        if not started_at:
            filtered.append(node)
            continue
        # Normalise to date string "YYYY-MM-DD"
        try:
            dt = datetime.fromisoformat(started_at)
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = str(started_at)[:10]

        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
        filtered.append(node)
    return filtered


# ---------------------------------------------------------------------------
# Neo4j adapter stub (P7-3 — full impl in neo4j_adapter.py)
# ---------------------------------------------------------------------------


def _make_neo4j_store() -> Any:
    """Instantiate the Neo4j adapter. Import is deferred to avoid hard dependency."""
    from rag.neo4j_adapter import Neo4jGraphStore  # noqa: PLC0415

    return Neo4jGraphStore()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_instance: GraphStoreService | None = None


def get_graph_store() -> GraphStoreService:
    """Return the singleton graph-store adapter, creating it on first call."""
    global _instance
    if _instance is None:
        _instance = _build_graph_store()
    return _instance


def reset_graph_store() -> None:
    """Reset singleton — used in tests to get a fresh empty store."""
    global _instance
    _instance = None


def _build_graph_store() -> GraphStoreService:
    from app.core.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    if settings.graph_store == "neo4j":
        return _make_neo4j_store()  # type: ignore[return-value]
    return MemoryGraphStore()


# ---------------------------------------------------------------------------
# Health check registration
# ---------------------------------------------------------------------------


def register_graph_store_check() -> None:
    """Register graph store readiness check.  Called once during lifespan."""
    from app.core.health import register_check  # noqa: PLC0415

    def _check() -> dict[str, str]:
        from app.core.config import get_settings as _gs  # noqa: PLC0415

        backend = _gs().graph_store
        try:
            store = get_graph_store()
            # For Neo4j, test connectivity explicitly
            if backend == "neo4j":
                from rag.neo4j_adapter import Neo4jGraphStore  # noqa: PLC0415

                if isinstance(store, Neo4jGraphStore) and not store.ping():
                    return {
                        "status": "degraded",
                        "detail": "neo4j unreachable — graph sub-questions will error",
                    }
            n_nodes = store.count_nodes()
            n_edges = store.count_edges()
            detail = f"{backend} ({n_nodes} nodes, {n_edges} edges)"
            return {"status": "ok", "detail": detail}
        except ConnectionError as exc:
            # Neo4j down → degraded (graph is non-critical; workflow continues)
            return {"status": "degraded", "detail": str(exc)}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    register_check("graph_store", _check)
