import { useMemo, useState } from "react";
import { ReviewConfig } from "../lib/types";
import { getUsageMetrics, reviewDiffs, runFullReview, runStaticChecks } from "../lib/wails-api";

const defaultConfig: ReviewConfig = {
  repo_path: "D:\\Product\\Infraon",
  ai_model: "gpt-4o-mini",
  max_tokens: 30000,
  organization: "infraon",
  project: "Infraon",
  repository_name: "Infraon",
  pull_request_id: "",
  azure_pat: "",
  is_local: false
};

export default function ReviewTab() {
  const [config, setConfig] = useState<ReviewConfig>(defaultConfig);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string>("Ready.");

  const canRun = useMemo(() => Boolean(config.repo_path.trim()), [config.repo_path]);

  async function execute(action: "review" | "full" | "checks" | "usage") {
    if (!canRun || running) {
      return;
    }
    setRunning(true);
    setOutput(`Running ${action}...`);
    try {
      const payload =
        action === "usage"
          ? await getUsageMetrics()
          : action === "review"
          ? await reviewDiffs(config, false)
          : action === "full"
            ? await runFullReview(config, false)
            : await runStaticChecks(
                {
                  repo_path: config.repo_path,
                  scope: "repo",
                  organization: config.organization,
                  project: config.project,
                  repository_name: config.repository_name,
                  pull_request_id: config.pull_request_id,
                  azure_pat: config.azure_pat,
                  is_local: config.is_local
                },
                false
              );
      setOutput(JSON.stringify(payload, null, 2));
    } catch (error) {
      setOutput(String(error));
    } finally {
      setRunning(false);
    }
  }

  function update<K extends keyof ReviewConfig>(key: K, value: ReviewConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Code Review</h2>
        <p>Local diff review, guarded patch checks, and repository diagnostics.</p>
      </div>

      <div className="form-grid">
        <label>
          Repository Path
          <input value={config.repo_path} onChange={(e) => update("repo_path", e.target.value)} />
        </label>
        <label>
          Model
          <input value={config.ai_model} onChange={(e) => update("ai_model", e.target.value)} />
        </label>
        <label>
          Max Tokens
          <input
            type="number"
            value={config.max_tokens}
            onChange={(e) => update("max_tokens", Number(e.target.value))}
          />
        </label>
        <label>
          Organization
          <input value={config.organization} onChange={(e) => update("organization", e.target.value)} />
        </label>
        <label>
          Project
          <input value={config.project} onChange={(e) => update("project", e.target.value)} />
        </label>
        <label>
          Repository
          <input value={config.repository_name} onChange={(e) => update("repository_name", e.target.value)} />
        </label>
        <label>
          Pull Request ID
          <input value={config.pull_request_id} onChange={(e) => update("pull_request_id", e.target.value)} />
        </label>
        <label>
          Azure PAT
          <input
            type="password"
            value={config.azure_pat}
            onChange={(e) => update("azure_pat", e.target.value)}
            placeholder="Optional"
          />
        </label>
      </div>

      <div className="action-row">
        <button className="btn primary" disabled={!canRun || running} onClick={() => execute("full")}>
          Run Full Review
        </button>
        <button className="btn" disabled={!canRun || running} onClick={() => execute("review")}>
          Review Diffs
        </button>
        <button className="btn" disabled={!canRun || running} onClick={() => execute("checks")}>
          Static Checks
        </button>
        <button className="btn" disabled={running} onClick={() => execute("usage")}>
          Usage Metrics
        </button>
      </div>

      <pre className="console">{output}</pre>
    </section>
  );
}
