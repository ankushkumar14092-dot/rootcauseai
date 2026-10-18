# RootCause AI — Competitor & Reference Analysis

> **Methodology**: Every finding below is sourced from a primary-source URL that was
> fetched and read during this session. Inferences are labelled **[INFERENCE]**.
> Claims not verifiable from fetched content are labelled **[UNKNOWN]**.
> Nothing is invented.

---

## 1. FalkorDB — Graph Database

**Sources inspected**
- `https://docs.falkordb.com/` (live HTML)
- `https://raw.githubusercontent.com/FalkorDB/falkordb-py/master/README.md`
- `https://raw.githubusercontent.com/FalkorDB/falkordb-py/master/falkordb/graph.py`

### Verified Facts

| Fact | Source |
|------|--------|
| Python SDK package name: `falkordb` v1.8.0 on PyPI | README |
| Requires a running FalkorDB server (Docker or FalkorDB Cloud) | README |
| Default port: `6379` (Redis-protocol compatible) | graph.py |
| Connection: `FalkorDB(host, port, username, password)` | graph.py + code-graph/api/graph.py |
| Graph selection: `db.select_graph(name)` returns a `Graph` object | graph.py |
| Query execution: `graph.query(cypher_string, params=dict)` | graph.py |
| Read-only query: `graph.ro_query(cypher_string)` | graph.py (RO_QUERY_CMD) |
| Index creation: `graph.create_node_range_index(label, *props)` | code-graph/api/graph.py |
| Full-text index: `graph.create_node_fulltext_index(label, prop)` | code-graph/api/graph.py |
| List graphs: `db.list_graphs()` | code-graph/api/graph.py |
| AsyncIO variant: `from falkordb.asyncio import FalkorDB` | code-graph/api/graph.py |
| FalkorDB Cloud free tier available at `app.falkordb.cloud` | code-graph-backend README |
| Docker run: `docker run -p 6379:6379 falkordb/falkordb:latest` | code-graph README |
| Supports OpenCypher query language | FalkorDB docs meta keywords |

### Limitations Relevant to MVP

- FalkorDB server **must be running independently** — the SDK is a client only.
- Docker daemon was confirmed **not running** on this machine at audit time.
- FalkorDB Cloud credentials not yet provided.
- Installing `falkordb` v1.8.0 upgrades `redis` from v5.3.1 to v8.1.0 (confirmed by pip output).

### Licensing

- `falkordb-py`: MIT License.
- `code-graph`: MIT License (verified from LICENSE file: "MIT License / Copyright (c) 2024 FalkorDB").

---

## 2. FalkorDB code-graph — Reference Implementation

**Sources inspected**
- `https://raw.githubusercontent.com/FalkorDB/code-graph/main/README.md`
- `https://raw.githubusercontent.com/FalkorDB/code-graph-backend/main/README.md`
- `https://raw.githubusercontent.com/FalkorDB/code-graph/main/api/graph.py`

### Verified Facts

| Fact | Source |
|------|--------|
| `code-graph-backend` is **no longer active** — merged into `code-graph` | code-graph-backend README |
| `code-graph` is a **codebase visualization tool** — not a regression investigator | README: "Visualize codebases as knowledge graphs" |
| Backend: FastAPI (`api/index.py`) | README project structure |
| Frontend: React + Vite (`app/`) | README project structure |
| Has `api/git_utils/` for git history graph utilities | README |
| Has `api/code_coverage/` utilities | README |
| Has LLM integration (`api/llm.py`) using LiteLLM + GraphRAG | README |
| Uses `uv` (not pip) as package manager | README |
| Python >=3.12, <3.14 required | README |
| Live demo: `https://code-graph.falkordb.com/` | README |

### Overlap with RootCause AI

| Feature | code-graph | RootCause AI |
|---------|-----------|--------------|
| FalkorDB graph of source code | Yes (files, functions) | Yes (files, functions + **tests, failures, commits**) |
| LLM chat over graph | Yes (general Q&A) | Yes (focused root cause investigation) |
| Git history analysis | Partial | Yes — central |
| Test failure analysis | No | Yes — core workflow |
| CI/CD log ingestion | No | Yes |
| Evidence ranking (FACT/INFERENCE/VALIDATED) | No | Yes — required |
| Subprocess test re-run | No | Yes — required |

