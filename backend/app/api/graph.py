"""Knowledge graph API — browse and expand nodes (P9-6).

F14: Browse the knowledge graph and expand nodes.

Endpoints:
  GET  /api/v1/graph/nodes           viewer+   list nodes (optionally filter by label)
  GET  /api/v1/graph/nodes/{id}      viewer+   get a node
  GET  /api/v1/graph/nodes/{id}/neighbors  viewer+  expand a node
  POST /api/v1/graph/cypher          analyst+  run read-only Cypher
  GET  /api/v1/graph/stats           viewer+   node + edge counts
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import Role, UserContext, require_role
from app.schemas.graph import (
    CypherQueryIn,
    CypherQueryOut,
    GraphEdgeOut,
    GraphNeighborsOut,
    GraphNodeOut,
)

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


def _graph_store():
    from rag.graph_store import get_graph_store  # noqa: PLC0415

    return get_graph_store()


def _node_to_out(node) -> GraphNodeOut:
    return GraphNodeOut(
        node_id=node.node_id,
        label=node.label,
        properties=node.properties,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats")
def graph_stats(
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
) -> dict:
    store = _graph_store()
    return {
        "node_count": store.count_nodes(),
        "edge_count": store.count_edges(),
    }


@router.get("/nodes", response_model=list[GraphNodeOut])
def list_nodes(
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
    label: str | None = Query(default=None, description="Filter by node label"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[GraphNodeOut]:
    """List graph nodes, optionally filtered by label."""
    store = _graph_store()

    if hasattr(store, "find_nodes_by_label") and label:
        nodes = store.find_nodes_by_label(label)
    elif hasattr(store, "_nodes"):
        nodes = list(store._nodes.values())
        if label:
            nodes = [n for n in nodes if n.label == label]
    else:
        nodes = []

    return [_node_to_out(n) for n in nodes[:limit]]


@router.get("/nodes/{node_id}", response_model=GraphNodeOut)
def get_node(
    node_id: str,
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
) -> GraphNodeOut:
    store = _graph_store()
    node = store.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return _node_to_out(node)


@router.get("/nodes/{node_id}/neighbors", response_model=GraphNeighborsOut)
def get_neighbors(
    node_id: str,
    _user: Annotated[UserContext, Depends(require_role(Role.VIEWER))],
    relationship: str | None = Query(default=None),
    direction: str = Query(default="out", pattern="^(out|in|both)$"),
) -> GraphNeighborsOut:
    """Expand a node — return its direct neighbours and the connecting edges."""
    store = _graph_store()
    node = store.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    if direction == "both":
        out_neighbors = store.get_neighbors(node_id, relationship=relationship, direction="out")
        in_neighbors = store.get_neighbors(node_id, relationship=relationship, direction="in")
        all_neighbors = {n.node_id: n for n in out_neighbors + in_neighbors}
        neighbor_list = list(all_neighbors.values())
    else:
        neighbor_list = store.get_neighbors(node_id, relationship=relationship, direction=direction)

    # Collect relevant edges
    edges: list[GraphEdgeOut] = []
    if hasattr(store, "_edges") and hasattr(store, "_out") and hasattr(store, "_in"):
        neighbor_ids = {n.node_id for n in neighbor_list}
        for edge in store._edges:
            out_match = (
                direction in ("out", "both")
                and edge.source_id == node_id
                and edge.target_id in neighbor_ids
            )
            in_match = (
                direction in ("in", "both")
                and edge.target_id == node_id
                and edge.source_id in neighbor_ids
            )
            relevant = out_match or in_match
            if relevant and (relationship is None or edge.relationship == relationship):
                edges.append(
                    GraphEdgeOut(
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        relationship=edge.relationship,
                        properties=edge.properties,
                    )
                )

    return GraphNeighborsOut(
        node=_node_to_out(node),
        neighbors=[_node_to_out(n) for n in neighbor_list],
        edges=edges,
    )


@router.post("/cypher", response_model=CypherQueryOut)
def run_cypher(
    body: CypherQueryIn,
    _user: Annotated[UserContext, Depends(require_role(Role.ANALYST))],
) -> CypherQueryOut:
    """Execute a read-only Cypher query.

    Only MATCH / RETURN / WHERE / WITH / ORDER BY / LIMIT / SKIP are allowed.
    Write clauses raise 422.
    """
    store = _graph_store()
    try:
        rows = store.execute_cypher_readonly(body.cypher, body.params)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cypher execution error: {exc}",
        ) from exc

    return CypherQueryOut(rows=rows, row_count=len(rows), cypher=body.cypher)
