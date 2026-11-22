"""MCP server exposing NovaEnterprise read-only tools (P15-5).

This server wraps the platform's retrieval capabilities as Model Context
Protocol tools so external AI agents can query documents, graph, and
structured data without direct database access.

All tools are READ-ONLY by design:
  - No SQL writes (enforced by validate_sql)
  - No graph writes (enforced by read-only Cypher check)
  - No document mutations (upload / delete not exposed)

Usage (stdio transport, the default):
    uv run python -m integrations.mcp_server

Usage (SSE transport for remote agents):
    uv run python -m integrations.mcp_server --transport sse --port 8002

Environment variables are read from the same .env as the main backend.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge",
        "description": (
            "Search the company's knowledge base using a natural language query. "
            "Returns relevant document chunks with relevance scores. "
            "Use this for policy questions, postmortems, ADRs, and meeting notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_graph",
        "description": (
            "Traverse the enterprise knowledge graph. "
            "Supports typed traversals: 'impacted_customers', 'owning_teams', "
            "'related_decisions', 'affected_services'. "
            "Returns nodes, edges, and the Cypher query that was executed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "traversal_type": {
                    "type": "string",
                    "enum": [
                        "impacted_customers",
                        "owning_teams",
                        "related_decisions",
                        "affected_services",
                    ],
                    "description": "The typed traversal to run",
                },
                "entity_id": {
                    "type": "string",
                    "description": "Starting entity node id (e.g. 'payments-api', 'inc-2031')",
                },
            },
            "required": ["traversal_type", "entity_id"],
        },
    },
    {
        "name": "run_sql_query",
        "description": (
            "Run a read-only SQL query against the enterprise database. "
            "Only SELECT statements against the allowlisted tables are permitted. "
            "Allowlisted tables: incidents, services, customers, decisions, teams, "
            "employees, projects, tickets, documents, research_sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A read-only SELECT statement",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "list_incidents",
        "description": "List recent incidents, optionally filtered by service name or date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Filter by service name (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "list_customers",
        "description": "List enterprise customers, optionally filtered by segment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "segment": {
                    "type": "string",
                    "enum": ["enterprise", "mid-market", "smb"],
                    "description": "Customer segment filter (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "get_research_session",
        "description": (
            "Retrieve the result of a completed research session by its session id. "
            "Returns the question, cited answer, evidence list, and strategies used."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "UUID of the research session",
                },
            },
            "required": ["session_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _handle_search_knowledge(args: dict[str, Any]) -> dict[str, Any]:
    from rag.retriever import HybridRetriever

    retriever = HybridRetriever()
    results = retriever.retrieve(query=args["query"], top_k=args.get("top_k", 5))
    return {
        "results": [
            {
                "id": e.id,
                "content": e.content,
                "score": e.score,
                "source_type": e.source_type,
                "locator": e.locator,
            }
            for e in results
        ]
    }


def _handle_query_graph(args: dict[str, Any]) -> dict[str, Any]:
    from rag.graph_store import get_graph_store

    store = get_graph_store()
    traversal = args["traversal_type"]
    entity_id = args["entity_id"]

    method = getattr(store, traversal, None)
    if method is None:
        return {"error": f"Traversal '{traversal}' not supported by this graph store"}

    try:
        results = method(entity_id)
        return {"results": results if isinstance(results, list) else [results]}
    except Exception as exc:
        return {"error": str(exc)}


def _handle_run_sql_query(args: dict[str, Any]) -> dict[str, Any]:
    from rag.sql_retrieval import SqlRetriever

    retriever = SqlRetriever()
    try:
        evidence = retriever.execute_raw(args["sql"])
        return {"results": [{"content": e.content, "locator": e.locator} for e in evidence]}
    except ValueError as exc:
        return {"error": str(exc)}


def _handle_list_incidents(args: dict[str, Any]) -> dict[str, Any]:
    from app.core.db import get_session_factory
    from app.repositories.incidents import IncidentRepository

    factory = get_session_factory()
    with factory() as session:
        repo = IncidentRepository(session)
        incidents = repo.list(limit=args.get("limit", 20))
        service_filter = args.get("service_name", "").lower()
        if service_filter:
            incidents = [i for i in incidents if service_filter in (i.service_name or "").lower()]
        return {
            "incidents": [
                {
                    "id": str(i.id),
                    "title": i.title,
                    "severity": i.severity,
                    "service_name": i.service_name,
                    "status": i.status,
                    "occurred_at": str(i.occurred_at),
                }
                for i in incidents
            ]
        }


def _handle_list_customers(args: dict[str, Any]) -> dict[str, Any]:
    from app.core.db import get_session_factory
    from app.repositories.customers import CustomerRepository

    factory = get_session_factory()
    with factory() as session:
        repo = CustomerRepository(session)
        customers = repo.list(limit=args.get("limit", 20))
        segment_filter = args.get("segment", "").lower()
        if segment_filter:
            customers = [c for c in customers if (c.segment or "").lower() == segment_filter]
        return {
            "customers": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "segment": c.segment,
                    "industry": c.industry,
                }
                for c in customers
            ]
        }


def _handle_get_research_session(args: dict[str, Any]) -> dict[str, Any]:
    from app.core.db import get_session_factory
    from app.repositories.research import ResearchRepository

    factory = get_session_factory()
    with factory() as session:
        repo = ResearchRepository(session)
        s = repo.get(args["session_id"])
        if s is None:
            return {"error": "Session not found"}
        return {
            "session_id": str(s.id),
            "question": s.question,
            "status": s.status,
            "answer": s.answer,
            "citations_valid": s.citations_valid,
            "strategies_used": s.strategies_used or [],
        }


TOOL_HANDLERS = {
    "search_knowledge": _handle_search_knowledge,
    "query_graph": _handle_query_graph,
    "run_sql_query": _handle_run_sql_query,
    "list_incidents": _handle_list_incidents,
    "list_customers": _handle_list_customers,
    "get_research_session": _handle_get_research_session,
}

# ---------------------------------------------------------------------------
# MCP protocol (stdio transport)
# ---------------------------------------------------------------------------


def _send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method", "")
    msg_id = message.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "nova-enterprise-mcp",
                    "version": "0.1.0",
                },
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = message.get("params", {})
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }

        try:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": "error" in result,
                },
            }
        except Exception as exc:
            logger.exception("Tool %s raised an error", tool_name)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                    "isError": True,
                },
            }

    if method == "notifications/initialized":
        return None  # notification — no response

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def run_stdio() -> None:
    """Run the MCP server over stdio (the default transport)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle_message(message)
        if response is not None:
            _send(response)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NovaEnterprise MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)

    if args.transport == "stdio":
        run_stdio()
