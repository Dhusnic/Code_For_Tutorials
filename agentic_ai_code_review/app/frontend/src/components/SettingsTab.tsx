import { useEffect, useState } from "react";
import { getSettings, health, saveSettings } from "../lib/wails-api";
import { JsonRecord } from "../lib/types";

export default function SettingsTab() {
  const [settings, setSettings] = useState<JsonRecord>({});
  const [metaPath, setMetaPath] = useState("");
  const [status, setStatus] = useState("Loading settings...");
  const [healthData, setHealthData] = useState<JsonRecord>({});

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
      await saveSettings(settings);
      setStatus("Settings saved.");
      await loadHealth();
    } catch (error) {
      setStatus(String(error));
    }
  }

  function update(key: string, value: string | boolean) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Desktop Settings</h2>
        <p>Native runtime preferences and diagnostics.</p>
      </div>

      <div className="meta-banner">
        <span>Config Path:</span>
        <code>{metaPath || "N/A"}</code>
      </div>

      <div className="form-grid">
        <label>
          Service Mode
          <select value={String(settings.service_mode || "native")} onChange={(e) => update("service_mode", e.target.value)}>
            <option value="native">native</option>
          </select>
        </label>
        <label>
          Runtime
          <input
            value={String(settings.runtime || "wails-native")}
            readOnly
          />
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
      </div>

      <div className="action-row">
        <button className="btn primary" onClick={save}>
          Save Settings
        </button>
        <button className="btn" onClick={() => void loadHealth()}>
          Refresh Health
        </button>
      </div>

      <div className="split">
        <div>
          <h3>Status</h3>
          <pre className="console">{status}</pre>
        </div>
        <div>
          <h3>Desktop Health</h3>
          <pre className="console">{JSON.stringify(healthData, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}
