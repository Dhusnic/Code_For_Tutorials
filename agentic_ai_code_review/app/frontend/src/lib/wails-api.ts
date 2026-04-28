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

function appBinding(): WailsApp {
  const binding = window.go?.desktop?.App;
  if (!binding) {
    throw new Error("Desktop runtime binding is unavailable. Start the app with Wails.");
  }
  return binding;
}

export async function runFullReview(payload: ReviewConfig, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().RunFullReview(payload, asyncJob);
}

export async function reviewDiffs(payload: ReviewConfig, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().ReviewDiffs(payload, asyncJob);
}

export async function runStaticChecks(payload: JsonRecord, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().RunStaticChecks(payload, asyncJob);
}

export async function raiseNewPR(payload: JsonRecord, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().RaiseNewPR(payload, asyncJob);
}

export async function getSettings(): Promise<JsonRecord> {
  return appBinding().GetSettings();
}

export async function saveSettings(payload: JsonRecord): Promise<JsonRecord> {
  return appBinding().SaveSettings(payload);
}

export async function health(): Promise<JsonRecord> {
  return appBinding().Health();
}
