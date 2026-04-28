package native

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"agenticai/desktop/internal/contracts"
	"agenticai/desktop/internal/core/jobs"
	"agenticai/desktop/internal/git"
	"agenticai/desktop/internal/services"
)

const executionMode = "native"

type Service struct {
	logger *slog.Logger
	git    *git.Adapter
	jobs   *jobs.Manager
	usage  *usageTracker
}

type changedFile struct {
	Serial         int    `json:"serial"`
	FilePath       string `json:"file_path"`
	Status         string `json:"status"`
	StagedStatus   string `json:"staged_status"`
	UnstagedStatus string `json:"unstaged_status"`
}

type reviewFinding struct {
	Severity string `json:"severity"`
	File     string `json:"file,omitempty"`
	Message  string `json:"message"`
}

type usageTracker struct {
	mu            sync.Mutex
	requestCount  int
	totalTokens   int
	totalCostUSD  float64
	recentRequest []map[string]any
}

var _ services.DesktopService = (*Service)(nil)

func NewService(logger *slog.Logger, jobManager *jobs.Manager) *Service {
	if jobManager == nil {
		jobManager = jobs.NewManager(2 * time.Hour)
	}
	return &Service{
		logger: logger,
		git:    git.NewAdapter(logger),
		jobs:   jobManager,
		usage:  &usageTracker{},
	}
}

func (s *Service) RunFullReview(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	if async {
		return s.submit(ctx, "run-full-review", request, func(ctx context.Context, payload map[string]any) (map[string]any, error) {
			var decoded contracts.ConfigModel
			if err := mapToStruct(payload, &decoded); err != nil {
				return nil, err
			}
			return s.runFullReview(ctx, decoded)
		})
	}
	return s.runFullReview(ctx, request)
}

func (s *Service) ReviewDiffs(ctx context.Context, request contracts.ConfigModel, async bool) (map[string]any, error) {
	if async {
		return s.submit(ctx, "review-diffs", request, func(ctx context.Context, payload map[string]any) (map[string]any, error) {
			var decoded contracts.ConfigModel
			if err := mapToStruct(payload, &decoded); err != nil {
				return nil, err
			}
			return s.reviewDiffs(ctx, decoded)
		})
	}
	return s.reviewDiffs(ctx, request)
}

func (s *Service) GenerateChanges(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	result := map[string]any{
		"code_changes":            []any{},
		"no_changes_required":     true,
		"resolution_status":       "manual_review_required",
		"raw_response":            "Native desktop mode does not auto-edit files from free-form review text. Use ApplyChanges with explicit file content to modify the repository.",
		"desktop_execution_mode":  executionMode,
		"desktop_operation":       "GenerateChanges",
		"review_input_available":  strings.TrimSpace(request.Review) != "",
		"generation_engine":       "native_guarded",
		"requires_user_approval":  true,
		"unsafe_autofix_disabled": true,
	}
	return result, nil
}

func (s *Service) ApplyChanges(ctx context.Context, request contracts.ApplyChangesModel) (map[string]any, error) {
	_ = ctx
	repoRoot, err := cleanRepoPath(request.RepoPath)
	if err != nil {
		return nil, err
	}
	target, rel, err := resolveFileInRepo(repoRoot, request.FilePath)
	if err != nil {
		return nil, err
	}

	raw, err := os.ReadFile(target)
	if err != nil {
		return nil, err
	}
	original := string(raw)
	next, matchMode, err := buildPatchedContent(original, request)
	if err != nil {
		return nil, err
	}
	if next == original {
		return nativeResult("ApplyChanges", map[string]any{
			"success":    true,
			"message":    "No content changes were necessary.",
			"file_path":  rel,
			"match_mode": matchMode,
		}), nil
	}

	backupPath, err := writeBackup(repoRoot, rel, raw)
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(target, []byte(next), 0o644); err != nil {
		return nil, err
	}

	return nativeResult("ApplyChanges", map[string]any{
		"success":     true,
		"message":     "Change applied.",
		"file_path":   rel,
		"backup_path": backupPath,
		"match_mode":  matchMode,
	}), nil
}

