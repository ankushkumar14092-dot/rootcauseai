"""Integration and unit tests for RootCause AI CI/CD log ingestion, MCP server, and graph agent."""

import json
import pytest
from fastapi.testclient import TestClient

from app.agent import investigate, seed_demo, validate_candidate
from app.ingester import ingest_ci_log, list_failures
from app.main import app
from app.mcp_server import analyze_blast_radius, mcp, trace_failure_path, validate_candidate_fix
from app.parser import parse_ci_log
from app.sample_logs import SAMPLE_LOGS


client = TestClient(app)


def test_seed_demo_and_status():
    """Verify seed endpoint initializes demo graph in FalkorDB."""
    response = client.post("/api/seed")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["nodes"] >= 11

    # Status check
    status_res = client.get("/api/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["ok"] is True
    assert status_data["nodes"] >= 11


def test_ci_log_parser_github_actions():
    """Verify parsing GitHub Actions console log with pytest failures and commits."""
    log = SAMPLE_LOGS["github_actions_coupon"]["log"]
    parsed = parse_ci_log(log, default_repo="checkout-service")

    assert parsed.status == "failed"
    assert len(parsed.failures) >= 1
    assert parsed.failures[0].test_id == "test_checkout_rejects_expired_coupon"
    assert parsed.failures[0].exception == "AssertionError"
    assert parsed.failures[0].line == 38
    assert parsed.failures[0].function_name == "validate_coupon"

    assert len(parsed.commits) >= 1
    assert parsed.commits[0].sha == "a17c9e2"
    assert "Mina Patel" in parsed.commits[0].author


def test_ci_log_parser_webhook_timeout():
    """Verify parsing payments service webhook timeout failure."""
    log = SAMPLE_LOGS["github_actions_webhook_timeout"]["log"]
    parsed = parse_ci_log(log, default_repo="payments-service")

    assert parsed.status == "failed"
    assert len(parsed.failures) >= 1
    failure = parsed.failures[0]
    assert failure.test_id == "test_stripe_webhook_retry"
    assert failure.exception == "TimeoutError"
    assert failure.line == 74
    assert failure.function_name == "handle_webhook_retry"

    assert len(parsed.commits) >= 1
    assert parsed.commits[0].sha == "d4e1a0b"


def test_ingest_endpoint():
    """Verify POST /api/ingest/log endpoint ingests log and links graph entities."""
    log = SAMPLE_LOGS["pytest_auth_invalidation"]["log"]
    response = client.post("/api/ingest/log", json={"raw_log": log, "repository": "auth-service"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["failures_count"] >= 1
    assert data["repository"] == "auth-service"
    assert data["primary_failure_id"] is not None


def test_dynamic_investigate_endpoint():
    """Verify investigating specific test failure returns graph trace and candidate commits."""
    response = client.post(
        "/api/investigate",
        json={"prompt": "Why did test_checkout_rejects_expired_coupon fail?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert "a17c9e2" in data["answer"]
    assert len(data["candidates"]) >= 1
    assert any(ev["kind"] == "FACT" for ev in data["evidence"])
    assert any(ev["kind"] == "INFERENCE" for ev in data["evidence"])


def test_validate_endpoint():
    """Verify POST /api/validate executes safe subprocess check and passes."""
    response = client.post("/api/validate", json={"commit_sha": "a17c9e2"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "passed"
    assert "validation_id" in data


def test_sample_logs_and_failures_endpoints():
    """Verify GET /api/sample-logs and GET /api/failures."""
    samples_res = client.get("/api/sample-logs")
    assert samples_res.status_code == 200
    assert len(samples_res.json()["samples"]) >= 3

    failures_res = client.get("/api/failures")
    assert failures_res.status_code == 200
    assert len(failures_res.json()["failures"]) >= 1


def test_blast_radius_endpoint():
    """Verify GET /api/blast-radius calculates downstream graph risk score."""
    res = client.get("/api/blast-radius?function_name=validate_coupon")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["function"] == "validate_coupon"
    assert "risk_score" in data
    assert len(data["direct_tests"]) >= 1


def test_graph_topology_endpoint():
    """Verify GET /api/graph-topology returns nodes and relationships for visual canvas."""
    res = client.get("/api/graph-topology")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["nodes"]) >= 5
    assert len(data["edges"]) >= 5


def test_mcp_server_tools():
    """Verify native Model Context Protocol tools execute successfully."""
    # Test blast radius tool
    blast_res = json.loads(analyze_blast_radius("validate_coupon"))
    assert blast_res["function"] == "validate_coupon"
    assert "impact_risk_level" in blast_res

    # Test failure path tool
    trace_res = json.loads(trace_failure_path(prompt="Why did test fail?"))
    assert trace_res["status"] == "answered"

    # Test candidate validation tool
    val_res = json.loads(validate_candidate_fix("a17c9e2"))
    assert val_res["status"] == "passed"