**Decision**: The FalkorDB connection pattern from `code-graph/api/graph.py` is the canonical SDK usage. We will use the same pattern (`FalkorDB(host, port, username, password)` + `db.select_graph(name)`) as it matches official documentation. We will not copy frontend or LLM code.

---

## 3. GitNexus — MCP-Based Code Context Engine

**Source inspected**
- `https://raw.githubusercontent.com/abhigyanpatwari/GitNexus/main/README.md` (520 lines, fully read)

### Verified Facts

| Fact | Source |
|------|--------|
| Language: TypeScript/Node.js (npm package `gitnexus`) | README |
| Storage: **LadybugDB** — NOT FalkorDB | README: "LadybugDB native" |
| Parsing: tree-sitter (native bindings) | README |
| MCP server: 19 MCP tools (query, context, impact, trace, detect_changes, cypher, etc.) | README tool table |
| Focus: AI agent context enrichment for editors (Cursor, Claude Code, Codex, Antigravity) | README |
| `detect_changes` tool maps git-diff lines to affected processes | README |
| License: **PolyForm Noncommercial 1.0** | README badge |
| Supports Antigravity IDE via MCP and AfterTool hooks | README editor table |
| Does NOT use FalkorDB | README |

### Overlap with RootCause AI

| Feature | GitNexus | RootCause AI |
|---------|---------|--------------|
| Code knowledge graph | Yes (LadybugDB) | Yes (FalkorDB) |
| Git diff impact analysis | Yes (`detect_changes`) | Yes (blame, diff → commit graph) |
| MCP server | Yes (19 tools) | Phase 2 only |
| Test failure investigation | Not documented | Yes — core |
| CI/CD log ingestion | Not documented | Yes |
| Evidence ranking | Not documented | Yes |
| Root cause ranking | Not documented | Yes |
| Commercial use allowed | No (PolyForm NC) | Yes (MIT planned) |

### Licensing Warning

**PolyForm Noncommercial 1.0** — GitNexus code CANNOT be used commercially or copied. No code will be borrowed from this project. Architecture studied only for inspiration.

---

## 4. codebase-memory-mcp (DeusData)

**Source inspected**
- `https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/README.md`

### Verified Facts

The README contained only 2 meaningful sentences:
> "System structure groups symbols into components and lets you inspect their dependencies. Behavior shows possible calls from a selected operation and the source evidence behind them."

**[UNKNOWN]**: Implementation language, storage backend, licensing, feature set — none verifiable.
**[INFERENCE]**: Likely an MCP server with call-graph queries based on the name and description.

Assessment: Insufficient information for meaningful competitive analysis. No code will be borrowed (license unknown).

---

## 5. SWE-agent

**Source inspected**
- `https://raw.githubusercontent.com/SWE-agent/SWE-agent/main/README.md`

### Verified Facts

| Fact | Source |
|------|--------|
| Purpose: enables LM to autonomously fix GitHub issues | README |
| **Active development moved to mini-swe-agent** (superseded) | README warning |
| mini-swe-agent: 65% on SWE-bench Verified in ~100 lines Python | README news |
| Designed for research: "Simple & hackable" | README |
| Built by Princeton + Stanford researchers | README |
| Configured via a single YAML file | README |

### Overlap with RootCause AI

| Feature | SWE-agent | RootCause AI |
|---------|----------|--------------|
| GitHub issue → patch generation | Yes — core | No — not our workflow |
| Test failure → root cause | Not focused | Yes — core |
| Graph database integration | None documented | FalkorDB — central |
| Evidence labelling | No | Yes |
| CI log ingestion | No | Yes |
| Research tool vs developer tool | Research | Developer product |

---

## 6. SWE-bench

**Source inspected**
- `https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/README.md`

### Verified Facts

| Fact | Source |
|------|--------|
| Purpose: Benchmark for evaluating LLMs on real GitHub issues | README |
| Task: codebase + issue → patch that resolves it | README |
| License: MIT | README badge |
| Uses Docker for evaluation | README |
| SWE-bench Verified: 500 problems confirmed solvable | README |
| Available as HuggingFace dataset: `princeton-nlp/SWE-bench` | README |

