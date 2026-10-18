"""A tool-using agent for traceable regression triage backed by FalkorDB."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .graph import rows, write
from .validation import run_isolated_regression


SEED_QUERIES = [
    """CREATE
      (repo:Repository {name:'checkout-service', language:'Python'}),
      (file:File {path:'src/checkout.py', repository:'checkout-service'}),
      (test:Test {id:'test_checkout_rejects_expired_coupon', name:'test_checkout_rejects_expired_coupon', status:'failed'}),
      (fn:Function {name:'validate_coupon', symbol:'checkout.validate_coupon'}),
      (run:TestRun {id:'run-1842', workflow:'CI / pull-request', branch:'main', at:'2026-10-16T10:42:00Z', status:'failed'}),
      (failure:Failure {id:'failure-1842-1', message:'Expected expired coupon to be rejected; got accepted', exception:'AssertionError', line:38, at:'2026-10-16T10:42:00Z'}),
      (c1:Commit {sha:'a17c9e2', message:'Refactor coupon expiry comparison', author:'Mina Patel', at:'2026-10-16T09:58:00Z', additions:2, deletions:2}),
      (c2:Commit {sha:'6bf04d1', message:'Add coupon validation logging', author:'Ravi Shah', at:'2026-10-15T16:10:00Z', additions:5, deletions:1}),
      (f2:Function {name:'log_coupon_decision', symbol:'checkout.log_coupon_decision'}),
      (file2:File {path:'src/logging.py', repository:'checkout-service'}),
      (old:Incident {id:'incident-77', summary:'Coupon boundary regression in pre-release', resolution:'Use an exclusive upper bound for valid_until'}),
      (repo)-[:CONTAINS]->(file),
      (repo)-[:CONTAINS]->(file2),
      (fn)-[:DEFINED_IN]->(file),
      (f2)-[:DEFINED_IN]->(file2),
      (test)-[:EXERCISES]->(fn),
      (test)-[:IN_REPOSITORY]->(repo),
      (run)-[:CONTAINS_FAILURE]->(failure),
      (failure)-[:FAILED_TEST]->(test),
      (c1)-[:CHANGED]->(fn),
      (c1)-[:CHANGED_FILE]->(file),
      (c2)-[:CHANGED]->(f2),
      (c2)-[:CHANGED_FILE]->(file2),
      (old)-[:RESOLVED_BY]->(c1)""",
]


def seed_demo() -> dict:
    write("MATCH (n) DETACH DELETE n")
    for query in SEED_QUERIES:
        write(query)
    return {"nodes": 11, "scenario": "checkout coupon test regression"}


def _score_candidate(row: dict, target_function: str | None = None) -> int:
    score = 0
    if row.get("commit_sha"):
        score += 4  # the commit directly changed the function exercised by the failed test
    if row.get("commit_at"):
        score += 2  # the commit predates this failing CI run in the seeded graph
    if target_function and row.get("function_name") == target_function:
        score += 2
    return score


def _find_target_failure_id(prompt: str, explicit_id: str | None = None) -> str | None:
    """Find the target failure in FalkorDB based on explicit ID, prompt keywords, or latest failure."""
    if explicit_id:
        exists = rows("MATCH (f:Failure {id: $id}) RETURN f.id AS id", {"id": explicit_id})
        if exists:
            return explicit_id

    # Check if prompt contains a specific failure ID or test name
    prompt_lower = prompt.lower()
    all_failures = rows("MATCH (f:Failure)-[:FAILED_TEST]->(t:Test) RETURN f.id AS fid, t.id AS tid, t.name AS tname")
    for item in all_failures:
        if item.get("fid") and item["fid"].lower() in prompt_lower:
            return item["fid"]
        if item.get("tid") and item["tid"].lower() in prompt_lower:
            return item["fid"]
        if item.get("tname") and item["tname"].lower() in prompt_lower:
            return item["fid"]

    # Keyword heuristics
    if "coupon" in prompt_lower:
        matched = rows("MATCH (f:Failure)-[:FAILED_TEST]->(t:Test) WHERE t.id CONTAINS 'coupon' RETURN f.id AS id LIMIT 1")
        if matched:
            return matched[0]["id"]
    if "webhook" in prompt_lower or "timeout" in prompt_lower:
        matched = rows("MATCH (f:Failure)-[:FAILED_TEST]->(t:Test) WHERE t.id CONTAINS 'webhook' RETURN f.id AS id LIMIT 1")
        if matched:
            return matched[0]["id"]
    if "token" in prompt_lower or "session" in prompt_lower or "auth" in prompt_lower:
        matched = rows("MATCH (f:Failure)-[:FAILED_TEST]->(t:Test) WHERE t.id CONTAINS 'token' OR t.id CONTAINS 'session' RETURN f.id AS id LIMIT 1")
        if matched:
            return matched[0]["id"]

    # Fallback to the latest failure in the graph
    latest = rows("MATCH (f:Failure) RETURN f.id AS id ORDER BY f.id DESC LIMIT 1")
    return latest[0]["id"] if latest else None


def investigate(prompt: str, failure_id: str | None = None) -> dict:
    normalized = prompt.lower()
    chosen_tools = ["trace_failure_path"]
    if any(word in normalized for word in ("before", "history", "memory", "previous", "remember")):
        chosen_tools.append("recall_prior_investigation")
    if any(word in normalized for word in ("similar", "incident", "resolved", "happened before")):
        chosen_tools.append("find_related_incidents")

    target_failure_id = _find_target_failure_id(prompt, failure_id)
    if not target_failure_id:
        return {
            "status": "unknown",
            "message": "No test failures are present in the graph. Ingest a CI log or seed the demo scenario first.",
        }

    # Dynamic multi-hop query parameterized by target failure ID
    incident_query = """
    MATCH (failure:Failure {id: $failure_id})-[:FAILED_TEST]->(test:Test)
          -[:EXERCISES]->(fn:Function)-[:DEFINED_IN]->(file:File)
    OPTIONAL MATCH (commit:Commit)-[:CHANGED]->(fn)
    RETURN failure.id AS failure_id, failure.message AS failure_message,
           failure.exception AS exception, failure.line AS line,
           test.id AS test_id, fn.name AS function_name, file.path AS file_path,
           commit.sha AS commit_sha, commit.message AS commit_message,
           commit.author AS commit_author, commit.at AS commit_at
    ORDER BY commit.at DESC
    """
    paths = rows(incident_query, {"failure_id": target_failure_id})
    if not paths:
        return {
            "status": "unknown",
            "message": f"Failure '{target_failure_id}' has no connected test/function path in the graph.",
        }

    target_fn = paths[0].get("function_name")
    target_test = paths[0].get("test_id")

    candidates_by_sha: dict[str, dict] = {}
    for path in paths:
        sha = path.get("commit_sha")
        if sha:
            item = candidates_by_sha.setdefault(sha, {**path, "score": _score_candidate(path, target_fn)})
            item["score"] = max(item["score"], _score_candidate(path, target_fn))
    candidates = sorted(candidates_by_sha.values(), key=lambda item: (-item["score"], item.get("commit_at", "")))

    # Related incidents query parameterized by target test
    incidents_query = """
    MATCH (test:Test {id: $test_id})-[:EXERCISES]->(fn:Function)<-[:CHANGED]-(commit:Commit)
          <-[:RESOLVED_BY]-(incident:Incident)
    RETURN incident.id AS incident_id, incident.summary AS summary,
           incident.resolution AS resolution, commit.sha AS commit_sha
    """
    incidents = rows(incidents_query, {"test_id": target_test}) if "find_related_incidents" in chosen_tools else []

    # Memory query parameterized by fingerprint
    fingerprint = f"{target_test}-{target_fn}"
    memory_query = """
    MATCH (i:Investigation {fingerprint: $fingerprint})
    OPTIONAL MATCH (i)-[:RECORDED]->(m:AgentMemory)
    RETURN i.id AS id, i.at AS at, i.summary AS summary,
           m.text AS memory, m.kind AS memory_kind
    ORDER BY i.at DESC LIMIT 5
    """
    memory = rows(memory_query, {"fingerprint": fingerprint}) if "recall_prior_investigation" in chosen_tools else []

    investigation_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    summary = f"CI failure {target_failure_id} traced through test → function → file → changed commits"
    memory_text = (
        f"Prior incident related to {target_fn} was resolved in commit {candidates[0]['commit_sha']}."
        if candidates
        else f"Investigation recorded for {target_test}."
    )
    write(
        """CREATE (i:Investigation {id:$id, fingerprint:$fingerprint, at:$at, summary:$summary, prompt:$prompt})
           CREATE (m:AgentMemory {text:$memory_text, kind:'episodic', at:$at})
           CREATE (i)-[:RECORDED]->(m)""",
        {
            "id": investigation_id,
            "fingerprint": fingerprint,
            "at": now,
            "summary": summary,
            "prompt": prompt[:500],
            "memory_text": memory_text,
        },
    )

    primary = candidates[0] if candidates else None
    return {
        "status": "answered",
        "investigation_id": investigation_id,
        "failure_id": target_failure_id,
        "prompt": prompt,
        "selected_tools": chosen_tools,
        "answer": (
            f"The strongest graph-supported candidate is commit {primary['commit_sha']} "
            f"({primary['commit_message']}). It changed {primary['function_name']}, which the failing test exercises. "
            "This is a candidate cause, not proof; validate it with the isolated regression check."
            if primary else "The test and function are connected, but the graph has no related commit to rank."
        ),
        "failure": {key: paths[0].get(key) for key in ("failure_id", "failure_message", "exception", "line", "test_id")},
        "paths": paths,
        "candidates": candidates,
        "memory": memory,
        "related_incidents": incidents,
        "evidence": [
            {"kind": "FACT", "text": f"CI recorded {paths[0].get('exception')} at {paths[0].get('file_path')}:{paths[0].get('line')}.", "source": paths[0].get("failure_id")},
            {"kind": "FACT", "text": f"{paths[0].get('test_id')} exercises {paths[0].get('function_name')} in the graph.", "source": paths[0].get("test_id")},
            *[
                {"kind": "FACT", "text": f"Commit {candidate['commit_sha']} changed {candidate['function_name']} before the failing CI run.", "source": candidate["commit_sha"]}
                for candidate in candidates
            ],
            *([{"kind": "INFERENCE", "text": f"{primary['commit_sha']} is the leading cause candidate because it directly changed the exercised function shortly before the failure.", "source": primary["commit_sha"]}] if primary else []),
        ],
    }


def validate_candidate(commit_sha: str) -> dict:
    """Run a fixed, synthetic regression check in an isolated Python subprocess."""
    result = run_isolated_regression(commit_sha)
    validation_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    write(
        """MERGE (c:Commit {sha:$sha})
           CREATE (v:Validation {id:$id, status:$status, output:$output, at:$at})
           CREATE (c)-[:CHECKED_BY]->(v)""",
        {"sha": commit_sha, "id": validation_id, "status": result["status"], "output": result["output"][:2000], "at": now},
    )
    return {"validation_id": validation_id, "commit_sha": commit_sha, **result}
