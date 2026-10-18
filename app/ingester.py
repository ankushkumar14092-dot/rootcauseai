"""FalkorDB Graph Ingestion Engine for CI/CD Logs."""

from __future__ import annotations

from typing import Any
from .graph import rows, write
from .parser import ParsedCILog, parse_ci_log


def ingest_ci_log(log_text: str, repository: str | None = None) -> dict[str, Any]:
    """Parse a CI log and ingest all entities and relationships into FalkorDB."""
    parsed: ParsedCILog = parse_ci_log(log_text, default_repo=repository or "checkout-service")
    repo_name = repository or parsed.repository

    # 1. Merge Repository
    write(
        """MERGE (repo:Repository {name: $repo})
           ON CREATE SET repo.language = 'Python'""",
        {"repo": repo_name},
    )

    # 2. Merge TestRun
    write(
        """MERGE (run:TestRun {id: $run_id})
           ON CREATE SET run.workflow = $workflow, run.branch = $branch, run.at = $at, run.status = $status
           ON MATCH SET run.workflow = $workflow, run.branch = $branch, run.status = $status""",
        {
            "run_id": parsed.run_id,
            "workflow": parsed.workflow,
            "branch": parsed.branch,
            "at": parsed.at,
            "status": parsed.status,
        },
    )

    nodes_created = 2
    relationships_created = 0
    ingested_failures = []

    # 3. Process each Failure
    for failure in parsed.failures:
        # Create or update File
        write(
            """MERGE (file:File {path: $path, repository: $repo})""",
            {"path": failure.source_file, "repo": repo_name},
        )

        # Create or update Function
        symbol = f"{failure.source_file.replace('/', '.').replace('.py', '')}.{failure.function_name}"
        write(
            """MERGE (fn:Function {name: $name, symbol: $symbol})""",
            {"name": failure.function_name, "symbol": symbol},
        )

        # Create or update Test
        write(
            """MERGE (test:Test {id: $test_id})
               ON CREATE SET test.name = $test_name, test.status = 'failed'
               ON MATCH SET test.status = 'failed'""",
            {"test_id": failure.test_id, "test_name": failure.test_name},
        )

        # Create Failure node
        write(
            """MERGE (f:Failure {id: $failure_id})
               ON CREATE SET f.message = $message, f.exception = $exception, f.line = $line, f.test_id = $test_id, f.at = $at
               ON MATCH SET f.message = $message, f.exception = $exception, f.line = $line""",
            {
                "failure_id": failure.failure_id,
                "message": failure.message,
                "exception": failure.exception,
                "line": failure.line,
                "test_id": failure.test_id,
                "at": parsed.at,
            },
        )

        # Connect graph relationships
        write(
            """MATCH (repo:Repository {name: $repo}),
                     (file:File {path: $path, repository: $repo}),
                     (fn:Function {name: $fn_name}),
                     (test:Test {id: $test_id}),
                     (run:TestRun {id: $run_id}),
                     (f:Failure {id: $failure_id})
               MERGE (repo)-[:CONTAINS]->(file)
               MERGE (fn)-[:DEFINED_IN]->(file)
               MERGE (test)-[:EXERCISES]->(fn)
               MERGE (test)-[:IN_REPOSITORY]->(repo)
               MERGE (run)-[:CONTAINS_FAILURE]->(f)
               MERGE (f)-[:FAILED_TEST]->(test)""",
            {
                "repo": repo_name,
                "path": failure.source_file,
                "fn_name": failure.function_name,
                "test_id": failure.test_id,
                "run_id": parsed.run_id,
                "failure_id": failure.failure_id,
            },
        )

        nodes_created += 4
        relationships_created += 6

        # Ingest Commits if found
        for commit in parsed.commits:
            write(
                """MERGE (c:Commit {sha: $sha})
                   ON CREATE SET c.message = $message, c.author = $author, c.at = $at, c.additions = $additions, c.deletions = $deletions""",
                {
                    "sha": commit.sha,
                    "message": commit.message,
                    "author": commit.author,
                    "at": commit.at,
                    "additions": commit.additions,
                    "deletions": commit.deletions,
                },
            )
            write(
                """MATCH (c:Commit {sha: $sha}), (fn:Function {name: $fn_name}), (file:File {path: $path, repository: $repo})
                   MERGE (c)-[:CHANGED]->(fn)
                   MERGE (c)-[:CHANGED_FILE]->(file)""",
                {
                    "sha": commit.sha,
                    "fn_name": failure.function_name,
                    "path": failure.source_file,
                    "repo": repo_name,
                },
            )
            nodes_created += 1
            relationships_created += 2

        # Add domain incidents if applicable
        if "coupon" in failure.function_name or "coupon" in failure.test_id:
            write(
                """MERGE (old:Incident {id:'incident-77'})
                   ON CREATE SET old.summary = 'Coupon boundary regression in pre-release',
                                 old.resolution = 'Use an exclusive upper bound for valid_until'
                   WITH old
                   MATCH (c:Commit) WHERE c.sha STARTS WITH 'a17c9'
                   MERGE (old)-[:RESOLVED_BY]->(c)"""
            )
        elif "webhook" in failure.function_name:
            write(
                """MERGE (old:Incident {id:'incident-92'})
                   ON CREATE SET old.summary = 'Gateway connection timeouts under burst traffic',
                                 old.resolution = 'Maintain at least 5s retry window and exponential backoff'
                   WITH old
                   MATCH (c:Commit) WHERE c.sha STARTS WITH 'd4e1'
                   MERGE (old)-[:RESOLVED_BY]->(c)"""
            )
        elif "session" in failure.function_name or "token" in failure.function_name:
            write(
                """MERGE (old:Incident {id:'incident-104'})
                   ON CREATE SET old.summary = 'Stale session tokens returned from redis cluster cache',
                                 old.resolution = 'Enforce cache eviction on session revocation'
                   WITH old
                   MATCH (c:Commit) WHERE c.sha STARTS WITH '7c3f'
                   MERGE (old)-[:RESOLVED_BY]->(c)"""
            )

        ingested_failures.append({
            "failure_id": failure.failure_id,
            "test_id": failure.test_id,
            "exception": failure.exception,
            "message": failure.message,
            "source_file": failure.source_file,
            "line": failure.line,
            "function_name": failure.function_name,
        })

    return {
        "ok": True,
        "run_id": parsed.run_id,
        "workflow": parsed.workflow,
        "branch": parsed.branch,
        "repository": repo_name,
        "failures_count": len(parsed.failures),
        "failures": ingested_failures,
        "commits_count": len(parsed.commits),
        "commits": [c.to_dict() for c in parsed.commits],
        "nodes_added": nodes_created,
        "relationships_added": relationships_created,
        "primary_failure_id": ingested_failures[0]["failure_id"] if ingested_failures else None,
    }


def list_failures() -> list[dict[str, Any]]:
    """Retrieve all failures currently stored in the FalkorDB graph."""
    query = """
    MATCH (f:Failure)-[:FAILED_TEST]->(t:Test)
    OPTIONAL MATCH (t)-[:EXERCISES]->(fn:Function)-[:DEFINED_IN]->(file:File)
    OPTIONAL MATCH (run:TestRun)-[:CONTAINS_FAILURE]->(f)
    RETURN f.id AS failure_id, f.message AS message, f.exception AS exception,
           f.line AS line, f.at AS at, t.id AS test_id, fn.name AS function_name,
           file.path AS file_path, run.id AS run_id, run.workflow AS workflow
    ORDER BY f.id DESC
    """
    return rows(query)