func (s *Service) RunStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel, async bool) (map[string]any, error) {
	if async {
		return s.submit(ctx, "static-checks", request, func(ctx context.Context, payload map[string]any) (map[string]any, error) {
			var decoded contracts.StaticChecksRequestModel
			if err := mapToStruct(payload, &decoded); err != nil {
				return nil, err
			}
			return s.runStaticChecks(ctx, decoded)
		})
	}
	return s.runStaticChecks(ctx, request)
}

func (s *Service) GetUsageMetrics(ctx context.Context) (map[string]any, error) {
	_ = ctx
	result := s.usage.snapshot()
	result["desktop_execution_mode"] = executionMode
	result["desktop_operation"] = "GetUsageMetrics"
	return result, nil
}

func (s *Service) GetFeatureContext(ctx context.Context, request contracts.PRFeatureContextRequestModel) (map[string]any, error) {
	_ = ctx
	branches := branchPlan(request.FeatureID, nil, request.DefaultsPath)
	return nativeResult("GetFeatureContext", map[string]any{
		"feature_id":      request.FeatureID,
		"feature_title":   fmt.Sprintf("Feature %d", request.FeatureID),
		"target_branches": branches,
		"work_items":      []any{},
		"message":         "Native desktop resolved local branch planning context. Azure work-item lookup is not enabled in this offline desktop mode.",
	}), nil
}

func (s *Service) ListChangedFiles(ctx context.Context, request contracts.PRWorkflowBaseRequestModel) (map[string]any, error) {
	files, err := s.collectChangedFiles(ctx, request.RepoPath)
	if err != nil {
		return nil, err
	}
	items := changedFilesToMaps(files)
	return nativeResult("ListChangedFiles", map[string]any{
		"count": len(items),
		"files": items,
	}), nil
}

func (s *Service) ListReviewers(ctx context.Context, request contracts.PRReviewersRequestModel) (map[string]any, error) {
	_ = ctx
	limit := request.Limit
	if limit <= 0 {
		limit = 25
	}
	reviewers := make([]map[string]any, 0, len(request.PreferredEmails))
	for _, email := range request.PreferredEmails {
		email = strings.TrimSpace(email)
		if email == "" {
			continue
		}
		reviewers = append(reviewers, map[string]any{
			"id":           email,
			"display_name": email,
			"unique_name":  email,
			"mail":         email,
			"source":       "preferred_email",
		})
		if len(reviewers) >= limit {
			break
		}
	}
	return nativeResult("ListReviewers", map[string]any{
		"count":     len(reviewers),
		"reviewers": reviewers,
		"message":   "Native desktop reviewer lookup uses preferred emails. Azure identity search is not called by this local runtime.",
	}), nil
}

func (s *Service) GetWorkItemFamily(ctx context.Context, request contracts.PRWorkItemFamilyRequestModel) (map[string]any, error) {
	_ = ctx
	return nativeResult("GetWorkItemFamily", map[string]any{
		"work_item_id": request.WorkItemID,
		"parent":       nil,
		"children":     []any{},
		"message":      "Native desktop work-item family lookup is offline. Connect Azure integration in Go to hydrate this data.",
	}), nil
}

func (s *Service) RaiseNewPR(ctx context.Context, request contracts.RaiseNewPRRequestModel, async bool) (map[string]any, error) {
	if async {
		return s.submit(ctx, "raise-new-pr", request, func(ctx context.Context, payload map[string]any) (map[string]any, error) {
			var decoded contracts.RaiseNewPRRequestModel
			if err := mapToStruct(payload, &decoded); err != nil {
				return nil, err
			}
			return s.preparePRPlan(ctx, decoded)
		})
	}
	return s.preparePRPlan(ctx, request)
}

func (s *Service) CherryPick(ctx context.Context, request contracts.CherryPickRequestModel) (map[string]any, error) {
	if strings.TrimSpace(request.SourceBranch) == "" || strings.TrimSpace(request.TargetBranch) == "" {
		return nil, errors.New("source_branch and target_branch are required")
	}
	return nativeResult("CherryPick", map[string]any{
		"source_branch": request.SourceBranch,
		"target_branch": request.TargetBranch,
		"commit_hashes": request.CommitHashes,
		"status":        "plan_ready",
		"message":       "Native desktop prepared the cherry-pick plan. Automatic branch mutation is intentionally left behind an explicit confirmation flow.",
	}), nil
}

