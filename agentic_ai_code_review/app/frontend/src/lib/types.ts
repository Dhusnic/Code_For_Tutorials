export type JsonRecord = Record<string, unknown>;

export type MainTab = "review" | "workflow" | "settings";
export type ServiceMode = "legacy" | "hybrid" | "native";

export type ReviewConfig = {
  repo_path: string;
  ai_model: string;
  max_tokens: number;
  organization: string;
  project: string;
  repository_name: string;
  pull_request_id: string;
  azure_pat: string;
  is_local: boolean;
  review?: string;
};

export type WorkflowBaseConfig = {
  repo_path: string;
  organization: string;
  project: string;
  repository_name: string;
  azure_pat: string;
  defaults_path?: string;
};

export type FeatureContextRequest = WorkflowBaseConfig & {
  feature_id: number;
};

export type ReviewersRequest = WorkflowBaseConfig & {
  limit?: number;
  preferred_emails?: string[];
};

export type WorkItemFamilyRequest = WorkflowBaseConfig & {
  work_item_id: number;
};

export type RaiseNewPRRequest = WorkflowBaseConfig & {
  feature_id: number;
  selected_serials: number[];
  reviewer_ids?: string[];
  reviewer_ids_by_branch?: Record<string, string[]>;
  target_branches?: string[];
  additional_work_item_ids?: number[];
  commit_message?: string | null;
};

export type CherryPickRequest = WorkflowBaseConfig & {
  source_branch: string;
  target_branch: string;
  commit_hashes: string[];
};

export type CommitAndPushRequest = WorkflowBaseConfig & {
  branch_name: string;
  base_branch: string;
  selected_serials: number[];
  commit_message: string;
};
