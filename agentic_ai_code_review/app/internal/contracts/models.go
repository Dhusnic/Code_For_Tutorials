package contracts

type ConfigModel struct {
	RepoPath       string `json:"repo_path"`
	AIModel        string `json:"ai_model,omitempty"`
	MaxTokens      int    `json:"max_tokens,omitempty"`
	Organization   string `json:"organization,omitempty"`
	Project        string `json:"project,omitempty"`
	RepositoryName string `json:"repository_name,omitempty"`
	PullRequestID  string `json:"pull_request_id,omitempty"`
	AzurePAT       string `json:"azure_pat,omitempty"`
	IsLocal        bool   `json:"is_local,omitempty"`
	Review         string `json:"review,omitempty"`
}

type ApplyChangesModel struct {
	FilePath                    string `json:"file_path"`
	NewContent                  string `json:"new_content"`
	RepoPath                    string `json:"repo_path"`
	LineNumber                  int    `json:"line_number"`
	NewStartLineNumber          int    `json:"new_start_line_number"`
	NumberOfLinesRemovedFromOld int    `json:"number_of_lines_removed_from_old"`
	NumberOfLinesAddedInNew     int    `json:"number_of_lines_added_in_new"`
	OldStartLineNumber          int    `json:"old_start_line_number"`
	OldContent                  string `json:"old_content"`
	AllowFallbackSearch         bool   `json:"allow_fallback_search"`
}

type StaticChecksRequestModel struct {
	RepoPath       string   `json:"repo_path"`
	Scope          string   `json:"scope,omitempty"`
	Organization   string   `json:"organization,omitempty"`
	Project        string   `json:"project,omitempty"`
	RepositoryName string   `json:"repository_name,omitempty"`
	PullRequestID  string   `json:"pull_request_id,omitempty"`
	AzurePAT       string   `json:"azure_pat,omitempty"`
	IsLocal        bool     `json:"is_local,omitempty"`
	FilePaths      []string `json:"file_paths,omitempty"`
}

type PRWorkflowBaseRequestModel struct {
	RepoPath       string `json:"repo_path"`
	Organization   string `json:"organization"`
	Project        string `json:"project"`
	RepositoryName string `json:"repository_name"`
	AzurePAT       string `json:"azure_pat"`
	DefaultsPath   string `json:"defaults_path,omitempty"`
}

type PRFeatureContextRequestModel struct {
	PRWorkflowBaseRequestModel
	FeatureID int `json:"feature_id"`
}

type PRWorkItemFamilyRequestModel struct {
	PRWorkflowBaseRequestModel
	WorkItemID int `json:"work_item_id"`
}

type PRReviewersRequestModel struct {
	PRWorkflowBaseRequestModel
	Limit           int      `json:"limit,omitempty"`
	PreferredEmails []string `json:"preferred_emails,omitempty"`
}

type RaiseNewPRRequestModel struct {
	PRWorkflowBaseRequestModel
	FeatureID             int                 `json:"feature_id"`
	SelectedSerials       []int               `json:"selected_serials,omitempty"`
	ReviewerIDs           []string            `json:"reviewer_ids,omitempty"`
	ReviewerIDsByBranch   map[string][]string `json:"reviewer_ids_by_branch,omitempty"`
	TargetBranches        []string            `json:"target_branches,omitempty"`
	AdditionalWorkItemIDs []int               `json:"additional_work_item_ids,omitempty"`
	CommitMessage         string              `json:"commit_message,omitempty"`
}

type CherryPickRequestModel struct {
	PRWorkflowBaseRequestModel
	SourceBranch string   `json:"source_branch"`
	TargetBranch string   `json:"target_branch"`
	CommitHashes []string `json:"commit_hashes,omitempty"`
}

type CommitAndPushRequestModel struct {
	PRWorkflowBaseRequestModel
	BranchName      string `json:"branch_name"`
	BaseBranch      string `json:"base_branch"`
	SelectedSerials []int  `json:"selected_serials,omitempty"`
	CommitMessage   string `json:"commit_message"`
}

type JobProceedRequestModel struct {
	RequestID string `json:"request_id,omitempty"`
}

type ReviewDiffsResult struct {
	Review        string         `json:"review,omitempty"`
	TokenEstimate int            `json:"token_estimate,omitempty"`
	TokensUsed    int            `json:"tokens_used,omitempty"`
	TokenSource   string         `json:"token_source,omitempty"`
	TokenUsage    map[string]any `json:"token_usage,omitempty"`
	Usage         map[string]any `json:"usage,omitempty"`
	OK            bool           `json:"ok,omitempty"`
}

type RunFullReviewResult struct {
	Review                          string         `json:"review,omitempty"`
	CodeChanges                     []any          `json:"code_changes,omitempty"`
	NoChangesRequired               bool           `json:"no_changes_required,omitempty"`
	ResolutionStatus                string         `json:"resolution_status,omitempty"`
	FilterRelaxedToIncludeGenerated bool           `json:"filter_relaxed_to_include_generated,omitempty"`
	TokenEstimate                   int            `json:"token_estimate,omitempty"`
	TokensUsed                      int            `json:"tokens_used,omitempty"`
	TokenSource                     string         `json:"token_source,omitempty"`
	TokenUsage                      map[string]any `json:"token_usage,omitempty"`
	RawResponse                     string         `json:"raw_response,omitempty"`
	Usage                           map[string]any `json:"usage,omitempty"`
}

type AsyncJobSubmission struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"`
	PollURL string `json:"poll_url"`
	WSURL   string `json:"ws_url"`
}

type ErrorEnvelope struct {
	Detail any `json:"detail"`
}
