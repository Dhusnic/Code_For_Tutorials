import { useEffect, useState } from "react";
import { deleteSecret, getSettings, health, saveSettings, setSecret } from "../lib/wails-api";
import { JsonRecord } from "../lib/types";

const SECRET_KEY = "azure_devops_pat";

export default function SettingsTab() {
  const [settings, setSettings] = useState<JsonRecord>({});
  const [metaPath, setMetaPath] = useState("");
  const [status, setStatus] = useState("Loading settings...");
  const [healthData, setHealthData] = useState<JsonRecord>({});
  const [secretValue, setSecretValue] = useState("");
  const [secretStatus, setSecretStatus] = useState("No secret action yet.");

  useEffect(() => {
    void load();
    void loadHealth();
  }, []);

  async function load() {
    try {
      const result = await getSettings();
      const config = (result.config as JsonRecord) || {};
      setMetaPath(String(result.path || ""));
      setSettings(config);
      if (result.health && typeof result.health === "object") {
        setHealthData(result.health as JsonRecord);
      }
      setStatus("Settings loaded.");
    } catch (error) {
      setStatus(String(error));
    }
  }

  async function loadHealth() {
    try {
      const result = await health();
      setHealthData(result);
    } catch (error) {
      setHealthData({ error: String(error) });
    }
  }

  async function save() {
    try {
      setStatus("Saving settings...");
      const result = await saveSettings(settings);
      const nextConfig = (result.config as JsonRecord) || {};
      setSettings(nextConfig);
      if (result.health && typeof result.health === "object") {
        setHealthData(result.health as JsonRecord);
      } else {
        await loadHealth();
      }
      setStatus("Settings saved.");
    } catch (error) {
      setStatus(String(error));
    }
  }

  async function savePatSecret() {
    try {
      setSecretStatus("Saving PAT into desktop secret store...");
      const result = await setSecret(SECRET_KEY, secretValue);
      if (result.ok !== true) {
        throw new Error(String(result.error || "Failed to save PAT."));
      }
      setSecretStatus("PAT saved to the desktop secret store.");
      setSecretValue("");
      await loadHealth();
    } catch (error) {
      setSecretStatus(String(error));
    }
  }

  async function removePatSecret() {
    try {
      setSecretStatus("Deleting PAT from desktop secret store...");
      const result = await deleteSecret(SECRET_KEY);
      if (result.ok !== true) {
        throw new Error(String(result.error || "Failed to delete PAT."));
      }
      setSecretStatus("PAT deleted from the desktop secret store.");
      await loadHealth();
    } catch (error) {
      setSecretStatus(String(error));
    }
  }

  function update(key: string, value: string | boolean) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  const compatibilityBackend = (healthData.compatibility_backend as JsonRecord) || {};
  const secretStore = ((settings.secret_store as JsonRecord) || (healthData.secret_store as JsonRecord) || {}) as JsonRecord;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Desktop Settings</h2>
        <p>Runtime routing, compatibility backend, secrets, and health diagnostics.</p>
      </div>

      <div className="meta-banner">
        <span>Config Path:</span>
        <code>{metaPath || "N/A"}</code>
      </div>

      <div className="form-grid">
        <label>
          Service Mode
          <select value={String(settings.service_mode || "hybrid")} onChange={(e) => update("service_mode", e.target.value)}>
            <option value="legacy">legacy</option>
            <option value="hybrid">hybrid</option>
            <option value="native">native</option>
          </select>
        </label>
        <label>
          Runtime
          <input value={String(settings.runtime || "wails-native")} readOnly />
        </label>
        <label>
          Request Timeout Seconds
          <input
            type="number"
            value={String(settings.request_timeout_seconds || 180)}
            onChange={(e) => update("request_timeout_seconds", e.target.value)}
          />
        </label>
        <label>
          Log Level
          <select value={String(settings.log_level || "info")} onChange={(e) => update("log_level", e.target.value)}>
            <option value="debug">debug</option>
            <option value="info">info</option>
            <option value="warn">warn</option>
            <option value="error">error</option>
          </select>
        </label>
        <label>
          Compatibility Base URL
          <input
            value={String(settings.legacy_api_base_url || "http://127.0.0.1:8000")}
            onChange={(e) => update("legacy_api_base_url", e.target.value)}
          />
        </label>
        <label>
          Auto Start Compatibility Backend
          <select
            value={String(Boolean(settings.auto_start_legacy_api))}
            onChange={(e) => update("auto_start_legacy_api", e.target.value === "true")}
          >
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </label>
        <label>
          Python Executable
          <input
            value={String(settings.legacy_api_python_bin || "python")}
            onChange={(e) => update("legacy_api_python_bin", e.target.value)}
          />
        </label>
        <label>
          Compatibility Script Path
          <input
            value={String(settings.legacy_api_script_path || "web/main.py")}
            onChange={(e) => update("legacy_api_script_path", e.target.value)}
          />
        </label>
        <label>
          Startup Timeout Seconds
          <input
            type="number"
            value={String(settings.legacy_startup_timeout_seconds || 60)}
            onChange={(e) => update("legacy_startup_timeout_seconds", e.target.value)}
          />
        </label>
        <label>
          Auto Install Compatibility Dependencies
          <select
            value={String(Boolean(settings.auto_install_legacy_deps))}
            onChange={(e) => update("auto_install_legacy_deps", e.target.value === "true")}
          >
            <option value="false">false</option>
            <option value="true">true</option>
          </select>
        </label>
      </div>

      <div className="action-row">
        <button className="btn primary" onClick={save}>
          Save Settings
        </button>
        <button className="btn" onClick={() => void load()}>
          Reload Settings
        </button>
        <button className="btn" onClick={() => void loadHealth()}>
          Refresh Health
        </button>
      </div>

      <div className="split">
        <div>
          <h3>Compatibility Backend</h3>
          <pre className="console">{JSON.stringify(compatibilityBackend, null, 2)}</pre>
        </div>
        <div>
          <h3>Desktop Health</h3>
          <pre className="console">{JSON.stringify(healthData, null, 2)}</pre>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Secrets</h2>
          <p>Store Azure PAT in the desktop secret store instead of config files.</p>
        </div>
        <div className="form-grid">
          <label>
            Secret Store Kind
            <input value={String(secretStore.kind || "unknown")} readOnly />
          </label>
          <label>
            Secret Read Supported
            <input value={String(secretStore.read_supported ?? false)} readOnly />
          </label>
          <label>
            Azure PAT
            <input
              type="password"
              value={secretValue}
              onChange={(e) => setSecretValue(e.target.value)}
              placeholder="Enter new PAT to store securely"
            />
          </label>
        </div>
        <div className="action-row">
          <button className="btn primary" onClick={() => void savePatSecret()} disabled={!secretValue.trim()}>
            Save PAT Secret
          </button>
          <button className="btn" onClick={() => void removePatSecret()}>
            Delete PAT Secret
          </button>
        </div>
        <pre className="console">{secretStatus}</pre>
      </div>

      <pre className="console">{status}</pre>
    </section>
  );
}
