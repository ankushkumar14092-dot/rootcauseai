# RootCause AI — Official Hackathon Submission Guide
## Track 01: Agents That Act on Connected Data
**Graph Hacks: Context for AI Agents | WeMakeDevs & FalkorDB (Oct 15–18, 2026)**

---

## 1. Executive Summary

**RootCause AI** is an autonomous root-cause investigation agent built specifically for test regressions and CI/CD pipelines, powered by **FalkorDB** as its connected context and memory layer.

Instead of flat CI logs or hallucinated guesses, RootCause AI:
1. **Parses and ingests real CI/CD logs** (GitHub Actions, Pytest, Python tracebacks) into a structured code knowledge graph.
2. **Performs multi-hop OpenCypher traversals** connecting:
   $$\text{TestRun} \longrightarrow \text{Failure} \longrightarrow \text{Test} \longrightarrow \text{Function} \longrightarrow \text{File} \longleftarrow \text{Commit} \longleftarrow \text{Incident}$$
3. **Calculates Blast Radius & Dependency Impact** using graph algorithms to evaluate downstream service risk.
4. **Separates observable FACTS from INFERENCES**, providing a transparent evidence trail.
5. **Takes verifiable action** by running isolated subprocess regression tests in sandboxes to validate hypotheses.
6. **Exposes native MCP (Model Context Protocol) tools** for seamless tool selection by any AI agent (Claude Desktop, Cursor, Antigravity IDE).

---

## 2. Track 01 Alignment Matrix

| Official Track 01 Focus Point | RootCause AI Implementation | Source Location |
| :--- | :--- | :--- |
| **Multi-hop reasoning** | 5-hop path traversal in FalkorDB linking failing assertions to the functions they exercise, files, and git commits that modified those functions. | `app/agent.py` |
| **Graph queries & algorithms as agent tools** | Dedicated OpenCypher tools (`trace_failure_path`, `analyze_blast_radius`, `recall_memory`). Downstream risk scoring and dependency traversals. | `app/agent.py`, `app/mcp_server.py` |
| **Tool selection through MCP** | Native Model Context Protocol (MCP) server (`app/mcp_server.py`) exposing 5 callable tools over stdio/JSON-RPC. Compatible with Claude Desktop, Cursor, and Antigravity. | `app/mcp_server.py` |
| **Actions based on what graph shows** | Autonomous candidate validation (`validate_candidate`): runs isolated Python subprocess in a sandbox fixture to confirm or refute hypotheses without touching repo files. | `app/validation.py` |
| **Explainable results** | Explicit labelling of graph evidence into observable **FACT** vs agent **INFERENCE**, with complete node & edge lineage. | `app/agent.py`, `web/app.js` |
| **FalkorDB doing real work (Rule 3)** | FalkorDB is the core engine; there is no relational or document store fallback. Ingesting, querying, ranking, and memory all fail if FalkorDB is removed. | `app/graph.py` |

---

## 3. FalkorDB Graph Schema & Cypher Queries

### Graph Data Model
- **`Repository`**: `{name, language}`
- **`TestRun`**: `{id, workflow, branch, at, status}`
- **`Failure`**: `{id, message, exception, line, at}`
- **`Test`**: `{id, name, status}`
- **`Function`**: `{name, symbol}`
- **`File`**: `{path, repository}`
- **`Commit`**: `{sha, message, author, at, additions, deletions}`
- **`Incident`**: `{id, summary, resolution}`
- **`Investigation`**: `{id, fingerprint, at, summary, prompt}`
- **`AgentMemory`**: `{text, kind, at}`
- **`Validation`**: `{id, status, output, at}`

### Core Cypher Queries

