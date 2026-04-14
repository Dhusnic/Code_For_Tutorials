export type JsonRecord = Record<string, unknown>;

export type MainTab = "review" | "workflow" | "settings";

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
};