func (s *Service) CommitAndPush(ctx context.Context, request contracts.CommitAndPushRequestModel) (map[string]any, error) {
	files, err := s.collectChangedFiles(ctx, request.RepoPath)
	if err != nil {
		return nil, err
	}
	selected := selectChangedFiles(files, request.SelectedSerials)
	return nativeResult("CommitAndPush", map[string]any{
		"branch_name":    request.BranchName,
		"base_branch":    request.BaseBranch,
		"commit_message": request.CommitMessage,
		"selected_files": changedFilesToMaps(selected),
		"status":         "plan_ready",
		"message":        "Native desktop prepared the commit/push plan. Automatic git mutation is intentionally left behind an explicit confirmation flow.",
	}), nil
}

func (s *Service) GetJob(ctx context.Context, jobID string) (map[string]any, error) {
	_ = ctx
	job, ok := s.jobs.Get(jobID)
	if !ok {
		return nil, fmt.Errorf("job not found: %s", jobID)
	}
	return job, nil
}

func (s *Service) ProceedJob(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	_ = ctx
	return s.jobs.Proceed(jobID, requestID)
}

func (s *Service) GetApprovalPreview(ctx context.Context, jobID, requestID string) (map[string]any, error) {
	approval, err := s.jobs.GetPendingApproval(jobID, requestID)
	if err != nil {
		return nil, err
	}
	repoPath, _ := approval["workspace_repo_path"].(string)
	repoPath = strings.TrimSpace(repoPath)
	if repoPath == "" {
		return nativeResult("GetApprovalPreview", map[string]any{
			"request_id": requestID,
			"diff":       "",
			"message":    "No workspace repository path is attached to this approval request.",
		}), nil
	}
	diff, _ := s.git.Run(ctx, repoPath, "diff", "--stat")
	return nativeResult("GetApprovalPreview", map[string]any{
		"request_id": requestID,
		"diff_stat":  diff.Stdout,
		"message":    "Native desktop approval preview generated from local git diff stats.",
	}), nil
}

func (s *Service) submit(
	ctx context.Context,
	jobType string,
	payload any,
	runner func(context.Context, map[string]any) (map[string]any, error),
) (map[string]any, error) {
	payloadMap, err := structToMap(payload)
	if err != nil {
		return nil, err
	}
	return s.jobs.Submit(ctx, jobType, payloadMap, func(ctx context.Context, _ string, jobPayload map[string]any) (map[string]any, error) {
		return runner(ctx, jobPayload)
	})
}

func (s *Service) runFullReview(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	review, err := s.reviewDiffs(ctx, request)
	if err != nil {
		return nil, err
	}
	noChanges := false
	if count, ok := review["changed_file_count"].(int); ok && count == 0 {
		noChanges = true
	}
	result := map[string]any{
		"review":                              review["review"],
		"code_changes":                        []any{},
		"no_changes_required":                 noChanges,
		"resolution_status":                   "reviewed",
		"filter_relaxed_to_include_generated": false,
		"token_estimate":                      review["token_estimate"],
		"tokens_used":                         review["tokens_used"],
		"token_source":                        review["token_source"],
		"token_usage":                         review["token_usage"],
		"raw_response":                        review["review"],
		"usage":                               review["usage"],
		"changed_files":                       review["changed_files"],
		"diff_stat":                           review["diff_stat"],
	}
	return nativeResult("RunFullReview", result), nil
}

