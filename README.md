# RootCause AI

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Cloudflare%20Tunnel-blue?style=for-the-badge&logo=cloudflare)](https://knitting-brain-ids-carmen.trycloudflare.com)
[![FalkorDB](https://img.shields.io/badge/Powered%20By-FalkorDB-red?style=for-the-badge)](https://www.falkordb.com/)
[![Track](https://img.shields.io/badge/Hackathon-Track%2001%20Submission-success?style=for-the-badge)](https://www.wemakedevs.org/hackathons/falkordb)

> **Live Demo URL:** [https://knitting-brain-ids-carmen.trycloudflare.com](https://knitting-brain-ids-carmen.trycloudflare.com)  
> *(Zero installation required for judges — live interactive UI with FalkorDB graph reasoning)*

RootCause AI investigates a synthetic CI regression by following its relationships through **FalkorDB**. It connects a failing test to the function it exercises, the source file where that function lives, and commits that changed the function. It ranks candidate causes, shows the graph evidence behind each claim, remembers investigations in the graph, and can run one fixed regression check in an isolated subprocess.

The graph is the product's working context: investigation, candidate ranking, and memory all depend on FalkorDB traversals. The app has no relational or document-store fallback.

## 🚀 Live Demo & Deployment

- **Live URL:** [https://knitting-brain-ids-carmen.trycloudflare.com](https://knitting-brain-ids-carmen.trycloudflare.com)
- **FalkorDB Web Visualizer:** Available locally at `http://localhost:3000`
- **MCP Server Endpoint:** `python3 -m app.mcp_server` (stdio JSON-RPC with 5 tools)

## Run locally

Docker Compose starts FalkorDB and the app:

```bash
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The FalkorDB Browser is at [http://localhost:3000](http://localhost:3000). Click **Load demo graph**, then investigate the sample expired-coupon failure.

To run only FalkorDB with the app in your Python environment:

```bash
docker compose up -d falkordb
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Python 3.12 is used in the app container. Local settings can be changed with the variables in `.env.example`; copy them to `.env` if needed. The demo uses synthetic data and requires no API key.

## Investigation flow

1. The agent accepts a short natural-language question. It does not turn that text into Cypher.
2. A bounded intent router selects from fixed tools: `trace_failure_path`, `recall_prior_investigation`, and `find_related_incidents`.
3. Those tools run application-authored Cypher over the graph. The failure-to-test-to-function path gives the agent context that a flat CI log alone does not carry.
4. Candidate commits are ranked from recorded graph relationships and timestamps. A leading commit is labeled **INFERENCE**, while the underlying failure and code links are shown as **FACT**.
5. The investigation and a short episodic memory are written back to FalkorDB. Questions about history retrieve prior investigations and related incidents.
6. **Run isolated check** runs a fixed synthetic regression test in a temporary directory and records the result against the candidate commit. It cannot execute commands or paths supplied by the user and does not modify this repository.

This proof of concept supports one seeded checkout regression scenario. Its agent loop is deterministic, so judges can run it without a model credential; the graph tools and evidence trail are the focus of the demo.

## Graph data model

| Node | Useful properties | Relationships |
| --- | --- | --- |
| `Repository` | `name`, `language` | `CONTAINS` files; tests belong through `IN_REPOSITORY` |
| `File` | `path`, `repository` | `CONTAINS` from repository; `DEFINED_IN` from functions; `CHANGED_FILE` from commits |
| `Test` | `id`, `name`, `status` | `EXERCISES` functions; `FAILED_TEST` from a failure; `IN_REPOSITORY` to repository |
| `Function` | `name`, `symbol` | `DEFINED_IN` a file; `CHANGED` from commits |
| `TestRun` | `id`, `workflow`, `branch`, `at`, `status` | `CONTAINS_FAILURE` failures |
| `Failure` | `id`, `message`, `exception`, `line` | `FAILED_TEST` a test |
| `Commit` | `sha`, `message`, `author`, `at` | `CHANGED` functions and `CHANGED_FILE` files; `CHECKED_BY` validation |
| `Incident` | `id`, `summary`, `resolution` | `RESOLVED_BY` a commit |
| `Investigation` | `id`, `fingerprint`, `at`, `summary`, `prompt` | `RECORDED` agent memory |
| `AgentMemory` | `text`, `kind`, `at` | `RECORDED` from investigation |
| `Validation` | `id`, `status`, `output`, `at` | `CHECKED_BY` from commit |

Relationship directions are intentionally explicit so a trace can be rendered as supporting evidence. IDs use the small synthetic `checkout-service` scenario shipped in `app/agent.py`.

## Core Cypher

The agent's principal multi-hop query follows the failing test to its exercised function and source file, then finds commits that changed that function:

```cypher
MATCH (failure:Failure {id:'failure-1842-1'})-[:FAILED_TEST]->(test:Test)
      -[:EXERCISES]->(fn:Function)-[:DEFINED_IN]->(file:File)
OPTIONAL MATCH (commit:Commit)-[:CHANGED]->(fn)
RETURN failure.id AS failure_id, failure.message AS failure_message,
       test.id AS test_id, fn.name AS function_name, file.path AS file_path,
       commit.sha AS commit_sha, commit.message AS commit_message,
       commit.author AS commit_author, commit.at AS commit_at
ORDER BY commit.at DESC
```

Related incident memory is retrieved by following the function to commits and earlier incidents:

```cypher
MATCH (test:Test {id:'test_checkout_rejects_expired_coupon'})
      -[:EXERCISES]->(fn:Function)<-[:CHANGED]-(commit:Commit)
      <-[:RESOLVED_BY]-(incident:Incident)
RETURN incident.id AS incident_id, incident.summary AS summary,
       incident.resolution AS resolution, commit.sha AS commit_sha
```

The full fixed query templates and graph writes are in `app/agent.py`. The model is not allowed to author Cypher.

## Architecture

```text
Browser UI ──HTTP──> FastAPI ──Log Ingestion / Parser──> FalkorDB Graph
                           └──fixed tools / Cypher─────> Traversal & Ranking
                           └──bounded subprocess───────> Candidate validation
```

FalkorDB serves as both connected operational context and persistent episodic memory. The browser UI renders paths, evidence, and ingestion results returned by the server.

## Features & Capabilities

- **CI/CD Log Parser (`app/parser.py`)**: Accepts raw console output from GitHub Actions, Pytest, and Python unittest runs. Automatically extracts test run metadata, failing assertions/exceptions, source file locations, line numbers, target functions, and git commit SHAs/authors.
- **Dynamic Graph Ingestion (`app/ingester.py`)**: Ingests parsed entities directly into FalkorDB, merging repository, test runs, failures, tests, functions, source files, and commits with explicit OpenCypher relationships.
- **Dynamic Multi-Hop Investigation (`app/agent.py`)**: Explores any test failure in the graph, evaluates candidate commits, separates **FACT** from **INFERENCE**, and retrieves episodic memory.
- **Isolated Validation Sandbox (`app/validation.py`)**: Re-runs isolated regression checks in temporary environments to confirm hypotheses.

## Endpoints

- `GET /api/status`: FalkorDB connection status, node counts, and recorded failures.
- `GET /api/sample-logs`: Pre-packaged realistic CI/CD failure logs (GitHub Actions Checkout Coupon, Payments Webhook Timeout, Pytest Auth Session Revocation).
- `GET /api/failures`: All test failures currently indexed in FalkorDB.
- `POST /api/ingest/log`: Ingests raw CI/CD console text and connects entities in FalkorDB.
- `POST /api/investigate`: Runs graph traversals and evidence ranking for any observed failure.
- `POST /api/validate`: Runs isolated regression check for a candidate commit.

## Track and disclosure

- **Track:** Agents That Act on Connected Data
- **AI coding assistant disclosure:** This project is being built with AI coding assistance.
- **Data:** Synthetic and real CI/CD logs.

