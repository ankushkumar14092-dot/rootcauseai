from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import investigate, seed_demo, validate_candidate
from .graph import GraphUnavailable, rows, scalar
from .ingester import ingest_ci_log, list_failures
from .sample_logs import SAMPLE_LOGS


ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="RootCause AI", version="0.2.0")
app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")


class InvestigationRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=500)
    failure_id: str | None = Field(default=None, max_length=100)


class ValidationRequest(BaseModel):
    commit_sha: str = Field(pattern=r"^[0-9a-f]{7,40}$")


class IngestLogRequest(BaseModel):
    raw_log: str = Field(min_length=10)
    repository: str | None = Field(default=None, max_length=100)


def graph_error(exc: GraphUnavailable) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="FalkorDB is not reachable. Start it with `docker compose up -d falkordb`, then retry.",
    )


@app.get("/")
def home():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/status")
def status():
    try:
        count = scalar("MATCH (n) RETURN count(n) AS count")
        failures_count = scalar("MATCH (f:Failure) RETURN count(f) AS count") or 0
        return {"ok": True, "graph": "rootcause", "nodes": count or 0, "failures": failures_count}
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="FalkorDB is not reachable or the graph query failed.") from exc


@app.post("/api/seed")
def seed():
    try:
        return {"ok": True, **seed_demo()}
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc


@app.get("/api/sample-logs")
def get_sample_logs():
    return {
        "ok": True,
        "samples": [
            {
                "id": k,
                "title": v["title"],
                "repository": v["repository"],
                "branch": v["branch"],
                "workflow": v["workflow"],
                "log": v["log"],
            }
            for k, v in SAMPLE_LOGS.items()
        ],
    }


@app.get("/api/failures")
def get_failures():
    try:
        failures = list_failures()
        return {"ok": True, "failures": failures}
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc


@app.post("/api/ingest/log")
def ingest_log(request: IngestLogRequest):
    try:
        result = ingest_ci_log(request.raw_log, repository=request.repository)
        return result
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to ingest CI log: {str(exc)}") from exc


@app.post("/api/investigate")
def run_investigation(request: InvestigationRequest):
    try:
        return investigate(request.prompt, failure_id=request.failure_id)
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc


@app.post("/api/validate")
def validate(request: ValidationRequest):
    try:
        return validate_candidate(request.commit_sha)
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc


@app.get("/api/blast-radius")
def get_blast_radius(function_name: str = "validate_coupon"):
    try:
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
            return {"ok": False, "message": f"Function '{function_name}' not found."}
        record = res[0]
        direct_tests = record.get("direct_tests") or []
        sibling_fns = record.get("sibling_functions") or []
        indirect_tests = record.get("indirect_tests") or []
        related_commits = record.get("related_commits") or []
        related_incidents = record.get("related_incidents") or []

        risk_score = (len(direct_tests) * 4) + (len(indirect_tests) * 2) + len(sibling_fns) + (len(related_incidents) * 3)
        risk_level = "CRITICAL" if risk_score >= 12 else "HIGH" if risk_score >= 6 else "MODERATE"

        return {
            "ok": True,
            "function": function_name,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "direct_tests": direct_tests,
            "indirect_tests": indirect_tests,
            "sibling_functions": sibling_fns,
            "related_commits": related_commits,
            "related_incidents": related_incidents,
        }
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc


@app.get("/api/graph-topology")
def get_graph_topology():
    try:
        node_query = """
        MATCH (n)
        RETURN labels(n) AS labels,
               coalesce(n.name, n.id, n.sha, n.path, 'Item') AS name,
               coalesce(n.summary, n.message, n.exception, '') AS details
        LIMIT 60
        """
        edge_query = """
        MATCH (a)-[r]->(b)
        RETURN type(r) AS rel_type,
               labels(a)[0] AS source_label,
               coalesce(a.name, a.id, a.sha, a.path, 'source') AS source_name,
               labels(b)[0] AS target_label,
               coalesce(b.name, b.id, b.sha, b.path, 'target') AS target_name
        LIMIT 80
        """
        nodes_raw = rows(node_query)
        edges_raw = rows(edge_query)
        
        # Clean nodes format
        formatted_nodes = []
        for i, n in enumerate(nodes_raw):
            lbl = n.get("labels", ["Node"])[0] if isinstance(n.get("labels"), list) and n.get("labels") else "Node"
            formatted_nodes.append({
                "id": n.get("name") or f"node_{i}",
                "label": lbl,
                "name": n.get("name") or f"node_{i}",
                "details": n.get("details", "")[:80],
            })

        return {
            "ok": True,
            "nodes": formatted_nodes,
            "edges": edges_raw,
        }
    except GraphUnavailable as exc:
        raise graph_error(exc) from exc

