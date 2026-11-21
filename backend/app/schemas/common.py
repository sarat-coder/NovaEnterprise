from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Unified evidence shape returned by all three retrieval paths.

    source_type discriminates the locator semantics:
      - document: locator is a chunk_id (UUID string)
      - sql:      locator is a query_id (UUID string) pointing to a recorded query
      - graph:    locator is a traversal_id (UUID string) or Cypher expression label
    """

    id: str = Field(..., description="Unique evidence id used in [n] citation markers")
    source_type: Literal["document", "sql", "graph"]
    locator: str = Field(..., description="chunk_id | query_id | traversal_id")
    content: str = Field(..., description="Human-readable content fragment")
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
