"""Neo4j adapter for GraphStoreService (P7-3).

Selected when GRAPH_STORE=neo4j.  Requires neo4j Python driver (optional dep).
If Neo4j is unreachable, every method raises ConnectionError; the health check
reports "degraded" and /health/ready returns status "degraded" for the
graph_store check — the workflow continues and records an error on graph
sub-questions rather than crashing.

Read-only Cypher enforcement: assert_readonly_cypher() from graph_store.py
is applied before every user-supplied query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rag.graph_store import (
    GraphEdge,
    GraphNode,
    assert_readonly_cypher,
)

if TYPE_CHECKING:
    from app.schemas.common import Evidence


class Neo4jGraphStore:
    """GraphStoreService adapter backed by Neo4j.

    Lazy connection: the driver is only opened on first use so that
    import at startup does not fail when Neo4j is not running.
    """

    def __init__(self) -> None:
        self._driver: Any = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> Any:
        """Open the Neo4j driver.  Raises ConnectionError if unavailable."""
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import GraphDatabase  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError as exc:
            raise ConnectionError(
                "neo4j Python driver is not installed. Add it with: uv add neo4j"
            ) from exc

        from app.core.config import get_settings  # noqa: PLC0415

        s = get_settings()
        if not s.neo4j_uri:
            raise ConnectionError(
                "NEO4J_URI is not set. Set it in .env or use GRAPH_STORE=memory for the demo."
            )
        try:
            driver = GraphDatabase.driver(
                s.neo4j_uri,
                auth=(s.neo4j_user, s.neo4j_password),
            )
            driver.verify_connectivity()
            self._driver = driver
            return driver
        except Exception as exc:
            raise ConnectionError(f"Cannot connect to Neo4j at {s.neo4j_uri}: {exc}") from exc

    def _session(self) -> Any:
        return self._connect().session()

    # ------------------------------------------------------------------
    # GraphStoreService implementation
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> None:
        props = {**node.properties, "node_id": node.node_id}
        with self._session() as session:
            session.run(
                f"MERGE (n:{node.label} {{node_id: $node_id}}) SET n += $props",
                node_id=node.node_id,
                props=props,
            )

    def add_edge(self, edge: GraphEdge) -> None:
        with self._session() as session:
            session.run(
                f"""
                MATCH (a {{node_id: $source_id}})
                MATCH (b {{node_id: $target_id}})
                MERGE (a)-[r:{edge.relationship}]->(b)
                SET r += $props
                """,
                source_id=edge.source_id,
                target_id=edge.target_id,
                props=edge.properties,
            )

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._session() as session:
            result = session.run(
                "MATCH (n {node_id: $node_id}) RETURN n LIMIT 1",
                node_id=node_id,
            )
            record = result.single()
            if record is None:
                return None
            n = record["n"]
            labels = list(n.labels)
            label = labels[0] if labels else "Unknown"
            props = dict(n)
            props.pop("node_id", None)
            return GraphNode(node_id=node_id, label=label, properties=props)

    def get_neighbors(
        self,
        node_id: str,
        relationship: str | None = None,
        direction: str = "out",
    ) -> list[GraphNode]:
        if direction == "out":
            if relationship:
                cypher = f"MATCH (a {{node_id: $nid}})-[:{relationship}]->(b) RETURN b"
            else:
                cypher = "MATCH (a {node_id: $nid})-->(b) RETURN b"
        else:
            if relationship:
                cypher = f"MATCH (a {{node_id: $nid}})<-[:{relationship}]-(b) RETURN b"
            else:
                cypher = "MATCH (a {node_id: $nid})<--(b) RETURN b"

        nodes = []
        with self._session() as session:
            result = session.run(cypher, nid=node_id)
            for record in result:
                n = record["b"]
                labels = list(n.labels)
                label = labels[0] if labels else "Unknown"
                nid = n.get("node_id", str(n.id))
                props = {k: v for k, v in n.items() if k != "node_id"}
                nodes.append(GraphNode(node_id=nid, label=label, properties=props))
        return nodes

    def traverse_impacted_customers(
        self,
        service_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Evidence]:
        import uuid  # noqa: PLC0415

        from app.schemas.common import Evidence as Ev  # noqa: PLC0415

        date_filter = ""
        params: dict[str, Any] = {"service_name": service_name}
        if start_date:
            date_filter += " AND inc.started_at >= $start_date"
            params["start_date"] = start_date
        if end_date:
            date_filter += " AND inc.started_at <= $end_date"
            params["end_date"] = end_date

        cypher = (
            f"MATCH (svc:Service {{name: $service_name}})"
            f"<-[:AFFECTED]-(inc:Incident)"
            f"-[:IMPACTED]->(c:Customer)"
            f"\nWHERE 1=1{date_filter}"
            f"\nRETURN svc, inc, c"
        )

        evidence_list: list[Evidence] = []
        seen: set[str] = set()
        with self._session() as session:
            result = session.run(cypher, **params)
            for record in result:
                inc = dict(record["inc"])
                cust = dict(record["c"])
                key = f"{inc.get('incident_id')}-{cust.get('id')}"
                if key in seen:
                    continue
                seen.add(key)
                content = (
                    f"Customer '{cust.get('name')}' was impacted by incident "
                    f"'{inc.get('incident_id')}' ({inc.get('title')}) "
                    f"which affected service '{service_name}'."
                )
                evidence_list.append(
                    Ev(
                        id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                        source_type="graph",
                        locator=f"{inc.get('incident_id')}->{cust.get('id')}",
                        content=content,
                        score=1.0,
                        metadata={
                            "cypher": cypher,
                            "traversal": "impacted_customers",
                            "service": service_name,
                            "incident_id": inc.get("incident_id"),
                            "customer_id": cust.get("id"),
                            "customer_name": cust.get("name"),
                        },
                    )
                )
        return evidence_list

    def traverse_owning_teams(self, service_name: str) -> list[Evidence]:
        import uuid  # noqa: PLC0415

        from app.schemas.common import Evidence as Ev  # noqa: PLC0415

        cypher = "MATCH (svc:Service {name: $service_name})-[:OWNED_BY]->(t:Team)\nRETURN svc, t"
        evidence_list: list[Evidence] = []
        with self._session() as session:
            result = session.run(cypher, service_name=service_name)
            for record in result:
                svc = dict(record["svc"])
                team = dict(record["t"])
                content = f"Service '{service_name}' is owned by team '{team.get('name')}'."
                evidence_list.append(
                    Ev(
                        id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                        source_type="graph",
                        locator=f"{svc.get('node_id')}->{team.get('node_id')}",
                        content=content,
                        score=1.0,
                        metadata={
                            "cypher": cypher,
                            "traversal": "owning_teams",
                            "service": service_name,
                            "team_id": team.get("id"),
                            "team_name": team.get("name"),
                        },
                    )
                )
        return evidence_list

    def traverse_related_decisions(self, incident_id: str) -> list[Evidence]:
        import uuid  # noqa: PLC0415

        from app.schemas.common import Evidence as Ev  # noqa: PLC0415

        cypher = (
            "MATCH (d:Decision)-[:ADDRESSES]->"
            "(inc:Incident {incident_id: $incident_id})\n"
            "RETURN d, inc"
        )
        evidence_list: list[Evidence] = []
        with self._session() as session:
            result = session.run(cypher, incident_id=incident_id)
            for record in result:
                d = dict(record["d"])
                content = (
                    f"Decision '{d.get('adr_id')}' ({d.get('title')}) "
                    f"addresses incident '{incident_id}'."
                )
                evidence_list.append(
                    Ev(
                        id=f"ev-graph-{uuid.uuid4().hex[:8]}",
                        source_type="graph",
                        locator=f"{d.get('node_id')}->{incident_id}",
                        content=content,
                        score=1.0,
                        metadata={
                            "cypher": cypher,
                            "traversal": "related_decisions",
                            "incident_id": incident_id,
                            "adr_id": d.get("adr_id"),
                            "decision_title": d.get("title"),
                            "decided_at": d.get("decided_at"),
                        },
                    )
                )
        return evidence_list

    def execute_cypher_readonly(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        assert_readonly_cypher(cypher)
        results = []
        with self._session() as session:
            result = session.run(cypher, **(params or {}))
            for record in result:
                results.append(dict(record))
        return results

    def count_nodes(self) -> int:
        with self._session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS cnt")
            record = result.single()
            return int(record["cnt"]) if record else 0

    def count_edges(self) -> int:
        with self._session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            record = result.single()
            return int(record["cnt"]) if record else 0

    def clear(self) -> None:
        with self._session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    # ------------------------------------------------------------------
    # Degraded health check helper
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Return True if Neo4j is reachable, False otherwise."""
        try:
            self._connect()
            return True
        except Exception:
            return False
