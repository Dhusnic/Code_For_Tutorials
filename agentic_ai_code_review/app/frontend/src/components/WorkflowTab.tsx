import { useState } from "react";
import {
  getFeatureContext,
  listChangedFiles,
  listReviewers,
  raiseNewPR
} from "../lib/wails-api";
import { JsonRecord, RaiseNewPRRequest } from "../lib/types";

const defaultPayload: RaiseNewPRRequest = {
  repo_path: "D:\\Product\\Infraon",
  organization: "infraon",
  project: "Infraon",
  repository_name: "Infraon",
  azure_pat: "",
  defaults_path: "config/pr_workflow_defaults.json",
  feature_id: 37709,
  selected_serials: [],
  target_branches: ["main", "prerelease"],
  commit_message: ""
};

export default function WorkflowTab() {
  const [payload, setPayload] = useState<RaiseNewPRRequest>(defaultPayload);
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState("Ready.");
  const [featureContext, setFeatureContext] = useState<JsonRecord>({});
  const [changedFiles, setChangedFiles] = useState<JsonRecord>({});
  const [reviewers, setReviewers] = useState<JsonRecord>({});

  async function execute(action: "feature" | "files" | "reviewers" | "raise") {
    if (running) {
      return;
    }
    setRunning(true);
    setOutput(`Running ${action}...`);
    try {
      if (action === "feature") {
        const result = await getFeatureContext({
          repo_path: payload.repo_path,
          organization: payload.organization,
          project: payload.project,
          repository_name: payload.repository_name,
          azure_pat: payload.azure_pat,
          defaults_path: payload.defaults_path,
          feature_id: payload.feature_id
        });
        setFeatureContext(result);
        setOutput("Feature context loaded.");
      } else if (action === "files") {
        const result = await listChangedFiles({
          repo_path: payload.repo_path,
          organization: payload.organization,
          project: payload.project,
          repository_name: payload.repository_name,
          azure_pat: payload.azure_pat,
          defaults_path: payload.defaults_path
        });
        setChangedFiles(result);
        const files = Array.isArray(result.files) ? result.files : [];
        setPayload((prev) => ({
          ...prev,
          selected_serials: files
            .map((item) => Number((item as JsonRecord).serial || 0))
            .filter((value) => Number.isFinite(value) && value > 0)
        }));
        setOutput(`Loaded ${files.length} changed files.`);
      } else if (action === "reviewers") {
        const preferredEmails = String((payload as JsonRecord).preferred_emails_csv || "")
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean);
        const result = await listReviewers({
          repo_path: payload.repo_path,
          organization: payload.organization,
          project: payload.project,
          repository_name: payload.repository_name,
          azure_pat: payload.azure_pat,
          defaults_path: payload.defaults_path,
          limit: Number((payload as JsonRecord).reviewer_limit || 25),
          preferred_emails: preferredEmails
        });
        setReviewers(result);
        setOutput("Reviewer candidates loaded.");
      } else {
        const result = await raiseNewPR(payload, false);
        setOutput(JSON.stringify(result, null, 2));
      }
    } catch (error) {
      setOutput(String(error));
    } finally {
      setRunning(false);
    }
  }

  function updateField<K extends keyof RaiseNewPRRequest>(key: K, value: RaiseNewPRRequest[K]) {
    setPayload((prev) => ({ ...prev, [key]: value }));
  }

  function updateExtraField(key: string, value: string) {
    setPayload((prev) => ({ ...prev, [key]: value } as RaiseNewPRRequest));
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>PR Workflow</h2>
        <p>Hybrid desktop workflow for feature context, changed files, reviewer lookup, and PR execution.</p>
      </div>

      <div className="form-grid">
        <label>
          Repo Path
          <input value={payload.repo_path} onChange={(e) => updateField("repo_path", e.target.value)} />
        </label>
        <label>
          Organization
          <input value={payload.organization} onChange={(e) => updateField("organization", e.target.value)} />
        </label>
        <label>
          Project
          <input value={payload.project} onChange={(e) => updateField("project", e.target.value)} />
        </label>
        <label>
          Repository Name
          <input value={payload.repository_name} onChange={(e) => updateField("repository_name", e.target.value)} />
        </label>
        <label>
          Azure PAT
          <input
            type="password"
            value={payload.azure_pat}
            onChange={(e) => updateField("azure_pat", e.target.value)}
            placeholder="Stored PAT can also be managed from Settings"
          />
        </label>
        <label>
          Defaults Path
          <input
            value={String(payload.defaults_path || "")}
            onChange={(e) => updateField("defaults_path", e.target.value)}
          />
        </label>
        <label>
          Feature ID
          <input
            type="number"
            value={String(payload.feature_id)}
            onChange={(e) => updateField("feature_id", Number(e.target.value))}
          />
        </label>
        <label>
          Target Branches
          <input
            value={(payload.target_branches || []).join(", ")}
            onChange={(e) =>
              updateField(
                "target_branches",
                e.target.value
                  .split(",")
                  .map((value) => value.trim())
                  .filter(Boolean)
              )
            }
          />
        </label>
        <label>
          Commit Message
          <input
            value={String(payload.commit_message || "")}
            onChange={(e) => updateField("commit_message", e.target.value)}
          />
        </label>
        <label>
          Reviewer Limit
          <input
            type="number"
            value={String((payload as JsonRecord).reviewer_limit || 25)}
            onChange={(e) => updateExtraField("reviewer_limit", e.target.value)}
          />
        </label>
        <label>
          Preferred Emails
          <input
            value={String((payload as JsonRecord).preferred_emails_csv || "")}
            onChange={(e) => updateExtraField("preferred_emails_csv", e.target.value)}
            placeholder="a@company.com, b@company.com"
          />
        </label>
      </div>

      <div className="action-row">
        <button className="btn primary" disabled={running} onClick={() => void execute("feature")}>
          Load Feature Context
        </button>
        <button className="btn" disabled={running} onClick={() => void execute("files")}>
          Load Changed Files
        </button>
        <button className="btn" disabled={running} onClick={() => void execute("reviewers")}>
          Load Reviewers
        </button>
        <button className="btn" disabled={running} onClick={() => void execute("raise")}>
          Raise / Plan PR
        </button>
      </div>

      <div className="split">
        <div>
          <h3>Feature Context</h3>
          <pre className="console">{JSON.stringify(featureContext, null, 2)}</pre>
        </div>
        <div>
          <h3>Changed Files</h3>
          <pre className="console">{JSON.stringify(changedFiles, null, 2)}</pre>
        </div>
      </div>

      <div className="split">
        <div>
          <h3>Reviewer Candidates</h3>
          <pre className="console">{JSON.stringify(reviewers, null, 2)}</pre>
        </div>
        <div>
          <h3>Workflow Output</h3>
          <pre className="console">{output}</pre>
        </div>
      </div>
    </section>
  );
}
