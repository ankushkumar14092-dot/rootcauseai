"""RootCause AI — Model Context Protocol (MCP) Server.

Exposes FalkorDB-powered regression investigation tools, CI log ingestion,
blast radius graph algorithms, and isolated candidate validation to any
MCP-compliant AI agent client (Cursor, Claude Desktop, Antigravity IDE, etc.).
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server

from .agent import investigate, validate_candidate
from .graph import rows
from .ingester import ingest_ci_log, list_failures


mcp = MCPServer("RootCause AI - FalkorDB Graph Agent")


@mcp.tool()
def trace_failure_path(prompt: str = "Why did the test fail?", failure_id: str | None = None) -> str:
    """Trace a CI regression through FalkorDB multi-hop relationships.

    Traverses: Failure -> Test -> Function -> File <- Changed Commits.
    Ranks candidate causes and separates FACT from INFERENCE.
    """
    res = investigate(prompt=prompt, failure_id=failure_id or None)
    return json.dumps(res, indent=2)


@mcp.tool()
def ingest_ci_log(raw_log: str, repository: str = "checkout-service") -> str:
    """Parse raw GitHub Actions or Pytest console logs and ingest into FalkorDB graph.

    Extracts test runs, failure messages, line numbers, files, exercised functions, and commits.
    """
    res = ingest_ci_log(log_text=raw_log, repository=repository)
    return json.dumps(res, indent=2)


@mcp.tool()
def analyze_blast_radius(function_name: str = "validate_coupon") -> str:
    """Graph algorithm tool: compute blast radius and downstream dependency impact in FalkorDB.

    Calculates directly affected tests, sibling functions, related historical incidents,
    and returns a quantitative impact risk score.
    """
    query = """
    MATCH (fn:Function {name: $fn_name})
    OPTIONAL MATCH (t:Test)-[:EXERCISES]->(fn)
    OPTIONAL MATCH (fn)-[:DEFINED_IN]->(f:File)<-[:DEFINED_IN]-(sibling_fn:Function)
    OPTIONAL MATCH (sibling_test:Test)-[:EXERCISES]->(sibling_fn)
    OPTIONAL MATCH (c:Commit)-[:CHANGED]->(fn)
    OPTIONAL MATCH (inc:Incident)-[:RESOLVED_BY]->(c)
    RETURN fn.name AS function,
           collect(DISTINCT t.id) AS direct_tests,
           collect(DISTINCT sibling_fn.name) AS sibling_functions,
           collect(DISTINCT sibling_test.id) AS indirect_tests,
           collect(DISTINCT c.sha) AS related_commits,
           collect(DISTINCT inc.id) AS related_incidents
    """
    res = rows(query, {"fn_name": function_name})
    if not res:
        return json.dumps({"status": "not_found", "message": f"Function '{function_name}' not found in graph."})

    record = res[0]
    direct_tests = record.get("direct_tests") or []
    sibling_fns = record.get("sibling_functions") or []
    indirect_tests = record.get("indirect_tests") or []
    related_commits = record.get("related_commits") or []
    related_incidents = record.get("related_incidents") or []

    # Risk score based on graph connectivity
    risk_score = (len(direct_tests) * 4) + (len(indirect_tests) * 2) + len(sibling_fns) + (len(related_incidents) * 3)
    risk_level = "CRITICAL" if risk_score >= 12 else "HIGH" if risk_score >= 6 else "MODERATE"

    output = {
        "function": function_name,
        "impact_risk_level": risk_level,
        "connectivity_risk_score": risk_score,
        "direct_dependent_tests": direct_tests,
        "indirect_dependent_tests": indirect_tests,
        "sibling_functions": sibling_fns,
        "related_commits": related_commits,
        "historical_incidents": related_incidents,
        "recommendation": (
            f"Changes to {function_name} directly affect {len(direct_tests)} test(s) and {len(indirect_tests)} indirect test(s). "
            f"Pre-release boundary checks and isolated validation are strongly recommended."
        ),
    }
    return json.dumps(output, indent=2)


@mcp.tool()
def validate_candidate_fix(commit_sha: str = "a17c9e2") -> str:
    """Run an isolated sandbox verification subprocess for candidate regression fix.

    Safe, bounded execution in a temporary directory with no repository changes.
    """
    res = validate_candidate(commit_sha=commit_sha)
    return json.dumps(res, indent=2)


@mcp.tool()
def recall_memory(fingerprint: str = "checkout-expired-coupon") -> str:
    """Recall prior triage investigations and episodic agent memory from FalkorDB."""
    query = """
    MATCH (i:Investigation)
    WHERE i.fingerprint CONTAINS $fingerprint OR $fingerprint = ''
    OPTIONAL MATCH (i)-[:RECORDED]->(m:AgentMemory)
    RETURN i.id AS id, i.at AS at, i.summary AS summary,
           m.text AS memory, m.kind AS memory_kind
    ORDER BY i.at DESC LIMIT 5
    """
    memories = rows(query, {"fingerprint": fingerprint})
    return json.dumps({"fingerprint": fingerprint, "records": memories}, indent=2)


async def main():
    """Run the MCP server over standard I/O."""
    async with stdio_server() as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