#### A. Multi-Hop Investigation Traversal
```cypher
MATCH (failure:Failure {id: $failure_id})-[:FAILED_TEST]->(test:Test)
      -[:EXERCISES]->(fn:Function)-[:DEFINED_IN]->(file:File)
OPTIONAL MATCH (commit:Commit)-[:CHANGED]->(fn)
RETURN failure.id AS failure_id, failure.message AS failure_message,
       failure.exception AS exception, failure.line AS line,
       test.id AS test_id, fn.name AS function_name, file.path AS file_path,
       commit.sha AS commit_sha, commit.message AS commit_message,
       commit.author AS commit_author, commit.at AS commit_at
ORDER BY commit.at DESC
```

#### B. Blast Radius & Dependency Impact Analysis
```cypher
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
```

#### C. Episodic Agent Memory Retrieval
```cypher
MATCH (i:Investigation {fingerprint: $fingerprint})
OPTIONAL MATCH (i)-[:RECORDED]->(m:AgentMemory)
RETURN i.id AS id, i.at AS at, i.summary AS summary,
       m.text AS memory, m.kind AS memory_kind
ORDER BY i.at DESC LIMIT 5
```

---

## 4. Demo Video Recording Script (2–3 Minutes)

### Scene 1: The Problem & Solution (0:00 – 0:30)
- **Visual**: Open [http://localhost:8000](http://localhost:8000). Show the dark sleek UI with active FalkorDB status indicator.
- **Narrate**: *"When CI pipelines break, developers drown in thousands of lines of flat terminal logs. Agents without graphs hallucinate causes because they can't trace relationships. RootCause AI uses FalkorDB as an operational context layer to connect failures to code, files, and commits."*

### Scene 2: Ingesting Real CI/CD Logs (0:30 – 1:00)
- **Visual**: Click **"Ingest CI Log"**. Click the preset **"GitHub Actions: Payment Webhook Timeout"** or **"Checkout Coupon Expiry"**. Click **"⚡ Ingest into FalkorDB"**.
- **Narrate**: *"Here we ingest a raw GitHub Actions console output. The parser extracts the failed test, line number, exercised function, and commit author, merging 7 nodes and 8 relationships directly into FalkorDB."*

### Scene 3: Multi-Hop Reasoning & Evidence Trail (1:00 – 1:40)
- **Visual**: Click **"Investigate This Failure ↗"**.
- **Narrate**: *"RootCause AI executes an OpenCypher multi-hop traversal. It tracks the `AssertionError` at line 38 to `test_checkout_rejects_expired_coupon`, to `validate_coupon()`, and reveals commit `a17c9e2` by Mina Patel. Notice how every observable fact is tagged FACT, while the leading hypothesis is labeled INFERENCE."*

### Scene 4: Blast Radius & Actionable Validation (1:40 – 2:15)
- **Visual**: Show the **Blast Radius Card** (Risk Score, Direct & Indirect Tests Affected). Then click **"Run isolated check →"** and show the instant passing sandbox validation badge `PASSED ✓`.
- **Narrate**: *"The agent calculates blast radius across downstream tests using graph connectivity. It then takes action: it spins up a safe, temporary Python subprocess sandbox to validate the candidate fix without touching our repo files."*

### Scene 5: Visual Graph & MCP Server (2:15 – 2:45)
- **Visual**: Switch to **"Graph Visualizer"** (drag nodes, inspect relationships) and **"MCP Server Hub"**.
- **Narrate**: *"Judges can explore the live topology on our interactive canvas or connect Claude Desktop and Cursor using our native Model Context Protocol (MCP) server. RootCause AI demonstrates the full power of FalkorDB for Track 01."*

---

## 5. Quick Start Instructions for Judges

### Run with Docker Compose (Recommended)
```bash
git clone <YOUR_GITHUB_REPO_URL>
cd GRAPHAGENT
docker compose up --build
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### Run with Local Python + FalkorDB Container
```bash
docker compose up -d falkordb
python3 -m pip install -r requirements.txt
python3 -m pytest tests/test_api.py -v
python3 -m uvicorn app.main:app --reload --port 8000
```

### Run Native MCP Server
```bash
python3 -m app.mcp_server
```
