const API_BASE = "http://localhost:8000";
const MAX_RENDER_LINES_PER_PANE = 500;
const JOB_POLL_INTERVAL_MS = 1000;
const JOB_MAX_WAIT_MS = 15 * 60 * 1000;

let allChanges = [];
let changeLookup = {};
let appliedChanges = new Set();
let cancelledChanges = new Set();
const codeChangesState = {
  query: "",
  page: 1,
  pageSize: 25,
  filteredChanges: [],
  emptyMessage: "No code changes available."
};
const staticChecksState = {
  raw: null,
  running: false,
  runStateText: "Idle",
  steps: [],
  issuesQuery: "",
  issuesPage: 1,
  issuesPageSize: 25,
  commandsQuery: "",
  commandsPage: 1,
  commandsPageSize: 10
};
const usageMonitorState = {
  enabled: false,
  latestRequestUsage: []
};

document.addEventListener("DOMContentLoaded", () => {
  initializeMarkdownRenderer();
  initializeTheme();
  bindListControlEvents();
  bindUsageMonitorToggle();
  renderStaticCheckRunState();
});

async function runReview() {
  const logs = document.getElementById("logs");
  const aiReview = document.getElementById("aiReview");
  const shouldRunStaticChecks = document.getElementById("runStaticChecks")?.checked;
  const codeSearch = document.getElementById("codeChangesSearch");
  logs.textContent = "Starting review process...\n";
  aiReview.innerHTML = "";
  codeChangesState.query = "";
  codeChangesState.page = 1;
  if (codeSearch) {
    codeSearch.value = "";
  }
  displayCodeChanges([], { emptyMessage: "No code changes available." });

  try {
    const payload = {
      repo_path: document.getElementById("repoPath").value,
      ai_model: document.getElementById("aiModel").value,
      max_tokens: Number(document.getElementById("maxTokens").value),
      organization: document.getElementById("organization").value,
      project: document.getElementById("project").value,
      repository_name: document.getElementById("repository").value,
      pull_request_id: document.getElementById("prId").value,
      azure_pat: document.getElementById("password").value,
      is_local: document.getElementById("isLocal").checked
    };

    logs.textContent += "Collecting PR diffs and generating required fixes...\n";
    const fullReviewData = await apiPostAsyncJob("/api/run-full-review", payload, {
      label: "run-full-review",
      onProgress: createJobProgressLogger(logs, "Full review job")
    });
    recordLatestUsage(fullReviewData?.usage);
    logs.textContent += `OK Full review completed (${fullReviewData?.token_estimate || 0} tokens estimated)\n`;
    aiReview.innerHTML = renderMarkdown(fullReviewData?.review || "");

    const requiredChanges = Array.isArray(fullReviewData?.code_changes) ? fullReviewData.code_changes : [];
    const noChangesRequired = Boolean(fullReviewData?.no_changes_required) || requiredChanges.length === 0;
    const relaxedFilter = Boolean(fullReviewData?.filter_relaxed_to_include_generated);
    if (noChangesRequired) {
      logs.textContent += "No required changes detected for the current PR diff.\n";
      displayCodeChanges(requiredChanges, {
        emptyMessage: "No required changes needed for this PR diff."
      });
    } else {
      logs.textContent += `OK Required code changes generated (${requiredChanges.length})\n`;
      if (relaxedFilter) {
        logs.textContent += "Note: showing generated suggestions after relaxing strict required-only filter.\n";
      }
      displayCodeChanges(requiredChanges, {
        emptyMessage: "No required changes needed for this PR diff."
      });
    }

    if (shouldRunStaticChecks) {
      logs.textContent += "Running static checks...\n";
      await runStaticChecks({
        repoPath: payload.repo_path,
        scope: "changed",
        reviewContext: payload
      });
      logs.textContent += "OK Static checks completed\n";
    }

    if (usageMonitorState.enabled) {
      await refreshUsageMetrics();
    }
  } catch (error) {
    logs.textContent += `\nError: ${error.message}\n`;
    showToast(`Error: ${error.message}`, "error");
  }
}

async function runStaticChecksOnly() {
  const logs = document.getElementById("logs");
  const payload = {
    repo_path: document.getElementById("repoPath").value,
    organization: document.getElementById("organization").value,
    project: document.getElementById("project").value,
    repository_name: document.getElementById("repository").value,
    pull_request_id: document.getElementById("prId").value,
    azure_pat: document.getElementById("password").value,
    is_local: document.getElementById("isLocal").checked
  };
  logs.textContent += "Running static checks...\n";
  try {
    await runStaticChecks({
      repoPath: payload.repo_path,
      scope: "repo",
      reviewContext: payload
    });
    logs.textContent += "OK Static checks completed\n";
  } catch (error) {
    logs.textContent += `Error running static checks: ${error.message}\n`;
    showToast(`Static checks failed: ${error.message}`, "error");
  }
}

function bindUsageMonitorToggle() {
  const toggle = document.getElementById("showUsageMonitor");
  const section = document.getElementById("usageMonitorSection");
  if (!toggle || !section) {
    return;
  }

  toggle.addEventListener("change", async () => {
    usageMonitorState.enabled = Boolean(toggle.checked);
    if (usageMonitorState.enabled) {
      section.classList.remove("hidden");
      await refreshUsageMetrics();
    } else {
      section.classList.add("hidden");
    }
  });
}

