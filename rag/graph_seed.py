"""Graph seeder — P7-4.

Loads all sample_data JSON files and populates the GraphStoreService with
≈85 nodes and ≈260 edges covering the required relationship types:
  (Incident)-[:AFFECTED]->(Service)
  (Incident)-[:IMPACTED]->(Customer)
  (Service)-[:OWNED_BY]->(Team)
  (Decision)-[:ADDRESSES]->(Incident)
  plus Employee, Project, Ticket nodes and their relationships.

Run via:  make seed-graph
         or directly:
         PYTHONPATH=backend python -m rag.graph_seed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


def _load(filename: str) -> list[dict]:
    path = SAMPLE_DATA / filename
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------


def seed_graph(store: object | None = None) -> dict[str, int]:
    """Seed the graph store with sample data.

    Parameters
    ----------
    store:
        A GraphStoreService instance.  When None the global singleton from
        get_graph_store() is used.

    Returns
    -------
    dict with keys "nodes" and "edges" showing the totals added.
    """
    if store is None:
        from rag.graph_store import get_graph_store  # noqa: PLC0415

        store = get_graph_store()

    from rag.graph_store import GraphNode  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Load raw data
    # ------------------------------------------------------------------
    teams = _load("teams.json")
    services = _load("services.json")
    customers = _load("customers.json")
    incidents = _load("incidents.json")
    decisions = _load("decisions.json")
    employees = _load("employees.json")
    projects = _load("projects.json")
    tickets = _load("tickets.json")

    # ------------------------------------------------------------------
    # Helper: add node and return node_id
    # ------------------------------------------------------------------

    def add(label: str, record: dict, id_key: str = "id") -> str:
        nid = f"{label.lower()}-{record[id_key]}"
        store.add_node(GraphNode(node_id=nid, label=label, properties=record))
        return nid

    def link(src: str, tgt: str, rel: str, props: dict | None = None) -> None:
        from rag.graph_store import GraphEdge as GE  # noqa: PLC0415

        store.add_edge(GE(source_id=src, target_id=tgt, relationship=rel, properties=props or {}))

    # ------------------------------------------------------------------
    # 1. NODES (85 total)
    # ------------------------------------------------------------------

    # Teams (6)
    team_ids = {t["id"]: add("Team", t) for t in teams}

    # Services (8)
    svc_ids = {s["id"]: add("Service", s) for s in services}

    # Customers (10)
    cust_ids = {c["id"]: add("Customer", c) for c in customers}

    # Incidents (12)
    inc_node_ids: dict[str, str] = {}
    for inc in incidents:
        nid = add("Incident", inc)
        inc_node_ids[inc["incident_id"]] = nid
        inc_node_ids[str(inc["id"])] = nid

    # Decisions (8)
    dec_node_ids: dict[str, str] = {}
    for dec in decisions:
        nid = add("Decision", dec)
        dec_node_ids[dec["adr_id"]] = nid

    # Employees (20)
    emp_ids = {e["id"]: add("Employee", e) for e in employees}

    # Projects (6)
    proj_ids = {p["id"]: add("Project", p) for p in projects}

    # Tickets (15)
    tick_ids = {t["id"]: add("Ticket", t) for t in tickets}

    # ------------------------------------------------------------------
    # 2. EDGES (~260 total)
    # ------------------------------------------------------------------

    # (1) Employee -[:MEMBER_OF]-> Team  (20 edges)
    for emp in employees:
        link(emp_ids[emp["id"]], team_ids[emp["team_id"]], "MEMBER_OF")

    # (2) Service -[:OWNED_BY]-> Team  (8 edges)
    for svc in services:
        link(svc_ids[svc["id"]], team_ids[svc["owner_team_id"]], "OWNED_BY")

    # (3) Incident -[:AFFECTED]-> Service  (12 edges)
    for inc in incidents:
        link(inc_node_ids[inc["incident_id"]], svc_ids[inc["service_id"]], "AFFECTED")

    # (4) Incident -[:IMPACTED]-> Customer  (46 edges total)
    for inc in incidents:
        for cust_id in inc.get("impacted_customer_ids", []):
            link(inc_node_ids[inc["incident_id"]], cust_ids[cust_id], "IMPACTED")

    # (5) Decision -[:ADDRESSES]-> Incident  (11 edges)
    for dec in decisions:
        for inc_id in dec.get("incident_ids", []):
            if inc_id in inc_node_ids:
                link(dec_node_ids[dec["adr_id"]], inc_node_ids[inc_id], "ADDRESSES")

    # (6) Project -[:OWNED_BY]-> Team  (6 edges)
    for proj in projects:
        link(proj_ids[proj["id"]], team_ids[proj["team_id"]], "OWNED_BY")

    # (7) Ticket -[:PART_OF]-> Project  (15 edges)
    for tick in tickets:
        link(tick_ids[tick["id"]], proj_ids[tick["project_id"]], "PART_OF")

    # (8) Ticket -[:ASSIGNED_TO]-> Employee  (15 edges)
    for tick in tickets:
        link(tick_ids[tick["id"]], emp_ids[tick["assignee_id"]], "ASSIGNED_TO")

    # (9) Customer -[:USES]-> Service  (~49 edges)
    # Assign based on customer segment: enterprise uses all 7 external-facing
    # services, mid-market uses 5, SMB uses 3.
    # External-facing services (excluding Data Pipeline which is internal):
    # 1=Payments, 2=Identity, 4=Analytics, 5=Notification, 6=Billing, 7=Portal, 8=Search
    ext_svc_enterprise = [1, 2, 4, 5, 6, 7, 8]  # all 7
    ext_svc_midmarket = [2, 4, 5, 7, 8]  # 5 services
    ext_svc_smb = [2, 7, 8]  # 3 services

    for cust in customers:
        if cust["segment"] == "enterprise":
            svcs = ext_svc_enterprise
        elif cust["segment"] == "mid-market":
            svcs = ext_svc_midmarket
        else:
            svcs = ext_svc_smb
        for svc_id in svcs:
            if svc_id in svc_ids:
                link(cust_ids[cust["id"]], svc_ids[svc_id], "USES")

    # (10) Service -[:DEPENDS_ON]-> Service  (4 edges — known dependencies)
    service_name_to_id = {s["name"]: s["id"] for s in services}
    _depends: list[tuple[str, str]] = [
        ("Billing Engine", "Payments API"),
        ("Analytics Dashboard", "Data Pipeline"),
        ("Customer Portal", "Identity Service"),
        ("Notification Service", "Identity Service"),
    ]
    for src_name, tgt_name in _depends:
        if src_name in service_name_to_id and tgt_name in service_name_to_id:
            link(
                svc_ids[service_name_to_id[src_name]],
                svc_ids[service_name_to_id[tgt_name]],
                "DEPENDS_ON",
            )

    # (11) Project -[:ADDRESSES]-> Decision  (7 edges)
    # Derived from project descriptions; mapping defined here explicitly.
    _proj_dec: list[tuple[int, str]] = [
        (1, "ADR-001"),
        (1, "ADR-002"),
        (2, "ADR-003"),
        (3, "ADR-005"),
        (4, "ADR-006"),
        (5, "ADR-008"),
        (6, "ADR-007"),
    ]
    for proj_id, adr_id in _proj_dec:
        if proj_id in proj_ids and adr_id in dec_node_ids:
            link(proj_ids[proj_id], dec_node_ids[adr_id], "ADDRESSES")

    # (12) Incident -[:INVESTIGATED_BY]-> Team  (12 edges — via service owner)
    svc_owner: dict[int, int] = {s["id"]: s["owner_team_id"] for s in services}
    for inc in incidents:
        owner_team = svc_owner.get(inc["service_id"])
        if owner_team and owner_team in team_ids:
            link(inc_node_ids[inc["incident_id"]], team_ids[owner_team], "INVESTIGATED_BY")

    # (13) Decision -[:APPLIES_TO]-> Service  (10 edges)
    # Map each ADR to the primary service it addresses.
    _dec_svc: list[tuple[str, str]] = [
        ("ADR-001", "Payments API"),
        ("ADR-002", "Payments API"),
        ("ADR-003", "Billing Engine"),
        ("ADR-004", "Payments API"),  # network policy incident affected Payments API
        ("ADR-005", "Identity Service"),
        ("ADR-006", "Data Pipeline"),
        ("ADR-007", "Payments API"),
        ("ADR-007", "Identity Service"),
        ("ADR-007", "Billing Engine"),
        ("ADR-008", "Notification Service"),
    ]
    for adr_id, svc_name in _dec_svc:
        svc_node_id = svc_ids.get(service_name_to_id.get(svc_name, -1))
        if adr_id in dec_node_ids and svc_node_id:
            link(dec_node_ids[adr_id], svc_node_id, "APPLIES_TO")

    # (14) Employee -[:WORKS_ON]-> Project  (15 edges — unique assignee-per-project)
    seen_emp_proj: set[tuple[int, int]] = set()
    for tick in tickets:
        key = (tick["assignee_id"], tick["project_id"])
        if key not in seen_emp_proj:
            seen_emp_proj.add(key)
            link(emp_ids[tick["assignee_id"]], proj_ids[tick["project_id"]], "WORKS_ON")

    # (15) Team -[:COORDINATES_WITH]-> Team  (4 edges — cross-team partnerships)
    _coords: list[tuple[str, str]] = [
        ("Payments Platform", "SRE"),
        ("Identity", "SRE"),
        ("Data Platform", "Analytics"),
        ("Customer Success", "SRE"),
    ]
    team_name_to_id = {t["name"]: t["id"] for t in teams}
    for t1_name, t2_name in _coords:
        if t1_name in team_name_to_id and t2_name in team_name_to_id:
            link(
                team_ids[team_name_to_id[t1_name]],
                team_ids[team_name_to_id[t2_name]],
                "COORDINATES_WITH",
            )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    n_nodes = store.count_nodes()
    n_edges = store.count_edges()
    return {"nodes": n_nodes, "edges": n_edges}


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    import os  # noqa: PLC0415

    # Ensure the backend package is importable
    root = Path(__file__).parent.parent
    backend_path = str(root / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    os.environ.setdefault("GRAPH_STORE", "memory")
    os.environ.setdefault("LLM_PROVIDER", "fake")
    os.environ.setdefault("VECTOR_STORE", "memory")
    os.environ.setdefault("DATABASE_URL", "sqlite:///data/enterprise.db")

    from rag.graph_store import get_graph_store, reset_graph_store  # noqa: PLC0415

    reset_graph_store()
    store = get_graph_store()
    result = seed_graph(store)
    print(f"Graph seeded: {result['nodes']} nodes, {result['edges']} edges")


if __name__ == "__main__":
    main()