func (s *Service) reviewDiffs(ctx context.Context, request contracts.ConfigModel) (map[string]any, error) {
	if strings.TrimSpace(request.PullRequestID) != "" && !request.IsLocal {
		return nil, errors.New("native desktop mode reviews local checked-out changes; checkout the PR branch locally or enable local review")
	}
	repoRoot, err := cleanRepoPath(request.RepoPath)
	if err != nil {
		return nil, err
	}
	if err := s.git.EnsureGitRepo(ctx, repoRoot); err != nil {
		return nil, err
	}

	files, err := s.collectChangedFiles(ctx, repoRoot)
	if err != nil {
		return nil, err
	}
	diffResult, diffErr := s.git.Run(ctx, repoRoot, "diff", "--no-ext-diff", "--unified=80")
	if diffErr != nil {
		return nil, diffErr
	}
	cachedDiff, _ := s.git.Run(ctx, repoRoot, "diff", "--cached", "--no-ext-diff", "--unified=80")
	statResult, _ := s.git.Run(ctx, repoRoot, "diff", "--stat")

	diffText := strings.TrimSpace(diffResult.Stdout)
	if cached := strings.TrimSpace(cachedDiff.Stdout); cached != "" {
		if diffText != "" {
			diffText += "\n"
		}
		diffText += cached
	}
	stats := diffStats(diffText)
	findings := reviewFindings(diffText)
	reviewText := buildReviewText(files, stats, findings)
	tokenEstimate := estimateTokens(diffText + "\n" + reviewText)
	usage := s.usage.record("/desktop/review-diffs", request.AIModel, tokenEstimate, "native_estimate")

	return nativeResult("ReviewDiffs", map[string]any{
		"review":             reviewText,
		"ok":                 true,
		"changed_file_count": len(files),
		"changed_files":      changedFilesToMaps(files),
		"diff_stat":          strings.TrimSpace(statResult.Stdout),
		"findings":           findingsToMaps(findings),
		"token_estimate":     tokenEstimate,
		"tokens_used":        tokenEstimate,
		"token_source":       "native_estimate",
		"token_usage": map[string]any{
			"source":        "native_estimate",
			"input_tokens":  tokenEstimate,
			"output_tokens": 0,
		},
		"usage": usage,
	}), nil
}

func (s *Service) runStaticChecks(ctx context.Context, request contracts.StaticChecksRequestModel) (map[string]any, error) {
	runner, err := newStaticRunner(request.RepoPath, request.FilePaths)
	if err != nil {
		return nil, err
	}
	result := runner.Run(ctx)
	result["desktop_execution_mode"] = executionMode
	result["desktop_operation"] = "RunStaticChecks"
	return result, nil
}

func (s *Service) preparePRPlan(ctx context.Context, request contracts.RaiseNewPRRequestModel) (map[string]any, error) {
	files, err := s.collectChangedFiles(ctx, request.RepoPath)
	if err != nil {
		return nil, err
	}
	selected := selectChangedFiles(files, request.SelectedSerials)
	branches := branchPlan(request.FeatureID, request.TargetBranches, request.DefaultsPath)
	return nativeResult("RaiseNewPR", map[string]any{
		"status":              "plan_ready",
		"feature_id":          request.FeatureID,
		"target_branches":     branches,
		"selected_files":      changedFilesToMaps(selected),
		"selected_file_count": len(selected),
		"reviewer_ids":        request.ReviewerIDs,
		"reviewers_by_branch": request.ReviewerIDsByBranch,
		"commit_message":      request.CommitMessage,
		"message":             "Native desktop prepared the PR plan without starting FastAPI. Branch push and Azure PR creation should run from an explicit confirmed action.",
	}), nil
}

func (s *Service) collectChangedFiles(ctx context.Context, repoPath string) ([]changedFile, error) {
	repoRoot, err := cleanRepoPath(repoPath)
	if err != nil {
		return nil, err
	}
	if err := s.git.EnsureGitRepo(ctx, repoRoot); err != nil {
		return nil, err
	}
	result, err := s.git.Run(ctx, repoRoot, "status", "--porcelain=v1")
	if err != nil {
		return nil, err
	}
	return parsePorcelainStatus(result.Stdout), nil
}

func parsePorcelainStatus(output string) []changedFile {
	files := make([]changedFile, 0)
	for _, rawLine := range strings.Split(output, "\n") {
		line := strings.TrimRight(rawLine, "\r")
		if strings.TrimSpace(line) == "" || len(line) < 3 {
			continue
		}
		staged := strings.TrimSpace(line[0:1])
		unstaged := strings.TrimSpace(line[1:2])
		path := strings.TrimSpace(line[3:])
		if strings.Contains(path, " -> ") {
			parts := strings.Split(path, " -> ")
			path = strings.TrimSpace(parts[len(parts)-1])
		}
		files = append(files, changedFile{
			Serial:         len(files) + 1,
			FilePath:       filepath.ToSlash(path),
			Status:         statusLabel(staged, unstaged),
			StagedStatus:   staged,
			UnstagedStatus: unstaged,
		})
	}
	return files
}

