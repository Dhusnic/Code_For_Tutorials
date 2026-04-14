import { useEffect, useState } from "react";
import { ensureDesktopBackendReady, getLegacyBaseUrl } from "./lib/wails-api";

export default function App() {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [bootStatus, setBootStatus] = useState("Initializing desktop runtime...");
  const [isReady, setIsReady] = useState(false);
  const [frameKey, setFrameKey] = useState(0);
  const [launchNonce, setLaunchNonce] = useState(() => Date.now());

  useEffect(() => {
    void launchParityUi();
  }, []);

  async function launchParityUi() {
    setIsReady(false);
    setBootStatus("Loading configuration...");

    const resolvedBaseUrl = await getLegacyBaseUrl();
    setBaseUrl(resolvedBaseUrl);

    setBootStatus("Starting integrated backend...");
    try {
      await ensureDesktopBackendReady();
    } catch (error) {
      setBootStatus(`Backend startup failed: ${String(error)}`);
      return;
    }

    setBootStatus("Waiting for backend health...");
    const healthy = await waitForHealth(resolvedBaseUrl, 120_000);
    if (!healthy) {
      setBootStatus(`Backend not reachable at ${resolvedBaseUrl}. Please verify Python is installed.`);
      return;
    }

    setBootStatus("Launching full web parity UI...");
    setIsReady(true);
    setLaunchNonce(Date.now());
    setFrameKey((value) => value + 1);
  }

  return (
    <div className="desktop-shell">
      {!isReady ? (
        <section className="boot-card">
          <h1>Agentic AI Code Review</h1>
          <p className="boot-subtitle">Preparing full web parity mode in desktop app...</p>
          <pre className="boot-console">{bootStatus}</pre>
          <div className="boot-actions">
            <button type="button" className="boot-btn" onClick={() => void launchParityUi()}>
              Retry
            </button>
          </div>
        </section>
      ) : (
        <iframe
          key={frameKey}
          className="web-parity-frame"
          src={`${baseUrl}/static/index.html?desktop_parity=1&_nonce=${launchNonce}`}
          title="Agentic AI Code Review - Full Web Parity"
        />
      )}
    </div>
  );
}

async function waitForHealth(baseUrl: string, timeoutMs: number): Promise<boolean> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(`${baseUrl}/api/health`, { method: "GET" });
      if (response.ok) {
        return true;
      }
    } catch {
      // Keep retrying until timeout.
    }
    await delay(1000);
  }
  return false;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}
