import { useEffect, useState } from "react";
import ReviewTab from "./components/ReviewTab";
import SettingsTab from "./components/SettingsTab";
import WorkflowTab from "./components/WorkflowTab";
import { health } from "./lib/wails-api";
import { JsonRecord, MainTab } from "./lib/types";

const tabs: Array<{ id: MainTab; label: string }> = [
  { id: "review", label: "Review" },
  { id: "workflow", label: "PR Workflow" },
  { id: "settings", label: "Settings" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<MainTab>("review");
  const [healthData, setHealthData] = useState<JsonRecord>({});

  useEffect(() => {
    void health().then(setHealthData).catch((error) => setHealthData({ error: String(error) }));
  }, []);

  const serviceMode = String(healthData.service_mode || "unknown");
  const compatibilityBackend = (healthData.compatibility_backend as JsonRecord) || {};
  const compatibilityHealthy = compatibilityBackend.health_endpoint_reachable === true;

  return (
    <main className="desktop-shell">
      <header className="app-header">
        <div>
          <h1>Agentic AI Code Review</h1>
          <p>Windows desktop runtime with native and compatibility-backend routing.</p>
          <div className="meta-banner">
            <span>Mode: {serviceMode}</span>
            <span>Compatibility backend: {compatibilityHealthy ? "healthy" : "not reachable"}</span>
          </div>
        </div>
        <nav className="tab-bar" aria-label="Main views">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={tab.id === activeTab ? "tab active" : "tab"}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <section className="workspace">
        {activeTab === "review" ? <ReviewTab /> : null}
        {activeTab === "workflow" ? <WorkflowTab /> : null}
        {activeTab === "settings" ? <SettingsTab /> : null}
      </section>
    </main>
  );
}