func statusLabel(staged, unstaged string) string {
	joined := strings.TrimSpace(staged + unstaged)
	switch {
	case joined == "??":
		return "untracked"
	case strings.Contains(joined, "A"):
		return "added"
	case strings.Contains(joined, "D"):
		return "deleted"
	case strings.Contains(joined, "R"):
		return "renamed"
	case strings.Contains(joined, "M"):
		return "modified"
	default:
		return "changed"
	}
}

func buildReviewText(files []changedFile, stats map[string]int, findings []reviewFinding) string {
	var builder strings.Builder
	builder.WriteString("Native desktop review\n\n")
	if len(files) == 0 {
		builder.WriteString("No local changed files were detected in this repository.\n")
		return builder.String()
	}
	builder.WriteString(fmt.Sprintf("Changed files: %d\n", len(files)))
	builder.WriteString(fmt.Sprintf("Added lines: %d\n", stats["additions"]))
	builder.WriteString(fmt.Sprintf("Removed lines: %d\n\n", stats["deletions"]))
	builder.WriteString("Files:\n")
	for _, file := range files {
		builder.WriteString(fmt.Sprintf("- [%d] %s (%s)\n", file.Serial, file.FilePath, file.Status))
	}
	if len(findings) == 0 {
		builder.WriteString("\nNo obvious high-risk patterns were detected in the local diff. Review behavior and tests before merging.\n")
		return builder.String()
	}
	builder.WriteString("\nFindings:\n")
	for _, finding := range findings {
		if finding.File != "" {
			builder.WriteString(fmt.Sprintf("- %s: %s - %s\n", finding.Severity, finding.File, finding.Message))
		} else {
			builder.WriteString(fmt.Sprintf("- %s: %s\n", finding.Severity, finding.Message))
		}
	}
	return builder.String()
}

func reviewFindings(diffText string) []reviewFinding {
	checks := []struct {
		severity string
		pattern  *regexp.Regexp
		message  string
	}{
		{"high", regexp.MustCompile(`(?i)(password|secret|api[_-]?key|access[_-]?token|azure_pat)\s*[:=]`), "Potential credential-like value added."},
		{"medium", regexp.MustCompile(`(?i)\b(todo|fixme)\b`), "TODO/FIXME marker added in changed code."},
		{"medium", regexp.MustCompile(`\b(console\.log|fmt\.Println|print\()`), "Debug logging or print statement added."},
		{"high", regexp.MustCompile(`\bpanic\(`), "Panic call added; confirm this cannot crash user-facing workflows."},
	}
	findings := make([]reviewFinding, 0)
	currentFile := ""
	for _, line := range strings.Split(diffText, "\n") {
		if strings.HasPrefix(line, "+++ b/") {
			currentFile = strings.TrimPrefix(line, "+++ b/")
			continue
		}
		if !strings.HasPrefix(line, "+") || strings.HasPrefix(line, "+++") {
			continue
		}
		for _, check := range checks {
			if check.pattern.MatchString(line) {
				findings = append(findings, reviewFinding{
					Severity: check.severity,
					File:     currentFile,
					Message:  check.message,
				})
			}
		}
	}
	return dedupeFindings(findings)
}

func dedupeFindings(input []reviewFinding) []reviewFinding {
	seen := map[string]bool{}
	output := make([]reviewFinding, 0, len(input))
	for _, item := range input {
		key := item.Severity + "\x00" + item.File + "\x00" + item.Message
		if seen[key] {
			continue
		}
		seen[key] = true
		output = append(output, item)
	}
	return output
}

func diffStats(diffText string) map[string]int {
	stats := map[string]int{"additions": 0, "deletions": 0}
	for _, line := range strings.Split(diffText, "\n") {
		switch {
		case strings.HasPrefix(line, "+++") || strings.HasPrefix(line, "---"):
			continue
		case strings.HasPrefix(line, "+"):
			stats["additions"]++
		case strings.HasPrefix(line, "-"):
			stats["deletions"]++
		}
	}
	return stats
}

