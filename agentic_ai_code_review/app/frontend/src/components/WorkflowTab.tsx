import { useState } from "react";
import { raiseNewPR } from "../lib/wails-api";
import { JsonRecord } from "../lib/types";

const defaultPayload: JsonRecord = {
  repo_path: "D:\\Product\\Infraon",
  organization: "infraon",
  project: "Infraon",
  repository_name: "Infraon",
  azure_pat: "",
  defaults_path: "config/pr_workflow_defaults.json",
  feature_id: 0,
  selected_serials: [],
  target_branches: ["main", "prerelease"]
};

export default function WorkflowTab() {
  const [payload, setPayload] = useState<JsonRecord>(defaultPayload);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("Ready.");

  async function executeRaisePR() {
    if (running) {
      return;
    }
    setRunning(true);
    setOutput("Running raise-new-pr workflow...");
    try {
      const result = await raiseNewPR(payload, true);
      setOutput(JSON.stringify(result, null, 2));
    } catch (error) {
      setOutput(String(error));
    } finally {
      setRunning(false);
    }
  }

  function updateField(key: string, value: string) {
    setPayload((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>PR Workflow</h2>
        <p>Branch orchestration, approvals, and PR creation in desktop flow.</p>
      </div>
      <div className="form-grid">
        <label>
          Repo Path
          <input value={String(payload.repo_path ?? "")} onChange={(e) => updateField("repo_path", e.target.value)} />
        </label>
        <label>
          Organization
          <input
            value={String(payload.organization ?? "")}
            onChange={(e) => updateField("organization", e.target.value)}
          />
        </label>
        <label>
          Project
          <input value={String(payload.project ?? "")} onChange={(e) => updateField("project", e.target.value)} />
        </label>
        <label>
          Repository Name
          <input
            value={String(payload.repository_name ?? "")}
            onChange={(e) => updateField("repository_name", e.target.value)}
          />
        </label>
        <label>
          Feature ID
          <input
            type="number"
            value={String(payload.feature_id ?? 0)}
            onChange={(e) => setPayload((prev) => ({ ...prev, feature_id: Number(e.target.value) }))}
          />
        </label>
      </div>
      <div className="action-row">
        <button className="btn primary" disabled={running} onClick={executeRaisePR}>
          Raise New PR (Async)
        </button>
      </div>
      <pre className="console">{output}</pre>
    </section>
  );
}
