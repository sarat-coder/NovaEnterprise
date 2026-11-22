"""Entity and relationship extraction from document chunks (P9-1).

Design:
- Pattern-based extraction works without an LLM and passes make test offline.
- Extracted entities and relationships are added to the graph store.
- Each entity type maps to a GraphNode label; each link maps to a GraphEdge.

Extracted entity types: Incident, Service, Team, Customer, Decision.
Extracted relationships: AFFECTED, IMPACTED, OWNED_BY, ADDRESSES.

The extractor is intentionally conservative — false negatives are preferable to
false positives. The graph seeder (rag/graph_seed.py) populates the structured
data; this extractor enriches it from free-form document text.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from rag.graph_store import GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """Nodes and edges extracted from a single document chunk."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    entity_mentions: dict[str, list[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Patterns for each entity type
# ---------------------------------------------------------------------------

# Incident IDs: INC-NNNN or INC-NNNN-words
_INCIDENT_ID_RE = re.compile(r"\bINC-\d{4}(?:-\w+)*\b", re.IGNORECASE)

# Service names (from canonical list)
_SERVICE_NAMES = [
    "Payments API",
    "Identity Service",
    "Data Pipeline",
    "Analytics Dashboard",
    "Notification Service",
    "Billing Engine",
    "Customer Portal",
    "Search Service",
]
_SERVICE_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _SERVICE_NAMES) + r")\b",
    re.IGNORECASE,
)

# Team names (from canonical list)
_TEAM_NAMES = [
    "Payments Platform",
    "Identity",
    "Data Platform",
    "Customer Success",
    "SRE",
    "Analytics",
]
_TEAM_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _TEAM_NAMES) + r")\s+[Tt]eam\b",
    re.IGNORECASE,
)

# ADR IDs: ADR-NNN
_ADR_ID_RE = re.compile(r"\bADR-\d{3,4}\b", re.IGNORECASE)

# Decision keywords near ADR references
_DECISION_CONTEXT_RE = re.compile(
    r"(decision|ADR|architecture decision|we decided|chosen approach)",
    re.IGNORECASE,
)

# "owned by" / "responsible team" / "on-call" links
_OWNED_BY_RE = re.compile(
    r"(?:owned by|maintained by|responsible team[:\s]+|on[- ]call[:\s]+)"
    r"([A-Z][a-zA-Z\s]+(?:Team|Platform|SRE|Analytics|Identity))",
    re.IGNORECASE,
)

# "impacted N customers" / "affected: CustomerName"
_IMPACT_RE = re.compile(
    r"(?:impacted|affected|disrupted)[^.]*?customer",
    re.IGNORECASE,
)

# "addresses INC-NNNN" / "resolves INC-NNNN"
_ADDRESSES_RE = re.compile(
    r"(?:addresses|resolves|mitigates|related to)\s+(INC-\d{4}(?:-\w+)*)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(text: str, doc_id: str) -> ExtractionResult:
    """Extract entities and relationships from free-form document text.

    Returns an ExtractionResult with GraphNode and GraphEdge objects ready to
    be added to the graph store.  Node ids are stable UUIDs derived from the
    entity canonical identifier so repeated ingestion is idempotent.
    """
    result = ExtractionResult()

    incident_ids = _extract_incidents(text, result)
    service_names = _extract_services(text, result)
    _extract_teams(text, result)
    adr_ids = _extract_decisions(text, result)

    # Relationships -------------------------------------------------------
    _extract_affected_links(text, incident_ids, service_names, result)
    _extract_addresses_links(text, adr_ids, result)
    _extract_ownership_links(text, service_names, result)

    return result


# ---------------------------------------------------------------------------
# Entity extractors
# ---------------------------------------------------------------------------


def _extract_incidents(text: str, result: ExtractionResult) -> list[str]:
    ids = list({m.upper() for m in _INCIDENT_ID_RE.findall(text)})
    for inc_id in ids:
        node_id = _stable_node_id("Incident", inc_id)
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                label="Incident",
                properties={"incident_id": inc_id, "source": "extracted"},
            )
        )
    result.entity_mentions["Incident"] = ids
    return ids


def _extract_services(text: str, result: ExtractionResult) -> list[str]:
    names = list({m.lower().title() for m in _SERVICE_RE.findall(text)})
    # Normalise to canonical capitalisation
    canonical: dict[str, str] = {s.lower(): s for s in _SERVICE_NAMES}
    names = [canonical.get(n.lower(), n) for n in names]
    names = list(set(names))
    for name in names:
        node_id = _stable_node_id("Service", name)
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                label="Service",
                properties={"name": name, "source": "extracted"},
            )
        )
    result.entity_mentions["Service"] = names
    return names


