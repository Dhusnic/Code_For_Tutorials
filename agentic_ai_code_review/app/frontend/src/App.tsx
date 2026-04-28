import { useState } from "react";
import ReviewTab from "./components/ReviewTab";
import SettingsTab from "./components/SettingsTab";
import WorkflowTab from "./components/WorkflowTab";
import { MainTab } from "./lib/types";

const tabs: Array<{ id: MainTab; label: string }> = [
  { id: "review", label: "Review" },
  { id: "workflow", label: "PR Workflow" },
  { id: "settings", label: "Settings" }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<MainTab>("review");

  return (
    <main className="desktop-shell">
      <header className="app-header">
        <div>
          <h1>Agentic AI Code Review</h1>
          <p>Native desktop runtime</p>
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
