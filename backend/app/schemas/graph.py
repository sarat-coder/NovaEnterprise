"""Pydantic schemas for the knowledge graph API (P9-6)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNodeOut(BaseModel):
    node_id: str
    label: str
    properties: dict[str, Any]


class GraphEdgeOut(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    properties: dict[str, Any]


class GraphNeighborsOut(BaseModel):
    node: GraphNodeOut
    neighbors: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class CypherQueryIn(BaseModel):
    cypher: str
    params: dict[str, Any] = {}


class CypherQueryOut(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    cypher: str
