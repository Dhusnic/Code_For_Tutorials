import {
  CherryPickRequest,
  CommitAndPushRequest,
  FeatureContextRequest,
  JsonRecord,
  RaiseNewPRRequest,
  ReviewConfig,
  ReviewersRequest,
  WorkItemFamilyRequest,
  WorkflowBaseConfig
} from "./types";

type WailsApp = {
  RunFullReview: (config: ReviewConfig, async: boolean) => Promise<JsonRecord>;
  ReviewDiffs: (config: ReviewConfig, async: boolean) => Promise<JsonRecord>;
  GenerateChanges: (config: ReviewConfig) => Promise<JsonRecord>;
  ApplyChanges: (payload: JsonRecord) => Promise<JsonRecord>;
  RunStaticChecks: (payload: JsonRecord, async: boolean) => Promise<JsonRecord>;
  GetFeatureContext: (payload: FeatureContextRequest) => Promise<JsonRecord>;
  ListChangedFiles: (payload: WorkflowBaseConfig) => Promise<JsonRecord>;
  ListReviewers: (payload: ReviewersRequest) => Promise<JsonRecord>;
  GetWorkItemFamily: (payload: WorkItemFamilyRequest) => Promise<JsonRecord>;
  RaiseNewPR: (payload: RaiseNewPRRequest, async: boolean) => Promise<JsonRecord>;
  CherryPick: (payload: CherryPickRequest) => Promise<JsonRecord>;
  CommitAndPush: (payload: CommitAndPushRequest) => Promise<JsonRecord>;
  GetJob: (jobID: string) => Promise<JsonRecord>;
  ProceedJob: (jobID: string, requestID: string) => Promise<JsonRecord>;
  GetApprovalPreview: (jobID: string, requestID: string) => Promise<JsonRecord>;
  GetUsageMetrics: () => Promise<JsonRecord>;
  GetSettings: () => Promise<JsonRecord>;
  SaveSettings: (payload: JsonRecord) => Promise<JsonRecord>;
  SetSecret: (key: string, value: string) => Promise<JsonRecord>;
  DeleteSecret: (key: string) => Promise<JsonRecord>;
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

export async function generateChanges(payload: ReviewConfig): Promise<JsonRecord> {
  return appBinding().GenerateChanges(payload);
}

export async function applyChanges(payload: JsonRecord): Promise<JsonRecord> {
  return appBinding().ApplyChanges(payload);
}

export async function runStaticChecks(payload: JsonRecord, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().RunStaticChecks(payload, asyncJob);
}

export async function getFeatureContext(payload: FeatureContextRequest): Promise<JsonRecord> {
  return appBinding().GetFeatureContext(payload);
}

export async function listChangedFiles(payload: WorkflowBaseConfig): Promise<JsonRecord> {
  return appBinding().ListChangedFiles(payload);
}

export async function listReviewers(payload: ReviewersRequest): Promise<JsonRecord> {
  return appBinding().ListReviewers(payload);
}

export async function getWorkItemFamily(payload: WorkItemFamilyRequest): Promise<JsonRecord> {
  return appBinding().GetWorkItemFamily(payload);
}

export async function raiseNewPR(payload: RaiseNewPRRequest, asyncJob: boolean): Promise<JsonRecord> {
  return appBinding().RaiseNewPR(payload, asyncJob);
}

export async function cherryPick(payload: CherryPickRequest): Promise<JsonRecord> {
  return appBinding().CherryPick(payload);
}

export async function commitAndPush(payload: CommitAndPushRequest): Promise<JsonRecord> {
  return appBinding().CommitAndPush(payload);
}

export async function getJob(jobID: string): Promise<JsonRecord> {
  return appBinding().GetJob(jobID);
}

export async function proceedJob(jobID: string, requestID: string): Promise<JsonRecord> {
  return appBinding().ProceedJob(jobID, requestID);
}

export async function getApprovalPreview(jobID: string, requestID: string): Promise<JsonRecord> {
  return appBinding().GetApprovalPreview(jobID, requestID);
}

export async function getUsageMetrics(): Promise<JsonRecord> {
  return appBinding().GetUsageMetrics();
}

export async function getSettings(): Promise<JsonRecord> {
  return appBinding().GetSettings();
}

export async function saveSettings(payload: JsonRecord): Promise<JsonRecord> {
  return appBinding().SaveSettings(payload);
}

export async function setSecret(key: string, value: string): Promise<JsonRecord> {
  return appBinding().SetSecret(key, value);
}

export async function deleteSecret(key: string): Promise<JsonRecord> {
  return appBinding().DeleteSecret(key);
}

export async function health(): Promise<JsonRecord> {
  return appBinding().Health();
}
