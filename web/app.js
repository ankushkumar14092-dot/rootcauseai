const $ = (id) => document.getElementById(id);

let state = {
  currentFailureId: null,
  activeCommitSha: "a17c9e2",
  activeFunction: "validate_coupon",
  failures: [],
  sampleLogs: [],
  topology: { nodes: [], edges: [] },
  canvasNodes: [],
  canvasEdges: [],
  draggedNode: null,
  selectedNode: null,
};

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "The request could not be completed.");
  }
  return body;
};

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char]
  );
}

// ----------------- View Navigation -----------------

function switchView(viewName) {
  $("welcome").classList.add("hidden");
  $("ingest-view").classList.add("hidden");
  $("results").classList.add("hidden");
  $("visualizer-view").classList.add("hidden");
  $("mcp-view").classList.add("hidden");

  $("nav-investigate").classList.remove("active");
  $("nav-ingest").classList.remove("active");
  $("nav-visualizer").classList.remove("active");
  $("nav-mcp").classList.remove("active");
  $("nav-failures").classList.remove("active");

  if (viewName === "ingest") {
    $("ingest-view").classList.remove("hidden");
    $("nav-ingest").classList.add("active");
    $("crumb-view").textContent = "CI/CD Log Ingestion";
  } else if (viewName === "results") {
    $("results").classList.remove("hidden");
    $("nav-investigate").classList.add("active");
    $("crumb-view").textContent = "Investigation Report";
  } else if (viewName === "visualizer") {
    $("visualizer-view").classList.remove("hidden");
    $("nav-visualizer").classList.add("active");
    $("crumb-view").textContent = "FalkorDB Visualizer";
    initCanvasGraph();
  } else if (viewName === "mcp") {
    $("mcp-view").classList.remove("hidden");
    $("nav-mcp").classList.add("active");
    $("crumb-view").textContent = "MCP Server Hub";
  } else {
    $("welcome").classList.remove("hidden");
    $("nav-investigate").classList.add("active");
    $("crumb-view").textContent = "New investigation";
  }
}

// ----------------- Status & Failures -----------------

async function refreshStatus() {
  try {
    const result = await api("/api/status");
    $("status-dot").className = "status-dot online";
    $("db-label").textContent = `Connected · ${result.nodes} nodes`;
    $("failures-count").textContent = String(result.failures || 0);
  } catch {
    $("status-dot").className = "status-dot offline";
    $("db-label").textContent = "FalkorDB offline · check docker";
  }
}

async function loadFailures() {
  try {
    const data = await api("/api/failures");
    state.failures = data.failures || [];
    renderFailureChips();
    $("failures-count").textContent = String(state.failures.length);
  } catch (e) {
    console.error("Failed to load failures:", e);
  }
}

function renderFailureChips() {
  const container = $("picker-chips");
  if (!container) return;

  if (!state.failures.length) {
    container.innerHTML = '<span class="picker-label">No failures recorded. Ingest a log or reload demo graph.</span>';
    return;
  }

  container.innerHTML = state.failures
    .map(
      (f, idx) => `
    <div class="chip ${f.failure_id === state.currentFailureId || (!state.currentFailureId && idx === 0) ? "active" : ""}"
         data-id="${escapeHtml(f.failure_id)}"
         data-test="${escapeHtml(f.test_id || "")}">
      <span class="chip-dot"></span>
      <span>${escapeHtml(f.test_id || f.failure_id)}</span>
    </div>
  `
    )
    .join("");

  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      container.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.currentFailureId = chip.dataset.id;
      const testName = chip.dataset.test;
      $("prompt").value = `Why did ${testName || state.currentFailureId} fail?`;
      $("prompt-suggestion").textContent = `Selected: ${testName || state.currentFailureId}`;
    });
  });

  if (!state.currentFailureId && state.failures.length) {
    state.currentFailureId = state.failures[0].failure_id;
  }
}

// ----------------- Sample Logs -----------------

async function loadSampleLogs() {
  try {
    const data = await api("/api/sample-logs");
    state.sampleLogs = data.samples || [];
    renderSamplePills();
  } catch (e) {
    console.error("Failed to load sample logs:", e);
  }
}

function renderSamplePills() {
  const container = $("sample-pills");
  if (!container) return;

  container.innerHTML = state.sampleLogs
    .map(
      (s, idx) => `
    <button class="sample-pill ${idx === 0 ? "active" : ""}" data-id="${escapeHtml(s.id)}">
      <span>📄</span> ${escapeHtml(s.title)}
    </button>
  `
    )
    .join("");

  if (state.sampleLogs.length) {
    selectSampleLog(state.sampleLogs[0].id);
  }

  container.querySelectorAll(".sample-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      container.querySelectorAll(".sample-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      selectSampleLog(pill.dataset.id);
    });
  });
}

