import { JsonRecord, ReviewConfig } from "./types";

type WailsApp = {
  RunFullReview: (config: ReviewConfig, async: boolean) => Promise<JsonRecord>;
  ReviewDiffs: (config: ReviewConfig, async: boolean) => Promise<JsonRecord>;
  RunStaticChecks: (payload: JsonRecord, async: boolean) => Promise<JsonRecord>;
  RaiseNewPR: (payload: JsonRecord, async: boolean) => Promise<JsonRecord>;
  GetUsageMetrics: () => Promise<JsonRecord>;
  GetSettings: () => Promise<JsonRecord>;
  SaveSettings: (payload: JsonRecord) => Promise<JsonRecord>;
  Health: () => Promise<JsonRecord>;
};

declare global {
  interface Window {
    go?: {
      desktop?: {
        App?: WailsApp;
      };
    };
  }
}

const LEGACY_API_BASE = "http://127.0.0.1:8000";

function appBinding(): WailsApp | null {
  return window.go?.desktop?.App ?? null;
}

async function post(path: string, payload: unknown): Promise<JsonRecord> {
  const response = await fetch(`${LEGACY_API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(String((body as JsonRecord).detail || "Request failed"));
  }
  return body as JsonRecord;
}

async function get(path: string): Promise<JsonRecord> {
  const response = await fetch(`${LEGACY_API_BASE}${path}`, { method: "GET" });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(String((body as JsonRecord).detail || "Request failed"));
  }
  return body as JsonRecord;
}

export async function runFullReview(payload: ReviewConfig, asyncJob: boolean): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.RunFullReview(payload, asyncJob);
  }
  return post(`/api/run-full-review?async_job=${asyncJob ? "true" : "false"}`, payload);
}

export async function reviewDiffs(payload: ReviewConfig, asyncJob: boolean): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.ReviewDiffs(payload, asyncJob);
  }
  return post(`/api/review-diffs?async_job=${asyncJob ? "true" : "false"}`, payload);
}

export async function runStaticChecks(payload: JsonRecord, asyncJob: boolean): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.RunStaticChecks(payload, asyncJob);
  }
  return post(`/api/static-checks?async_job=${asyncJob ? "true" : "false"}`, payload);
}

export async function raiseNewPR(payload: JsonRecord, asyncJob: boolean): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.RaiseNewPR(payload, asyncJob);
  }
  return post(`/api/pr-workflow/raise-new-pr?async_job=${asyncJob ? "true" : "false"}`, payload);
}

export async function getSettings(): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.GetSettings();
  }
  return {
    path: "legacy-browser-fallback",
    config: {
      service_mode: "legacy",
      legacy_api_base_url: LEGACY_API_BASE,
      request_timeout_seconds: 180,
      log_level: "info",
      auto_start_legacy_api: true,
      auto_install_legacy_deps: true,
      legacy_api_python_bin: "python",
      legacy_api_script_path: "web/main.py",
      legacy_startup_timeout_seconds: 60
    }
  };
}

export async function saveSettings(payload: JsonRecord): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.SaveSettings(payload);
  }
  return payload;
}

export async function health(): Promise<JsonRecord> {
  const binding = appBinding();
  if (binding) {
    return binding.Health();
  }
  return get("/api/health");
}

export async function getLegacyBaseUrl(): Promise<string> {
  try {
    const settings = await getSettings();
    const config = (settings.config as JsonRecord) || {};
    const raw = String(config.legacy_api_base_url || "").trim();
    return raw || LEGACY_API_BASE;
  } catch {
    return LEGACY_API_BASE;
  }
}

export async function ensureDesktopBackendReady(): Promise<void> {
  const binding = appBinding();
  if (!binding || typeof binding.GetUsageMetrics !== "function") {
    return;
  }
  await binding.GetUsageMetrics();
}