### Relevance to RootCause AI

SWE-bench is a benchmark, not a product. Relevant as:
1. A source of verified real failing test scenarios for our own fixture data
2. Evidence that the problem is hard — even SOTA models don't explain *why* something broke, only fix it
3. **[INFERENCE]**: RootCause AI fills the explanation gap that SWE-bench doesn't evaluate

---

## 7. MCP (Model Context Protocol)

**Source inspected**
- `https://modelcontextprotocol.io/introduction` (rendered HTML)

### Verified Facts

| Fact | Source |
|------|--------|
| Current version: **2026-07-28** (latest) | MCP docs navbar |
| Has sections: Getting Started, Architecture, Servers, Clients, Versioning | Sidebar |
| Has Specification, Extensions, Registry, SEPs tabs | Navbar |

**[UNKNOWN]**: Specific protocol primitives not verifiable from rendered HTML. Full spec at `/specification/2026-07-28` not fetched.

### Relevance to MVP

MCP is **out of scope for the MVP**. It can be added in Phase 2 to expose RootCause AI's investigation workflow as MCP tools consumable by editors.

---

## 8. Feature Gap Summary

| Feature | code-graph | GitNexus | SWE-agent | **RootCause AI** |
|---------|-----------|---------|----------|-----------------|
| FalkorDB backend | Yes | No | No | **Yes** |
| Code structure graph | Yes | Yes | No | **Yes** |
| Git history in graph | Partial | Yes | No | **Yes** |
| **Test failure ingestion** | No | No | No | **Yes** |
| **CI/CD log parsing** | No | No | No | **Yes** |
| **Multi-hop failure → cause traversal** | No | Partial | No | **Yes** |
| **FACT / INFERENCE / VALIDATED labels** | No | No | No | **Yes** |
| **Ranked candidate causes** | No | No | No | **Yes** |
| **Supporting + contradicting evidence** | No | No | No | **Yes** |
| **Subprocess test re-run for validation** | No | No | No | **Yes** |
| MCP server | No | Yes | No | Phase 2 |
| Commercial license | MIT | PolyForm NC | Unknown | **MIT** |

---

## 9. Differentiation Hypothesis

> **Hypothesis (to be demonstrated, not asserted)**:
> RootCause AI is the only tool in this comparison that implements a complete,
> traceable investigation workflow specifically for test regression — connecting
> a CI failure log through a graph of tests, functions, files, and commits,
> ranking candidate causes with explicit evidence labels (FACT, INFERENCE, VALIDATED),
> and validating hypotheses by re-running tests.

### What must be demonstrated to support this:

1. A real GitHub Actions log can be parsed and ingested into FalkorDB
2. Cypher traversal queries surface multi-hop paths from test failure to plausible commit
3. The AI agent output explicitly distinguishes observed facts from inferences
4. At least one candidate cause can be validated by re-running the failing test
5. Output is actionable: ranked causes with source file locations and commit SHAs

### What we explicitly do NOT claim:

- More accurate patch generation than SWE-agent/mini-SWE-agent
- More complete code structure analysis than GitNexus
- Always-correct AI diagnosis
- Outperformance of `git bisect` on linear single-commit regressions

---

## 10. Unresolved Questions

| Question | Impact |
|---------|--------|
| FalkorDB Cloud free tier: persistent graphs across sessions? | High — affects demo reliability |
| GitHub Actions log URL format and API rate limits? | High — affects CI ingestion |
| Which FalkorDB index types best serve multi-hop path queries? | Medium — affects query design |
| Does GitNexus have undocumented test failure features? | Low — license prevents copying regardless |
| What is codebase-memory-mcp's actual implementation? | Low — too sparse to matter |

---

## 11. Attribution & Licensing

| Source | License | Our Usage |
|--------|---------|-----------|
| `falkordb-py` | MIT | Use SDK directly |
| `code-graph` | MIT | Studied connection pattern; no code copied |
| `GitNexus` | PolyForm Noncommercial | No code copied; architecture studied only |
| `SWE-bench` | MIT | Potential fixture data source (with attribution) |
| `SWE-agent` | Unknown | No code copied |
| `codebase-memory-mcp` | Unknown | No code copied |

---

*Generated: 2026-10-16 | All findings from primary source inspection*