function selectSampleLog(sampleId) {
  const sample = state.sampleLogs.find((s) => s.id === sampleId);
  if (!sample) return;
  $("ci-log-input").value = sample.log.trim();
  $("repo-input").value = sample.repository || "checkout-service";
}

// ----------------- Ingest CI Log -----------------

async function handleIngest() {
  const rawLog = $("ci-log-input").value.trim();
  const repo = $("repo-input").value.trim() || "checkout-service";
  const btn = $("btn-parse-ingest");

  if (!rawLog) {
    alert("Please enter or paste a CI/CD log first.");
    return;
  }

  btn.disabled = true;
  btn.innerHTML = "<span>Parsing & Ingesting… ◌</span>";

  try {
    const result = await api("/api/ingest/log", {
      method: "POST",
      body: JSON.stringify({ raw_log: rawLog, repository: repo }),
    });

    const summaryCard = $("ingest-summary-card");
    summaryCard.classList.remove("hidden");
    $("ingest-summary-meta").textContent = `Run ${result.run_id} · ${result.workflow} · ${result.repository}`;

    $("ingest-stats-grid").innerHTML = `
      <div class="stat-badge"><div class="stat-num">${result.failures_count}</div><div class="stat-lbl">Failures</div></div>
      <div class="stat-badge"><div class="stat-num">${result.commits_count}</div><div class="stat-lbl">Commits</div></div>
      <div class="stat-badge"><div class="stat-num">${result.nodes_added}</div><div class="stat-lbl">Nodes Merged</div></div>
      <div class="stat-badge"><div class="stat-num">${result.relationships_added}</div><div class="stat-lbl">Edges Linked</div></div>
    `;

    $("parsed-failure-details").innerHTML = (result.failures || [])
      .map(
        (f) => `
      <div class="failure-item-card">
        <div>
          <code>${escapeHtml(f.test_id)}</code>
          <small>${escapeHtml(f.exception)}: ${escapeHtml(f.message)}</small>
          <small>${escapeHtml(f.source_file)}:${f.line} ➔ fn: ${escapeHtml(f.function_name)}</small>
        </div>
      </div>
    `
      )
      .join("");

    state.currentFailureId = result.primary_failure_id;
    if (result.commits && result.commits.length) {
      state.activeCommitSha = result.commits[0].sha;
    }

    $("active-repo-name").textContent = result.repository;
    $("crumb-repo").textContent = result.repository;

    await refreshStatus();
    await loadFailures();
    summaryCard.scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    alert(`Ingestion failed: ${error.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "<span>⚡ Ingest into FalkorDB</span>";
  }
}

// ----------------- Blast Radius Analysis -----------------

async function loadBlastRadius(functionName) {
  try {
    const data = await api(`/api/blast-radius?function_name=${encodeURIComponent(functionName)}`);
    if (!data.ok) return;

    $("blast-risk-badge").textContent = `${data.risk_level} RISK (${data.risk_score} PTS)`;
    $("blast-direct-tests").textContent = String(data.direct_tests.length);
    $("blast-sibling-fns").textContent = String(data.sibling_functions.length);
    $("blast-related-commits").textContent = String(data.related_commits.length);
    $("blast-risk-score").textContent = String(data.risk_score);

    $("blast-recommendation").textContent =
      `Changes to ${functionName}() impact ${data.direct_tests.length} direct test(s) and ${data.indirect_tests.length} indirect test(s) in FalkorDB. ` +
      `Historical incidents: ${data.related_incidents.join(", ") || "none"}.`;
  } catch (e) {
    console.error("Blast radius error:", e);
  }
}

// ----------------- Investigation Report -----------------

function renderInvestigation(result) {
  switchView("results");

  state.currentFailureId = result.failure_id || result.failure?.failure_id;
  const primaryCandidate = result.candidates?.[0];
  if (primaryCandidate?.commit_sha) {
    state.activeCommitSha = primaryCandidate.commit_sha;
  }
  const path = result.paths?.[0];
  if (path?.function_name) {
    state.activeFunction = path.function_name;
    loadBlastRadius(path.function_name);
  }

  $("result-title").textContent = result.failure?.test_id || "Regression Analysis";
  $("answer").textContent = result.answer || result.message;
  $("tool-chip").textContent = `${result.selected_tools?.length || 1} graph tools`;

  $("test-name").textContent = result.failure?.test_id || "Unknown Test";
  $("failure-message").textContent = result.failure?.failure_message || "No message found.";
  $("failure-exception-badge").textContent = result.failure?.exception || "Error";
  $("failure-location").textContent = `${path?.file_path || "source.py"}:${result.failure?.line ?? "?"}`;
  $("run-context-label").textContent = `${result.failure?.failure_id || "CI Run"}`;

  // Traversal Path Strip
  if (path) {
    const nodes = [
      { text: path.exception || "Failure", cls: "fail" },
      { text: path.test_id, cls: "test" },
      { text: `${path.function_name}()`, cls: "fn" },
      { text: path.file_path, cls: "test" },
      ...(path.commit_sha ? [{ text: `Commit ${path.commit_sha}`, cls: "commit" }] : []),
    ];
    $("trace-strip").innerHTML = nodes
      .map(
        (n, idx) =>
          `${idx ? '<span class="trace-arrow">→</span>' : ""}<span class="trace-step ${n.cls}">${escapeHtml(n.text)}</span>`
      )
      .join("");
  } else {
    $("trace-strip").innerHTML = '<span class="trace-step">No connected path</span>';
  }

  // Evidence list
  $("evidence-count").textContent = `${result.evidence?.length || 0} items`;
  $("evidence-list").innerHTML = (result.evidence || [])
    .map(
      (item) => `
    <div class="evidence-item">
      <span class="evidence-tag ${item.kind === "INFERENCE" ? "inference" : ""}">${escapeHtml(item.kind)}</span>
      <div>
        <div class="evidence-text">${escapeHtml(item.text)}</div>
        <span class="evidence-source">SOURCE · ${escapeHtml(item.source)}</span>
      </div>
    </div>
  `
    )
    .join("");

  // Candidate commits list
  $("candidate-list").innerHTML =
    (result.candidates || [])
      .map(
        (item, idx) => `
    <div class="candidate">
      <span class="rank">0${idx + 1}</span>
      <div>
        <code>${escapeHtml(item.commit_sha)}</code>
        <p>${escapeHtml(item.commit_message || "Changed exercised function")}</p>
        <small>${escapeHtml(item.commit_author || "Author")} · ${escapeHtml(item.commit_at || "")}</small>
      </div>
      <span class="score">${item.score} pts</span>
    </div>
  `
      )
      .join("") || '<p class="evidence-text">No changed commits connect to this function in the graph.</p>';

  // Memory & Incidents
  const memory = result.memory || [];
  const incidents = result.related_incidents || [];
  if (memory.length || incidents.length) {
    $("memory-content").innerHTML = [
      ...memory.map(
        (m) => `<div class="memory-date">REMEMBERED · ${escapeHtml(m.at || "")}</div><p>${escapeHtml(m.memory || m.summary)}</p>`
      ),
      ...incidents.map(
        (inc) => `<div class="memory-date">RELATED INCIDENT · ${escapeHtml(inc.incident_id)}</div><p>${escapeHtml(inc.summary)} — <i>${escapeHtml(inc.resolution)}</i></p>`
      ),
    ].join("<br>");
  } else {
    $("memory-content").innerHTML = `<p>Investigation <code>${escapeHtml(result.investigation_id || "new")}</code> and episodic memory were saved to FalkorDB. Ask about history or related incidents to retrieve prior context.</p>`;
  }

  // Reset validation card
  $("validation-result").classList.add("hidden");
  $("validate-button").disabled = false;
  $("validate-btn-text").textContent = `Run isolated check for ${state.activeCommitSha}`;

  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function runInvestigation() {
  const prompt = $("prompt").value.trim() || "Why did the test fail?";
  const btn = $("investigate");
  btn.disabled = true;
  btn.innerHTML = "Tracing graph… <span>◌</span>";

  try {
    const result = await api("/api/investigate", {
      method: "POST",
      body: JSON.stringify({
        prompt: prompt,
        failure_id: state.currentFailureId,
      }),
    });
    renderInvestigation(result);
  } catch (error) {
    alert(error.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Investigate <span>↗</span>";
  }
}

async function runValidation() {
  const btn = $("validate-button");
  const output = $("validation-result");
  btn.disabled = true;
  $("validate-btn-text").textContent = "Running isolated check in sandbox…";

  try {
    const result = await api("/api/validate", {
      method: "POST",
      body: JSON.stringify({ commit_sha: state.activeCommitSha }),
    });

    output.textContent = `${result.status.toUpperCase()} · ${result.output}`;
    output.classList.toggle("fail", result.status !== "passed");
    output.classList.remove("hidden");
    $("validate-btn-text").textContent =
      result.status === "passed" ? "Hypothesis validated ✓" : "Check completed";
  } catch (error) {
    output.textContent = error.message;
    output.classList.add("fail");
    output.classList.remove("hidden");
    $("validate-btn-text").textContent = "Check failed to run";
  } finally {
    btn.disabled = false;
  }
}

async function seedDemoGraph() {
  const btn = $("seed-link");
  btn.textContent = "Loading demo graph…";
  btn.disabled = true;
  try {
    const result = await api("/api/seed", { method: "POST", body: "{}" });
    btn.textContent = `Loaded ${result.nodes} graph nodes`;
    state.currentFailureId = "failure-1842-1";
    state.activeCommitSha = "a17c9e2";
    state.activeFunction = "validate_coupon";
    $("active-repo-name").textContent = "checkout-service";
    $("crumb-repo").textContent = "checkout-service";
    await refreshStatus();
    await loadFailures();
  } catch (error) {
    btn.textContent = error.message;
  } finally {
    btn.disabled = false;
  }
}

// ----------------- Interactive Canvas Graph Visualizer -----------------

const COLOR_MAP = {
  Failure: "#f47e8b",
  Test: "#9486ff",
  Function: "#83d9b1",
  File: "#6ed0e0",
  Commit: "#e9b86d",
  Incident: "#70a5ff",
  TestRun: "#b5b0db",
  Repository: "#d9d8e5",
  AgentMemory: "#54b890",
  Investigation: "#a695e2",
  Validation: "#e09f58",
  Node: "#888899",
};

async function initCanvasGraph() {
  const canvas = $("graph-canvas");
  if (!canvas) return;

  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = rect.height * window.devicePixelRatio;
  const ctx = canvas.getContext("2d");
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  try {
    const data = await api("/api/graph-topology");
    state.topology = data;

    // Layout nodes in circular/orbital distribution
    const width = rect.width;
    const height = rect.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.38;

    state.canvasNodes = data.nodes.map((n, i) => {
      const angle = (i / data.nodes.length) * 2 * Math.PI;
      const r = radius * (0.6 + 0.4 * (i % 3));
      return {
        ...n,
        x: centerX + Math.cos(angle) * r,
        y: centerY + Math.sin(angle) * r,
        radius: n.label === "Failure" ? 18 : n.label === "Test" ? 16 : 14,
        color: COLOR_MAP[n.label] || COLOR_MAP.Node,
      };
    });

    drawGraph(canvas, ctx);
    setupCanvasInteractivity(canvas, ctx);
  } catch (e) {
    console.error("Failed to load graph topology:", e);
  }
}

function drawGraph(canvas, ctx) {
  const width = canvas.width / window.devicePixelRatio;
  const height = canvas.height / window.devicePixelRatio;
  ctx.clearRect(0, 0, width, height);

  // Draw edges
  ctx.lineWidth = 1;
  state.topology.edges.forEach((e) => {
    const srcNode = state.canvasNodes.find((n) => n.id === e.source_name || n.name === e.source_name);
    const tgtNode = state.canvasNodes.find((n) => n.id === e.target_name || n.name === e.target_name);
    if (!srcNode || !tgtNode) return;

    ctx.beginPath();
    ctx.moveTo(srcNode.x, srcNode.y);
    ctx.lineTo(tgtNode.x, tgtNode.y);
    ctx.strokeStyle = "#272838";
    ctx.stroke();

    // Relationship label at edge midpoint
    const midX = (srcNode.x + tgtNode.x) / 2;
    const midY = (srcNode.y + tgtNode.y) / 2;
    ctx.font = "8px 'DM Mono'";
    ctx.fillStyle = "#5d5c6f";
    ctx.textAlign = "center";
    ctx.fillText(`[:${e.rel_type}]`, midX, midY - 3);
  });

  // Draw nodes
  state.canvasNodes.forEach((node) => {
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
    ctx.fillStyle = node === state.selectedNode ? "#ffffff" : node.color;
    ctx.fill();

    ctx.lineWidth = node === state.selectedNode ? 3 : 1.5;
    ctx.strokeStyle = "#12131a";
    ctx.stroke();

    // Node text
    ctx.font = "10px 'DM Sans', sans-serif";
    ctx.fillStyle = "#dedce8";
    ctx.textAlign = "center";
    const shortName = String(node.name).split("/").pop().slice(0, 16);
    ctx.fillText(shortName, node.x, node.y + node.radius + 12);
  });
}

function setupCanvasInteractivity(canvas, ctx) {
  canvas.onmousedown = (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const clicked = state.canvasNodes.find(
      (n) => Math.hypot(n.x - mouseX, n.y - mouseY) <= n.radius + 4
    );

    if (clicked) {
      state.draggedNode = clicked;
      state.selectedNode = clicked;
      inspectNode(clicked);
      drawGraph(canvas, ctx);
    }
  };

  canvas.onmousemove = (e) => {
    if (!state.draggedNode) return;
    const rect = canvas.getBoundingClientRect();
    state.draggedNode.x = e.clientX - rect.left;
    state.draggedNode.y = e.clientY - rect.top;
    drawGraph(canvas, ctx);
  };

  window.onmouseup = () => {
    state.draggedNode = null;
  };
}

function inspectNode(node) {
  $("inspector-node-title").textContent = `${node.label}: ${node.name}`;
  $("inspector-node-desc").textContent = node.details || `Recorded ${node.label} entity in FalkorDB graph.`;

  const connectedEdges = state.topology.edges.filter(
    (e) => e.source_name === node.name || e.target_name === node.name
  );

  $("inspector-props").innerHTML = `
    <div class="prop-badge"><b>Label</b><span>${escapeHtml(node.label)}</span></div>
    <div class="prop-badge"><b>Identifier</b><span>${escapeHtml(node.id)}</span></div>
    <div class="prop-badge"><b>Relationships (${connectedEdges.length})</b>
      <span>${connectedEdges.map((e) => `${e.source_name} ➔ [${e.rel_type}] ➔ ${e.target_name}`).join("<br>") || "None"}</span>
    </div>
  `;
}

// ----------------- Initialization -----------------

document.addEventListener("DOMContentLoaded", async () => {
  // Navigation event listeners
  $("nav-investigate").addEventListener("click", () => switchView("welcome"));
  $("nav-ingest").addEventListener("click", () => switchView("ingest"));
  $("nav-visualizer").addEventListener("click", () => switchView("visualizer"));
  $("nav-mcp").addEventListener("click", () => switchView("mcp"));
  $("nav-failures").addEventListener("click", () => {
    switchView("welcome");
    $("failure-picker-container")?.scrollIntoView({ behavior: "smooth" });
  });

  $("header-visualizer-btn").addEventListener("click", () => switchView("visualizer"));
  $("header-mcp-btn").addEventListener("click", () => switchView("mcp"));
  $("header-ingest-btn").addEventListener("click", () => switchView("ingest"));

  $("back-to-investigate").addEventListener("click", () => switchView("welcome"));
  $("new-investigation").addEventListener("click", () => switchView("welcome"));
  $("ingest-another-btn").addEventListener("click", () => switchView("ingest"));
  $("view-in-graph-btn").addEventListener("click", () => switchView("visualizer"));
  $("back-from-graph-btn").addEventListener("click", () => switchView("welcome"));
  $("back-from-mcp-btn").addEventListener("click", () => switchView("welcome"));
  $("refresh-graph-btn").addEventListener("click", initCanvasGraph);

  // Investigation & validation buttons
  $("investigate").addEventListener("click", runInvestigation);
  $("validate-button").addEventListener("click", runValidation);
  $("btn-parse-ingest").addEventListener("click", handleIngest);
  $("btn-investigate-ingested").addEventListener("click", () => {
    switchView("welcome");
    runInvestigation();
  });

  $("seed-link").addEventListener("click", seedDemoGraph);
  $("refresh-status").addEventListener("click", refreshStatus);
  $("clear-log-btn").addEventListener("click", () => {
    $("ci-log-input").value = "";
  });

  $("copy-mcp-btn").addEventListener("click", () => {
    const config = `{
  "mcpServers": {
    "rootcause-ai": {
      "command": "python3",
      "args": ["-m", "app.mcp_server"],
      "cwd": "${window.location.origin}"
    }
  }
}`;
    navigator.clipboard.writeText(config);
    $("copy-mcp-btn").textContent = "Copied ✓";
    setTimeout(() => {
      $("copy-mcp-btn").textContent = "Copy JSON";
    }, 2000);
  });

  // Prompt enter key
  $("prompt").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      runInvestigation();
    }
  });

  // Graph dialog
  const dialog = $("graph-dialog");
  $("open-graph").addEventListener("click", () => dialog.showModal());
  $("help-button").addEventListener("click", () => dialog.showModal());
  $("close-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });

  // Initial load
  await refreshStatus();
  await loadFailures();
  await loadSampleLogs();
});