func estimateTokens(text string) int {
	trimmed := strings.TrimSpace(text)
	if trimmed == "" {
		return 0
	}
	tokens := len([]rune(trimmed)) / 4
	if tokens < 1 {
		return 1
	}
	return tokens
}

func nativeResult(operation string, result map[string]any) map[string]any {
	if result == nil {
		result = map[string]any{}
	}
	result["desktop_execution_mode"] = executionMode
	result["desktop_operation"] = operation
	return result
}

func changedFilesToMaps(files []changedFile) []map[string]any {
	items := make([]map[string]any, 0, len(files))
	for _, file := range files {
		items = append(items, map[string]any{
			"serial":          file.Serial,
			"file_path":       file.FilePath,
			"status":          file.Status,
			"staged_status":   file.StagedStatus,
			"unstaged_status": file.UnstagedStatus,
		})
	}
	return items
}

func findingsToMaps(findings []reviewFinding) []map[string]any {
	items := make([]map[string]any, 0, len(findings))
	for _, finding := range findings {
		items = append(items, map[string]any{
			"severity": finding.Severity,
			"file":     finding.File,
			"message":  finding.Message,
		})
	}
	return items
}

func selectChangedFiles(files []changedFile, serials []int) []changedFile {
	if len(serials) == 0 {
		return files
	}
	wanted := map[int]bool{}
	for _, serial := range serials {
		wanted[serial] = true
	}
	selected := make([]changedFile, 0, len(serials))
	for _, file := range files {
		if wanted[file.Serial] {
			selected = append(selected, file)
		}
	}
	return selected
}

func branchPlan(featureID int, requested []string, defaultsPath string) []map[string]any {
	targets := requested
	if len(targets) == 0 {
		targets = []string{"main", "prerelease"}
	}
	sort.Strings(targets)
	plan := make([]map[string]any, 0, len(targets))
	for _, target := range targets {
		target = strings.TrimSpace(target)
		if target == "" {
			continue
		}
		branchName := fmt.Sprintf("Feature/#%d/%s", featureID, safeBranchToken(target))
		plan = append(plan, map[string]any{
			"target_key":    target,
			"base_branch":   target,
			"branch_name":   branchName,
			"defaults_path": defaultsPath,
		})
	}
	return plan
}

func safeBranchToken(value string) string {
	value = strings.ToLower(strings.TrimSpace(value))
	value = strings.ReplaceAll(value, "\\", "/")
	value = strings.ReplaceAll(value, " ", "-")
	value = regexp.MustCompile(`[^a-z0-9._/-]+`).ReplaceAllString(value, "-")
	value = strings.Trim(value, "-/")
	if value == "" {
		return "target"
	}
	return value
}

func buildPatchedContent(original string, request contracts.ApplyChangesModel) (string, string, error) {
	oldContent := request.OldContent
	if oldContent != "" && strings.Contains(original, oldContent) {
		return strings.Replace(original, oldContent, request.NewContent, 1), "old_content", nil
	}
	if oldContent != "" && !request.AllowFallbackSearch {
		return "", "", errors.New("old_content does not match current file content")
	}

	lines := splitPreserveLines(original)
	startLine := request.OldStartLineNumber
	if startLine <= 0 {
		startLine = request.LineNumber
	}
	if startLine <= 0 {
		return "", "", errors.New("line_number or old_start_line_number is required when old_content is not matched")
	}
	start := startLine - 1
	if start < 0 || start > len(lines) {
		return "", "", fmt.Errorf("line number %d is outside file range", startLine)
	}
	removeCount := request.NumberOfLinesRemovedFromOld
	if removeCount < 0 {
		removeCount = 0
	}
	end := start + removeCount
	if end > len(lines) {
		end = len(lines)
	}
	newLines := splitPatchLines(request.NewContent)
	nextLines := make([]string, 0, len(lines)-removeCount+len(newLines))
	nextLines = append(nextLines, lines[:start]...)
	nextLines = append(nextLines, newLines...)
	nextLines = append(nextLines, lines[end:]...)
	return strings.Join(nextLines, ""), "line_range", nil
}

func splitPreserveLines(text string) []string {
	if text == "" {
		return []string{}
	}
	parts := strings.SplitAfter(text, "\n")
	if parts[len(parts)-1] == "" {
		parts = parts[:len(parts)-1]
	}
	return parts
}