function recordLatestUsage(usage) {
  if (!usage || typeof usage !== "object") {
    return;
  }
  usageMonitorState.latestRequestUsage.unshift(usage);
  usageMonitorState.latestRequestUsage = usageMonitorState.latestRequestUsage.slice(0, 20);
}

async function refreshUsageMetrics() {
  if (!usageMonitorState.enabled) {
    return;
  }
  const data = await apiGet("/api/usage-metrics");
  renderUsageMetrics(data);
}

function renderUsageMetrics(data) {
  const summary = data?.summary || {};
  const recentFromServer = Array.isArray(data?.recent_requests) ? data.recent_requests : [];
  const recent = usageMonitorState.latestRequestUsage.length
    ? mergeRecentRequests(usageMonitorState.latestRequestUsage, recentFromServer)
    : recentFromServer;

  const requestSummary = document.getElementById("usageRequestSummary");
  const tokenFill = document.getElementById("tokenMeterFill");
  const tokenLabel = document.getElementById("tokenMeterLabel");
  const costFill = document.getElementById("costMeterFill");
  const costLabel = document.getElementById("costMeterLabel");
  const recentContainer = document.getElementById("usageRecentRequests");

  if (!requestSummary || !tokenFill || !tokenLabel || !costFill || !costLabel || !recentContainer) {
    return;
  }

  const summaryCards = [
    { label: "Requests", value: `${summary.request_count || 0}` },
    { label: "Total Tokens", value: `${summary.total_tokens_used || 0}` },
    { label: "Total Cost (Est.)", value: `$${Number(summary.total_estimated_cost_usd || 0).toFixed(4)}` },
    { label: "Tokens Remaining", value: `${summary.token_budget_remaining || 0}` },
    { label: "Cost Remaining", value: `$${Number(summary.cost_budget_remaining_usd || 0).toFixed(4)}` }
  ];

  requestSummary.innerHTML = "";
  summaryCards.forEach((item) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<div class="summary-label">${item.label}</div><div class="summary-value">${item.value}</div>`;
    requestSummary.appendChild(card);
  });

  const tokenPercent = Number(summary.token_budget_used_percent || 0);
  const costPercent = Number(summary.cost_budget_used_percent || 0);
  tokenFill.style.width = `${Math.min(Math.max(tokenPercent, 0), 100)}%`;
  costFill.style.width = `${Math.min(Math.max(costPercent, 0), 100)}%`;
  tokenLabel.textContent = `${tokenPercent.toFixed(2)}%`;
  costLabel.textContent = `${costPercent.toFixed(2)}%`;

  recentContainer.innerHTML = "";
  if (!recent.length) {
    recentContainer.innerHTML = `<p class="muted-text">No AI requests recorded yet.</p>`;
    return;
  }

  recent.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "command-item";
    item.innerHTML = `
      <div class="command-head">
        <span class="command-tool">${entry.endpoint || "unknown endpoint"} (${entry.model || "unknown model"})</span>
        <span class="command-status ok">${entry.tokens_used || 0} tokens</span>
      </div>
      <div class="command-meta">estimated cost: $${Number(entry.estimated_cost_usd || 0).toFixed(6)}</div>
    `;
    recentContainer.appendChild(item);
  });
}

function mergeRecentRequests(clientRecent, serverRecent) {
  const merged = [...clientRecent, ...serverRecent];
  const seen = new Set();
  const unique = [];
  merged.forEach((item) => {
    const key = `${item.timestamp || ""}-${item.endpoint || ""}-${item.tokens_used || ""}-${item.model || ""}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    unique.push(item);
  });
  return unique.slice(0, 20);
}

async function runStaticChecks(options) {
  const repoPath = options?.repoPath;
  const scope = options?.scope || "repo";
  const reviewContext = options?.reviewContext || {};
  const logs = document.getElementById("logs");
  startStaticCheckRun();
  completeStaticCheckStep("Preparing static check request payload");
  beginStaticCheckStep("Sending static check request to backend");

  try {
    const data = await apiPostAsyncJob("/api/static-checks", {
      repo_path: repoPath,
      scope,
      organization: reviewContext.organization,
      project: reviewContext.project,
      repository_name: reviewContext.repository_name,
      pull_request_id: reviewContext.pull_request_id,
      azure_pat: reviewContext.azure_pat,
      is_local: reviewContext.is_local
    }, {
      label: "static-checks",
      onProgress: createJobProgressLogger(logs, "Static checks job")
    });
    completeStaticCheckStep("Sending static check request to backend");
    beginStaticCheckStep("Parsing command outputs and critical failures");
    renderStaticChecks(data);
    completeStaticCheckStep("Parsing command outputs and critical failures");
    finishStaticCheckRun(`Completed. Critical failures: ${countCriticalIssues(data)}.`);
    return data;
  } catch (error) {
    failStaticCheckRun(error.message || "Static checks failed");
    throw error;
  }
}

