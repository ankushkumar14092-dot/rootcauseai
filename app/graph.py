"""FalkorDB connection and the fixed Cypher tools used by the investigator."""

from __future__ import annotations

import os
from typing import Any

from falkordb import FalkorDB


GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "rootcause")


class GraphUnavailable(RuntimeError):
    pass


def get_graph():
    try:
        client = FalkorDB(
            host=os.getenv("FALKORDB_HOST", "localhost"),
            port=int(os.getenv("FALKORDB_PORT", "6379")),
            username=os.getenv("FALKORDB_USERNAME") or None,
            password=os.getenv("FALKORDB_PASSWORD") or None,
        )
        return client.select_graph(GRAPH_NAME)
    except Exception as exc:  # surfaced as a helpful setup message by the API
        raise GraphUnavailable(str(exc)) from exc


def rows(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a read-only, application-authored Cypher query."""
    graph = get_graph()
    try:
        result = graph.ro_query(query, params or {})
    except TypeError:
        # Older client releases accept only the query string for ro_query.
        result = graph.ro_query(query)
    records = result.result_set
    headers = [
        col[1] if isinstance(col, (list, tuple)) and len(col) > 1 else str(col)
        for col in result.header
    ]
    return [dict(zip(headers, record)) for record in records]


def write(query: str, params: dict[str, Any] | None = None) -> None:
    graph = get_graph()
    graph.query(query, params or {})


def scalar(query: str) -> Any:
    result = rows(query)
    if not result:
        return None
    return next(iter(result[0].values()))