func splitPatchLines(text string) []string {
	if text == "" {
		return []string{}
	}
	parts := strings.SplitAfter(text, "\n")
	if parts[len(parts)-1] == "" {
		parts = parts[:len(parts)-1]
	}
	if len(parts) > 0 && !strings.HasSuffix(parts[len(parts)-1], "\n") {
		parts[len(parts)-1] += "\n"
	}
	return parts
}

func writeBackup(repoRoot, rel string, content []byte) (string, error) {
	stamp := time.Now().Format("20060102_150405")
	backupPath := filepath.Join(repoRoot, ".agentic-backups", stamp, filepath.FromSlash(rel)+".bak")
	if err := os.MkdirAll(filepath.Dir(backupPath), 0o755); err != nil {
		return "", err
	}
	if err := os.WriteFile(backupPath, content, 0o600); err != nil {
		return "", err
	}
	return backupPath, nil
}

func cleanRepoPath(repoPath string) (string, error) {
	trimmed := strings.TrimSpace(repoPath)
	if trimmed == "" {
		return "", errors.New("repo_path is required")
	}
	abs, err := filepath.Abs(trimmed)
	if err != nil {
		return "", err
	}
	info, err := os.Stat(abs)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", fmt.Errorf("repo_path is not a directory: %s", abs)
	}
	return abs, nil
}

func resolveFileInRepo(repoRoot, filePath string) (string, string, error) {
	trimmed := strings.TrimSpace(filePath)
	if trimmed == "" {
		return "", "", errors.New("file_path is required")
	}
	candidate := filepath.Clean(filepath.FromSlash(trimmed))
	if !filepath.IsAbs(candidate) {
		candidate = filepath.Join(repoRoot, candidate)
	}
	abs, err := filepath.Abs(candidate)
	if err != nil {
		return "", "", err
	}
	rel, err := filepath.Rel(repoRoot, abs)
	if err != nil {
		return "", "", err
	}
	if rel == "." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || rel == ".." || filepath.IsAbs(rel) {
		return "", "", fmt.Errorf("file_path is outside repo: %s", filePath)
	}
	return abs, filepath.ToSlash(rel), nil
}

func structToMap(input any) (map[string]any, error) {
	raw, err := json.Marshal(input)
	if err != nil {
		return nil, err
	}
	var output map[string]any
	if err := json.Unmarshal(raw, &output); err != nil {
		return nil, err
	}
	return output, nil
}

func mapToStruct(input map[string]any, output any) error {
	raw, err := json.Marshal(input)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, output)
}

func (u *usageTracker) record(endpoint, model string, tokens int, source string) map[string]any {
	u.mu.Lock()
	defer u.mu.Unlock()
	if tokens < 0 {
		tokens = 0
	}
	event := map[string]any{
		"timestamp":              time.Now().Unix(),
		"endpoint":               endpoint,
		"model":                  strings.TrimSpace(model),
		"tokens_used":            tokens,
		"token_source":           source,
		"input_tokens":           tokens,
		"output_tokens":          0,
		"estimated_cost_usd":     0.0,
		"desktop_execution_mode": executionMode,
	}
	u.requestCount++
	u.totalTokens += tokens
	u.recentRequest = append([]map[string]any{event}, u.recentRequest...)
	if len(u.recentRequest) > 100 {
		u.recentRequest = u.recentRequest[:100]
	}
	return event
}

func (u *usageTracker) snapshot() map[string]any {
	u.mu.Lock()
	defer u.mu.Unlock()
	recent := make([]map[string]any, len(u.recentRequest))
	copy(recent, u.recentRequest)
	return map[string]any{
		"summary": map[string]any{
			"request_count":                 u.requestCount,
			"total_tokens_used":             u.totalTokens,
			"total_estimated_cost_usd":      u.totalCostUSD,
			"token_budget":                  0,
			"cost_budget_usd":               0,
			"token_budget_remaining":        0,
			"cost_budget_remaining_usd":     0,
			"token_budget_used_percent":     0,
			"cost_budget_used_percent":      0,
			"desktop_usage_metering_source": "native_in_memory",
		},
		"recent_requests": recent,
	}
}