function renderStaticChecks(data) {
  const summaryElement = document.getElementById("staticChecksSummary");
  const majorIssuesElement = document.getElementById("staticChecksMajorIssues");
  const issuesElement = document.getElementById("staticChecksIssues");
  const commandsElement = document.getElementById("staticChecksCommands");
  const outputElement = document.getElementById("staticChecksOutput");

  if (!summaryElement || !majorIssuesElement || !issuesElement || !commandsElement || !outputElement) {
    return;
  }

  staticChecksState.raw = data || {};
  staticChecksState.issuesPage = 1;
  staticChecksState.commandsPage = 1;

  const summary = staticChecksState.raw?.summary || {};
  const languages = Array.isArray(staticChecksState.raw?.languages_detected)
    ? staticChecksState.raw.languages_detected
    : [];
  const allIssues = Array.isArray(staticChecksState.raw?.issues) ? staticChecksState.raw.issues : [];
  const criticalIssues = allIssues.filter((issue) => (issue?.severity || "").toLowerCase() === "critical");

  summaryElement.innerHTML = "";
  const summaryCards = [
    { label: "Languages", value: languages.length ? languages.join(", ") : "none" },
    { label: "Commands", value: `${summary.commands_total || 0}` },
    { label: "Failed Commands", value: `${summary.commands_failed || 0}` },
    { label: "Critical Issues", value: `${summary.issues_critical || 0}` },
    { label: "Total Issues", value: `${summary.issues_total || 0}` },
    { label: "Duration", value: `${summary.duration_ms || 0} ms` }
  ];
  summaryCards.forEach((item) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<div class="summary-label">${item.label}</div><div class="summary-value">${item.value}</div>`;
    summaryElement.appendChild(card);
  });

  majorIssuesElement.innerHTML = `<h3>Critical Failures</h3>`;
  if (!criticalIssues.length) {
    majorIssuesElement.innerHTML += `<p class="muted-text">No critical failures found.</p>`;
  } else {
    majorIssuesElement.appendChild(buildIssuesTable(criticalIssues, { showOnlyCriticalStyling: true }));
  }
  renderStaticIssuesList();
  renderStaticCommandsList();
  outputElement.textContent = JSON.stringify(staticChecksState.raw, null, 2);
}

function buildIssuesTable(issues, options = {}) {
  const table = document.createElement("table");
  table.className = "issues-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Severity</th>
        <th>Language</th>
        <th>Tool</th>
        <th>File</th>
        <th>Line</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;

  const tbody = table.querySelector("tbody");
  issues.forEach((issue) => {
    const row = document.createElement("tr");
    const severity = (issue.severity || "").toLowerCase();
    if (severity === "critical" || severity === "high") {
      row.classList.add("issue-row-major");
    }
    if (severity === "critical") {
      row.classList.add("issue-row-critical");
    }
    row.innerHTML = `
      <td><span class="issue-severity ${issue.severity}">${issue.severity}</span></td>
      <td>${issue.language || ""}</td>
      <td>${issue.tool || ""}</td>
      <td title="${issue.file || ""}">${issue.file || ""}</td>
      <td>${issue.line || ""}</td>
      <td>${issue.message || ""}</td>
    `;
    tbody.appendChild(row);
  });

  if (options.showOnlyCriticalStyling) {
    table.classList.add("issues-table-major");
  }

  return table;
}

function renderStaticIssuesList() {
  const issuesElement = document.getElementById("staticChecksIssues");
  const paginationElement = document.getElementById("staticIssuesPagination");
  const allIssues = Array.isArray(staticChecksState.raw?.issues) ? staticChecksState.raw.issues : [];
  if (!issuesElement || !paginationElement) {
    return;
  }

  const criticalOnly = allIssues.filter((issue) => (issue?.severity || "").toLowerCase() === "critical");
  const query = (staticChecksState.issuesQuery || "").trim().toLowerCase();
  const filtered = criticalOnly.filter((issue) => matchStaticIssue(issue, query));
  const pageData = paginateItems(filtered, staticChecksState.issuesPage, staticChecksState.issuesPageSize);
  staticChecksState.issuesPage = pageData.page;

  issuesElement.innerHTML = "";
  if (!filtered.length) {
    issuesElement.innerHTML = `<p class="muted-text">No critical issues found for the current filter.</p>`;
  } else {
    issuesElement.appendChild(buildIssuesTable(pageData.items));
  }

  renderPagination(
    paginationElement,
    pageData.page,
    pageData.totalPages,
    filtered.length,
    staticChecksState.issuesPageSize,
    (nextPage) => {
      staticChecksState.issuesPage = nextPage;
      renderStaticIssuesList();
    }
  );
}

function renderStaticCommandsList() {
  const commandsElement = document.getElementById("staticChecksCommands");
  const paginationElement = document.getElementById("staticCommandsPagination");
  const commands = Array.isArray(staticChecksState.raw?.commands) ? staticChecksState.raw.commands : [];
  if (!commandsElement || !paginationElement) {
    return;
  }

  const query = (staticChecksState.commandsQuery || "").trim().toLowerCase();
  const filtered = commands.filter((command) => matchStaticCommand(command, query));
  const pageData = paginateItems(filtered, staticChecksState.commandsPage, staticChecksState.commandsPageSize);
  staticChecksState.commandsPage = pageData.page;

  commandsElement.innerHTML = "";
  if (!filtered.length) {
    commandsElement.innerHTML = `<p class="muted-text">No commands found for the current filter.</p>`;
  } else {
    pageData.items.forEach((command) => {
      const item = document.createElement("div");
      item.className = "command-item";
      item.innerHTML = `
        <div class="command-head">
          <span class="command-tool">${command.language} / ${command.tool}</span>
          <span class="command-status ${command.status}">${command.status}</span>
        </div>
        <div class="command-line">${command.command}</div>
        <div class="command-meta">exit=${command.return_code}, duration=${command.duration_ms} ms</div>
      `;
      commandsElement.appendChild(item);
    });
  }

  renderPagination(
    paginationElement,
    pageData.page,
    pageData.totalPages,
    filtered.length,
    staticChecksState.commandsPageSize,
    (nextPage) => {
      staticChecksState.commandsPage = nextPage;
      renderStaticCommandsList();
    }
  );
}

function bindListControlEvents() {
  const codeSearch = document.getElementById("codeChangesSearch");
  const codePageSize = document.getElementById("codeChangesPageSize");
  const issuesSearch = document.getElementById("staticIssuesSearch");
  const issuesPageSize = document.getElementById("staticIssuesPageSize");
  const commandsSearch = document.getElementById("staticCommandsSearch");
  const commandsPageSize = document.getElementById("staticCommandsPageSize");

  if (codeSearch) {
    codeSearch.addEventListener("input", (event) => {
      codeChangesState.query = event.target.value || "";
      codeChangesState.page = 1;
      renderCodeChangesList();
    });
  }
  if (codePageSize) {
    codePageSize.addEventListener("change", (event) => {
      codeChangesState.pageSize = Number(event.target.value || 25);
      codeChangesState.page = 1;
      renderCodeChangesList();
    });
  }

  if (issuesSearch) {
    issuesSearch.addEventListener("input", (event) => {
      staticChecksState.issuesQuery = event.target.value || "";
      staticChecksState.issuesPage = 1;
      renderStaticIssuesList();
    });
  }
  if (issuesPageSize) {
    issuesPageSize.addEventListener("change", (event) => {
      staticChecksState.issuesPageSize = Number(event.target.value || 25);
      staticChecksState.issuesPage = 1;
      renderStaticIssuesList();
    });
  }

  if (commandsSearch) {
    commandsSearch.addEventListener("input", (event) => {
      staticChecksState.commandsQuery = event.target.value || "";
      staticChecksState.commandsPage = 1;
      renderStaticCommandsList();
    });
  }
  if (commandsPageSize) {
    commandsPageSize.addEventListener("change", (event) => {
      staticChecksState.commandsPageSize = Number(event.target.value || 10);
      staticChecksState.commandsPage = 1;
      renderStaticCommandsList();
    });
  }
}

function paginateItems(items, page, pageSize) {
  const safePageSize = Math.max(1, Number(pageSize) || 25);
  const totalPages = Math.max(1, Math.ceil(items.length / safePageSize));
  const safePage = Math.min(Math.max(1, Number(page) || 1), totalPages);
  const start = (safePage - 1) * safePageSize;
  const end = start + safePageSize;
  return {
    items: items.slice(start, end),
    page: safePage,
    totalPages
  };
}

function renderPagination(element, page, totalPages, totalItems, pageSize, onPageChange) {
  element.innerHTML = "";
  const wrapper = document.createElement("div");
  wrapper.className = "pagination";
  wrapper.innerHTML = `
    <button class="page-btn" ${page <= 1 ? "disabled" : ""}>Prev</button>
    <span class="page-text">Page ${page} / ${totalPages} (${totalItems} items, ${pageSize}/page)</span>
    <button class="page-btn" ${page >= totalPages ? "disabled" : ""}>Next</button>
  `;

  const [prevButton, nextButton] = wrapper.querySelectorAll(".page-btn");
  prevButton?.addEventListener("click", () => onPageChange(page - 1));
  nextButton?.addEventListener("click", () => onPageChange(page + 1));
  element.appendChild(wrapper);
}

function matchStaticIssue(issue, query) {
  if (!query) {
    return true;
  }
  const haystack = [
    issue?.severity || "",
    issue?.language || "",
    issue?.tool || "",
    issue?.file || "",
    issue?.line || "",
    issue?.message || ""
  ]
    .join("\n")
    .toLowerCase();
  return haystack.includes(query);
}

function matchStaticCommand(command, query) {
  if (!query) {
    return true;
  }
  const haystack = [
    command?.language || "",
    command?.tool || "",
    command?.status || "",
    command?.command || "",
    command?.stdout || "",
    command?.stderr || ""
  ]
    .join("\n")
    .toLowerCase();
  return haystack.includes(query);
}

function countCriticalIssues(data) {
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  return issues.filter((issue) => (issue?.severity || "").toLowerCase() === "critical").length;
}

function startStaticCheckRun() {
  staticChecksState.running = true;
  staticChecksState.steps = [];
  staticChecksState.runStateText = "Running static checks...";
  renderStaticCheckRunState();
}

function beginStaticCheckStep(label) {
  staticChecksState.steps.push({ label, status: "running" });
  renderStaticCheckRunState();
}

function completeStaticCheckStep(label) {
  const lastRunning = [...staticChecksState.steps].reverse().find((step) => step.status === "running");
  if (lastRunning) {
    lastRunning.status = "done";
  } else if (label) {
    staticChecksState.steps.push({ label, status: "done" });
  }
  renderStaticCheckRunState();
}

function finishStaticCheckRun(message) {
  const lastRunning = [...staticChecksState.steps].reverse().find((step) => step.status === "running");
  if (lastRunning) {
    lastRunning.status = "done";
  }
  staticChecksState.running = false;
  staticChecksState.runStateText = message || "Completed.";
  renderStaticCheckRunState();
}

function failStaticCheckRun(message) {
  const lastRunning = [...staticChecksState.steps].reverse().find((step) => step.status === "running");
  if (lastRunning) {
    lastRunning.status = "failed";
  }
  staticChecksState.running = false;
  staticChecksState.runStateText = `Failed: ${message || "Unknown error"}`;
  renderStaticCheckRunState();
}

function renderStaticCheckRunState() {
  const spinner = document.getElementById("staticChecksSpinner");
  const runState = document.getElementById("staticChecksRunState");
  const stepsElement = document.getElementById("staticChecksSteps");
  if (!spinner || !runState || !stepsElement) {
    return;
  }

  if (staticChecksState.running) {
    spinner.classList.remove("hidden");
  } else {
    spinner.classList.add("hidden");
  }
  runState.textContent = staticChecksState.runStateText;

  stepsElement.innerHTML = "";
  staticChecksState.steps.forEach((step) => {
    const item = document.createElement("li");
    item.className = `step-item ${step.status}`;
    item.textContent = step.label;
    stepsElement.appendChild(item);
  });
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (body?.detail?.message) {
        detail = body.detail.message;
        if (body.detail.diagnostics && typeof body.detail.diagnostics === "object") {
          const diagnostics = body.detail.diagnostics;
          const requested = diagnostics.requested_start_line;
          const removed = diagnostics.removed_line_count;
          const existing = diagnostics.existing_preview;
          const expected = diagnostics.expected_preview;
          const diagnosticsParts = [];
          if (requested !== undefined) diagnosticsParts.push(`requested_start_line=${requested}`);
          if (removed !== undefined) diagnosticsParts.push(`removed_line_count=${removed}`);
          if (existing) diagnosticsParts.push(`existing_preview=${existing}`);
          if (expected) diagnosticsParts.push(`expected_preview=${expected}`);
          if (diagnosticsParts.length) {
            detail = `${detail} (${diagnosticsParts.join("; ")})`;
          }
        }
      } else if (body?.detail && typeof body.detail === "object") {
        detail = JSON.stringify(body.detail);
      } else {
        detail = body?.detail || detail;
      }
    } catch (_) {}
    throw new Error(detail);
  }

  return response.json();
}

async function apiPostAsyncJob(path, payload, options = {}) {
  const response = await apiPost(`${path}?async_job=true`, payload);
  if (!response?.job_id) {
    return response;
  }
  return waitForJobCompletion(response, options);
}

async function waitForJobCompletion(jobMetadata, options = {}) {
  const label = options?.label || "job";
  const pollPath = jobMetadata?.poll_url || `/api/jobs/${jobMetadata?.job_id || ""}`;
  const startedAt = Date.now();
  const onProgress = typeof options?.onProgress === "function" ? options.onProgress : null;

  if (!pollPath || !jobMetadata?.job_id) {
    throw new Error("Invalid async job response: missing job_id or poll_url.");
  }

  while (Date.now() - startedAt < JOB_MAX_WAIT_MS) {
    const job = await apiGet(pollPath);
    if (onProgress) {
      onProgress(job);
    }

    const status = String(job?.status || "").toLowerCase();
    if (status === "succeeded") {
      return job?.result || {};
    }
    if (status === "failed") {
      const detail = job?.error?.message || `Async ${label} failed.`;
      throw new Error(detail);
    }

    await delay(JOB_POLL_INTERVAL_MS);
  }

  throw new Error(`Timed out waiting for async ${label} job.`);
}

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" }
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

function createJobProgressLogger(logTarget, title) {
  let lastStatus = "";
  return (job) => {
    if (!logTarget || !job) {
      return;
    }
    const status = String(job?.status || "unknown").toLowerCase();
    if (status === lastStatus) {
      return;
    }
    lastStatus = status;
    const jobId = job?.job_id || "unknown";
    logTarget.textContent += `${title}: ${status} (${jobId})\n`;
  };
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function displayCodeChanges(changes, options = {}) {
  const container = document.getElementById("codeChanges");
  if (!container) {
    return;
  }

  const normalized = Array.isArray(changes) ? changes : changes ? [changes] : [];
  allChanges = normalized;
  changeLookup = {};
  appliedChanges = new Set();
  cancelledChanges = new Set();
  codeChangesState.page = 1;
  codeChangesState.emptyMessage = options?.emptyMessage || "No code changes available.";
  renderCodeChangesList();
}

function renderCodeChangesList() {
  const container = document.getElementById("codeChanges");
  const paginationElement = document.getElementById("codeChangesPagination");
  if (!container || !paginationElement) {
    return;
  }

  const query = (codeChangesState.query || "").trim().toLowerCase();
  codeChangesState.filteredChanges = allChanges
    .map((change, index) => ({ change, index }))
    .filter((entry) => matchCodeChange(entry.change, query));

  const pageData = paginateItems(
    codeChangesState.filteredChanges,
    codeChangesState.page,
    codeChangesState.pageSize
  );
  codeChangesState.page = pageData.page;

  container.innerHTML = "";
  if (!codeChangesState.filteredChanges.length) {
    const emptyTemplate = document.getElementById("emptyChangesTemplate");
    const emptyNode = emptyTemplate.content.cloneNode(true);
    const message = emptyNode.querySelector("p");
    if (message) {
      message.textContent = codeChangesState.emptyMessage || "No code changes available.";
    }
    container.appendChild(emptyNode);
  } else {
    pageData.items.forEach((entry) => {
      const filePath = entry.change?.diff?.file_path || "Unknown file";
      container.appendChild(renderChangeItem(entry.change, filePath, entry.index));
    });
  }

  renderPagination(
    paginationElement,
    pageData.page,
    pageData.totalPages,
    codeChangesState.filteredChanges.length,
    codeChangesState.pageSize,
    (nextPage) => {
      codeChangesState.page = nextPage;
      renderCodeChangesList();
    }
  );
}

function matchCodeChange(change, query) {
  if (!query) {
    return true;
  }
  const diff = change?.diff || {};
  const haystack = [
    diff.file_path || "",
    diff.change_type || "",
    diff.old_content || "",
    diff.new_content || "",
    change?.explanation || "",
    change?.comments || "",
    ...(Array.isArray(change?.categories) ? change.categories : [])
  ]
    .join("\n")
    .toLowerCase();
  return haystack.includes(query);
}

function groupChangesByFile(changes) {
  const grouped = {};
  changes.forEach((change, index) => {
    const filePath = change?.diff?.file_path || "Unknown file";
    if (!grouped[filePath]) {
      grouped[filePath] = [];
    }
    grouped[filePath].push({ change, index });
  });
  return grouped;
}

function renderChangeItem(change, filePath, index) {
  const changeId = `change-${index}`;
  changeLookup[changeId] = change;

  const template = document.getElementById("changeItemTemplate");
  const element = template.content.firstElementChild.cloneNode(true);

  const diff = change?.diff || {};
  const lineNumber = Number(diff.old_start_line_number || diff.line_number || 1);
  const newLineNumber = Number(diff.new_start_line_number || lineNumber);
  const changeType = diff.change_type || "modified";
  const categories = Array.isArray(change.categories) ? change.categories : [];

  const oldParsed = parseCodeLines(diff.old_content || "");
  const newParsed = parseCodeLines(diff.new_content || "");

  element.dataset.changeId = changeId;
  element.dataset.categories = categories.join(",");
  element.dataset.type = changeType;

  const header = element.querySelector(".file-change-header");
  const icon = element.querySelector(".collapse-icon");
  const diffContent = element.querySelector(".diff-content");
  const statusIndicator = element.querySelector(".status-indicator");
  const categoriesElement = element.querySelector(".categories");
  const changeTypeElement = element.querySelector(".change-type-badge");
  const explanationElement = element.querySelector(".explanation-text");
  const commentBox = element.querySelector(".comment-box");
  const commentText = element.querySelector(".comment-text");

  icon.id = `icon-${changeId}`;
  diffContent.id = `diff-${changeId}`;
  statusIndicator.id = `status-${changeId}`;

  element.querySelector(".file-path-text").textContent = filePath;
  element.querySelector(".line-info").textContent = `Lines ${lineNumber} -> ${newLineNumber}`;
  element.querySelector(".pane-title-old").textContent = `Original (Line ${lineNumber})`;
  element.querySelector(".pane-title-new").textContent = `Modified (Line ${newLineNumber})`;

  categories.forEach((cat) => {
    const badge = document.createElement("span");
    badge.className = `category-badge ${cat}`;
    badge.textContent = cat;
    categoriesElement.appendChild(badge);
  });

  changeTypeElement.classList.add(changeType);
  changeTypeElement.textContent = changeType;
  explanationElement.textContent = change.explanation || "No explanation provided.";

  if (change.comments) {
    commentBox.hidden = false;
    commentText.textContent = change.comments;
  }

  const oldCodePane = element.querySelector(".pane-code-old");
  const newCodePane = element.querySelector(".pane-code-new");
  oldCodePane.appendChild(renderCodeLines(oldParsed.lines, "removed", lineNumber));
  newCodePane.appendChild(renderCodeLines(newParsed.lines, "added", newLineNumber));

  const oldNote = renderTruncationNote(oldParsed);
  const newNote = renderTruncationNote(newParsed);
  if (oldNote) {
    oldCodePane.appendChild(oldNote);
  }
  if (newNote) {
    newCodePane.appendChild(newNote);
  }

  header.addEventListener("click", () => toggleDiff(changeId));
  element.querySelector(".btn-copy-old").addEventListener("click", () => copyOldContent(changeId));
  element.querySelector(".btn-copy-new").addEventListener("click", () => copyNewContent(changeId));
  element.querySelector(".btn-copy-change").addEventListener("click", () => copyChange(changeId));
  element.querySelector(".btn-cancel").addEventListener("click", () => cancelChange(changeId));
  element.querySelector(".btn-apply").addEventListener("click", () => applyChange(changeId));

  return element;
}

function parseCodeLines(code) {
  const normalizedCode = normalizeCodeText(code);
  if (!normalizedCode) {
    return { lines: [], truncatedCount: 0 };
  }

  const allLines = normalizedCode.split("\n");
  if (allLines.length <= MAX_RENDER_LINES_PER_PANE) {
    return { lines: allLines, truncatedCount: 0 };
  }

  return {
    lines: allLines.slice(0, MAX_RENDER_LINES_PER_PANE),
    truncatedCount: allLines.length - MAX_RENDER_LINES_PER_PANE
  };
}

function normalizeCodeText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch (_) {
      return String(value);
    }
  }
  return String(value);
}

function renderTruncationNote(parsed) {
  if (!parsed.truncatedCount) {
    return null;
  }
  const line = document.createElement("div");
  line.className = "code-line line-context";
  line.innerHTML = `
    <span class="line-number">...</span>
    <span class="line-code">Preview truncated: ${parsed.truncatedCount} more lines</span>
  `;
  return line;
}

function renderCodeLines(lines, type, startLine) {
  const fragment = document.createDocumentFragment();
  if (!lines || lines.length === 0) {
    const empty = document.createElement("div");
    empty.className = "code-line line-context";
    empty.innerHTML = '<span class="line-number">-</span><span class="line-code">No content</span>';
    fragment.appendChild(empty);
    return fragment;
  }

  const base = Number(startLine) || 1;
  const lineClass = type === "added" ? "line-added" : type === "removed" ? "line-removed" : "line-context";

  lines.forEach((line, index) => {
    const row = document.createElement("div");
    row.className = `code-line ${lineClass}`;

    const lineNumber = document.createElement("span");
    lineNumber.className = "line-number";
    lineNumber.textContent = String(base + index);

    const lineCode = document.createElement("span");
    lineCode.className = "line-code";
    lineCode.textContent = line || " ";
    if (line && line.length > 240) {
      lineCode.title = line;
    }

    row.appendChild(lineNumber);
    row.appendChild(lineCode);
    fragment.appendChild(row);
  });

  return fragment;
}

function toggleDiff(changeId) {
  const diffContent = document.getElementById(`diff-${changeId}`);
  const icon = document.getElementById(`icon-${changeId}`);
  if (!diffContent || !icon) {
    return;
  }

  diffContent.classList.toggle("expanded");
  icon.classList.toggle("expanded");
}

async function applyChange(changeId, options = {}) {
  const change = changeLookup[changeId];
  const changeElement = document.querySelector(`[data-change-id="${changeId}"]`);
  const silent = Boolean(options?.silent);
  if (!change || !change.diff) {
    if (!silent) {
      showToast("Change not found", "error");
    }
    return;
  }
  if (appliedChanges.has(changeId)) {
    if (!silent) {
      showToast("Change already applied", "info");
    }
    return;
  }

  const repoPath = document.getElementById("repoPath").value;
  const diff = change.diff;

  try {
    if (!silent) {
      showToast("Applying change...", "info");
    }
    const result = await apiPost("/api/apply-changes", {
      repo_path: repoPath,
      file_path: diff.file_path,
      new_content: diff.new_content || "",
      line_number: Number(diff.new_start_line_number || diff.line_number || 1),
      new_start_line_number: Number(diff.new_start_line_number || diff.line_number || 1),
      number_of_lines_removed_from_old: Number(diff.number_of_lines_removed_from_old || 0),
      number_of_lines_added_in_new: Number(diff.number_of_lines_added_in_new || 0),
      old_start_line_number: Number(diff.old_start_line_number || diff.line_number || 1),
      old_content: diff.old_content || "",
      allow_fallback_search: true
    });

    appliedChanges.add(changeId);
    cancelledChanges.delete(changeId);

    if (changeElement) {
      changeElement.classList.add("applied");
      changeElement.classList.remove("cancelled");
    }

    const statusIndicator = document.getElementById(`status-${changeId}`);
    if (statusIndicator) {
      statusIndicator.style.display = "flex";
      statusIndicator.className = "status-indicator applied";
      statusIndicator.innerHTML = '<i class="fas fa-check-circle"></i> Applied';
    }

    const appliedLine = result?.applied_start_line_number;
    const usedRelaxed = Boolean(result?.applied_with_relaxed_old_content);
    const usedFallback = Boolean(result?.applied_with_fallback_search);
    if (!silent) {
      if (appliedLine) {
        if (usedRelaxed) {
          showToast(`Change applied at line ${appliedLine} (relaxed match mode)`, "success");
        } else if (usedFallback) {
          showToast(`Change applied at line ${appliedLine} (fallback match mode)`, "success");
        } else {
          showToast(`Change applied at line ${appliedLine}`, "success");
        }
      } else {
        showToast("Change applied successfully", "success");
      }
    }
  } catch (error) {
    if (!silent) {
      showToast(`Failed to apply change: ${error.message}`, "error");
    }
  }
}

function cancelChange(changeId) {
  const changeElement = document.querySelector(`[data-change-id="${changeId}"]`);
  cancelledChanges.add(changeId);
  appliedChanges.delete(changeId);

  if (changeElement) {
    changeElement.classList.add("cancelled");
    changeElement.classList.remove("applied");
  }

  const statusIndicator = document.getElementById(`status-${changeId}`);
  if (statusIndicator) {
    statusIndicator.style.display = "flex";
    statusIndicator.className = "status-indicator cancelled";
    statusIndicator.innerHTML = '<i class="fas fa-times-circle"></i> Cancelled';
  }

  const diffContent = document.getElementById(`diff-${changeId}`);
  const icon = document.getElementById(`icon-${changeId}`);
  if (diffContent && icon) {
    diffContent.classList.remove("expanded");
    icon.classList.remove("expanded");
  }

  showToast("Change cancelled", "info");
}

function copyChange(changeId) {
  const change = changeLookup[changeId];
  if (!change || !change.diff) {
    showToast("Change not found", "error");
    return;
  }

  const text = [
    `File: ${change.diff.file_path}`,
    `Line: ${change.diff.old_start_line_number || change.diff.line_number || 1}`,
    "",
    "Old Content:",
    change.diff.old_content || "",
    "",
    "New Content:",
    change.diff.new_content || "",
    "",
    `Explanation: ${change.explanation || ""}`
  ].join("\n");

  navigator.clipboard
    .writeText(text)
    .then(() => showToast("Change copied to clipboard", "success"))
    .catch(() => showToast("Failed to copy", "error"));
}

function copyOldContent(changeId) {
  const change = changeLookup[changeId];
  if (!change || !change.diff) {
    showToast("Change not found", "error");
    return;
  }

  const text = normalizeCodeText(change.diff.old_content || "");
  if (!text.trim()) {
    showToast("No old content to copy", "info");
    return;
  }

  navigator.clipboard
    .writeText(text)
    .then(() => showToast("Old content copied", "success"))
    .catch(() => showToast("Failed to copy old content", "error"));
}

function copyNewContent(changeId) {
  const change = changeLookup[changeId];
  if (!change || !change.diff) {
    showToast("Change not found", "error");
    return;
  }

  const text = normalizeCodeText(change.diff.new_content || "");
  if (!text.trim()) {
    showToast("No new content to copy", "info");
    return;
  }

  navigator.clipboard
    .writeText(text)
    .then(() => showToast("New content copied", "success"))
    .catch(() => showToast("Failed to copy new content", "error"));
}

function copyAllChanges() {
  if (!allChanges.length) {
    showToast("No changes to copy", "info");
    return;
  }

  const text = allChanges
    .map((change, index) => {
      const diff = change?.diff || {};
      return [
        `Change ${index + 1}`,
        `File: ${diff.file_path || "Unknown file"}`,
        `Line: ${diff.old_start_line_number || diff.line_number || 1}`,
        "",
        "Old Content:",
        diff.old_content || "",
        "",
        "New Content:",
        diff.new_content || "",
        "",
        `Explanation: ${change?.explanation || ""}`,
        "",
        "=".repeat(80)
      ].join("\n");
    })
    .join("\n");

  navigator.clipboard
    .writeText(text)
    .then(() => showToast("All changes copied to clipboard", "success"))
    .catch(() => showToast("Failed to copy", "error"));
}

async function applyAllChanges() {
  if (allChanges.length === 0) {
    showToast("No changes to apply", "info");
    return;
  }

  if (!confirm(`Apply all ${allChanges.length} changes?`)) {
    return;
  }

  let successCount = 0;
  let failCount = 0;
  const pendingChangeIds = getPendingChangeIdsForBulkApply();
  for (const changeId of pendingChangeIds) {
    try {
      await applyChange(changeId, { silent: true });
      if (appliedChanges.has(changeId)) {
        successCount += 1;
      } else {
        failCount += 1;
      }
    } catch (_) {
      failCount += 1;
    }
  }

  showToast(`Applied ${successCount} changes. ${failCount} failed.`, failCount ? "info" : "success");
}

function getPendingChangeIdsForBulkApply() {
  const pending = [];
  for (let i = 0; i < allChanges.length; i += 1) {
    const changeId = `change-${i}`;
    if (cancelledChanges.has(changeId) || appliedChanges.has(changeId)) {
      continue;
    }
    const diff = allChanges[i]?.diff || {};
    pending.push({
      changeId,
      filePath: String(diff.file_path || ""),
      line: Number(diff.old_start_line_number || diff.line_number || 1)
    });
  }

  pending.sort((left, right) => {
    if (left.filePath !== right.filePath) {
      return left.filePath.localeCompare(right.filePath);
    }
    return right.line - left.line;
  });

  return pending.map((item) => item.changeId);
}

function filterByCategory(category) {
  document.querySelectorAll(".change-item").forEach((item) => {
    const categories = (item.dataset.categories || "").split(",").filter(Boolean);
    if (category === "all" || categories.includes(category)) {
      item.classList.remove("hidden");
    } else {
      item.classList.add("hidden");
    }
  });
}

function copyText(id) {
  const el = document.getElementById(id);
  if (!el) {
    return;
  }
  const text = el.innerText || el.textContent || "";

  navigator.clipboard
    .writeText(text)
    .then(() => showToast("Copied to clipboard", "success"))
    .catch(() => showToast("Failed to copy", "error"));
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: ${type === "error" ? "#ef4444" : type === "info" ? "#0ea5e9" : "#22c55e"};
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    z-index: 9999;
    animation: slideIn 0.3s ease-out;
  `;

  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "slideOut 0.3s ease-out";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function initializeMarkdownRenderer() {
  if (typeof marked === "undefined") {
    return;
  }

  marked.setOptions({
    gfm: true,
    breaks: true
  });
}

function renderMarkdown(text) {
  if (!text) {
    return "";
  }
  if (typeof marked === "undefined") {
    return escapeHtmlForFallback(text);
  }

  try {
    return marked.parse(text);
  } catch (_) {
    return escapeHtmlForFallback(text);
  }
}

function escapeHtmlForFallback(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return `<pre>${div.innerHTML}</pre>`;
}

function initializeTheme() {
  const toggle = document.getElementById("themeToggle");
  const label = document.getElementById("themeLabel");
  if (!toggle || !label) {
    return;
  }

  const stored = localStorage.getItem("ui-theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const theme = stored || (prefersDark ? "dark" : "light");
  applyTheme(theme);

  toggle.checked = theme === "dark";
  label.textContent = theme === "dark" ? "Dark" : "Light";

  toggle.addEventListener("change", () => {
    const nextTheme = toggle.checked ? "dark" : "light";
    applyTheme(nextTheme);
    label.textContent = nextTheme === "dark" ? "Dark" : "Light";
    localStorage.setItem("ui-theme", nextTheme);
  });
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
}

const style = document.createElement("style");
style.textContent = `
  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }

  @keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
  }
`;
document.head.appendChild(style);