def _extract_teams(text: str, result: ExtractionResult) -> list[str]:
    raw = _TEAM_RE.findall(text)
    names = list({r.strip() for r in raw})
    canonical: dict[str, str] = {t.lower(): t for t in _TEAM_NAMES}
    names = [canonical.get(n.lower(), n) for n in names]
    names = list(set(names))
    for name in names:
        node_id = _stable_node_id("Team", name)
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                label="Team",
                properties={"name": name, "source": "extracted"},
            )
        )
    result.entity_mentions["Team"] = names
    return names


def _extract_decisions(text: str, result: ExtractionResult) -> list[str]:
    ids = list({m.upper() for m in _ADR_ID_RE.findall(text)})
    for adr_id in ids:
        node_id = _stable_node_id("Decision", adr_id)
        result.nodes.append(
            GraphNode(
                node_id=node_id,
                label="Decision",
                properties={"adr_id": adr_id, "source": "extracted"},
            )
        )
    result.entity_mentions["Decision"] = ids
    return ids


# ---------------------------------------------------------------------------
# Relationship extractors
# ---------------------------------------------------------------------------


def _extract_affected_links(
    text: str,
    incident_ids: list[str],
    service_names: list[str],
    result: ExtractionResult,
) -> None:
    """Add (Incident)-[:AFFECTED]->(Service) edges when both appear near each other."""
    if not incident_ids or not service_names:
        return
    sentences = re.split(r"[.!?\n]", text)
    for sent in sentences:
        inc_found = [i for i in incident_ids if i.lower() in sent.lower()]
        svc_found = [s for s in service_names if s.lower() in sent.lower()]
        for inc in inc_found:
            for svc in svc_found:
                result.edges.append(
                    GraphEdge(
                        source_id=_stable_node_id("Incident", inc),
                        target_id=_stable_node_id("Service", svc),
                        relationship="AFFECTED",
                        properties={"source": "extracted"},
                    )
                )


def _extract_addresses_links(text: str, adr_ids: list[str], result: ExtractionResult) -> None:
    """Add (Decision)-[:ADDRESSES]->(Incident) edges from 'addresses INC-NNNN' patterns."""
    for m in _ADDRESSES_RE.finditer(text):
        inc_id = m.group(1).upper()
        # Find the nearest ADR mention before this point
        pos = m.start()
        preceding = text[:pos]
        adr_matches = list(_ADR_ID_RE.finditer(preceding))
        if adr_matches:
            adr_id = adr_matches[-1].group(0).upper()
        elif adr_ids:
            adr_id = adr_ids[0]
        else:
            continue
        # Ensure incident node exists
        inc_node_id = _stable_node_id("Incident", inc_id)
        if not any(n.node_id == inc_node_id for n in result.nodes):
            result.nodes.append(
                GraphNode(
                    node_id=inc_node_id,
                    label="Incident",
                    properties={"incident_id": inc_id, "source": "extracted"},
                )
            )
        result.edges.append(
            GraphEdge(
                source_id=_stable_node_id("Decision", adr_id),
                target_id=inc_node_id,
                relationship="ADDRESSES",
                properties={"source": "extracted"},
            )
        )


def _extract_ownership_links(text: str, service_names: list[str], result: ExtractionResult) -> None:
    """Add (Service)-[:OWNED_BY]->(Team) edges from ownership patterns."""
    canonical_teams: dict[str, str] = {t.lower(): t for t in _TEAM_NAMES}
    sentences = re.split(r"[.!?\n]", text)
    for sent in sentences:
        m = _OWNED_BY_RE.search(sent)
        if not m:
            continue
        team_raw = m.group(1).strip()
        team_name = canonical_teams.get(team_raw.lower())
        if not team_name:
            # Try partial match
            for key, val in canonical_teams.items():
                if key in team_raw.lower():
                    team_name = val
                    break
        if not team_name:
            continue
        svc_found = [s for s in service_names if s.lower() in sent.lower()]
        for svc in svc_found:
            result.edges.append(
                GraphEdge(
                    source_id=_stable_node_id("Service", svc),
                    target_id=_stable_node_id("Team", team_name),
                    relationship="OWNED_BY",
                    properties={"source": "extracted"},
                )
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_node_id(label: str, identifier: str) -> str:
    """Derive a stable UUID from (label, identifier) so re-runs are idempotent."""
    import hashlib  # noqa: PLC0415

    h = hashlib.sha256(f"{label}:{identifier}".encode()).hexdigest()
    return str(uuid.UUID(h[:32]))
