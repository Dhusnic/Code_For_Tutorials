package native

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const (
	maxCommandOutputChars = 12000
	maxFilesPerCheck      = 2000
)

type staticRunner struct {
	repoRoot    string
	targetFiles []string
}

type commandExecution struct {
	Language   string `json:"language"`
	Tool       string `json:"tool"`
	Command    string `json:"command"`
	ReturnCode int    `json:"return_code"`
	Status     string `json:"status"`
	DurationMS int64  `json:"duration_ms"`
	Stdout     string `json:"stdout"`
	Stderr     string `json:"stderr"`
}

type staticIssue struct {
	Severity string `json:"severity"`
	Language string `json:"language"`
	Tool     string `json:"tool"`
	File     string `json:"file"`
	Message  string `json:"message"`
	Line     int    `json:"line,omitempty"`
	Column   int    `json:"column,omitempty"`
}

var ignoredStaticDirs = map[string]bool{
	".git":         true,
	".hg":          true,
	".svn":         true,
	"node_modules": true,
	".venv":        true,
	"venv":         true,
	"__pycache__":  true,
	"dist":         true,
	"build":        true,
	"out":          true,
	".next":        true,
	".angular":     true,
	".idea":        true,
	".vscode":      true,
}

func newStaticRunner(repoPath string, filePaths []string) (*staticRunner, error) {
	repoRoot, err := cleanRepoPath(repoPath)
	if err != nil {
		return nil, err
	}
	targets, err := resolveTargetFiles(repoRoot, filePaths)
	if err != nil {
		return nil, err
	}
	return &staticRunner{
		repoRoot:    repoRoot,
		targetFiles: targets,
	}, nil
}

func (r *staticRunner) Run(ctx context.Context) map[string]any {
	started := time.Now()
	files := r.files()
	languages := detectLanguages(r.repoRoot, files)
	commands := make([]commandExecution, 0)
	issues := make([]staticIssue, 0)

	if languages["json"] {
		execs, found := r.runJSONChecks(files)
		commands = append(commands, execs...)
		issues = append(issues, found...)
	}
	if languages["javascript"] {
		execs, found := r.runNodeChecks(ctx, files)
		commands = append(commands, execs...)
		issues = append(issues, found...)
	}
	if languages["typescript"] || languages["angular"] {
		execs, found := r.runTypeScriptChecks(ctx)
		commands = append(commands, execs...)
		issues = append(issues, found...)
	}
	if languages["python"] {
		execs, found := r.runPythonChecks(ctx, files)
		commands = append(commands, execs...)
		issues = append(issues, found...)
	}
	if languages["go"] {
		execRecord, found := r.runGoChecks(ctx)
		commands = append(commands, execRecord)
		issues = append(issues, found...)
	}

	sort.Slice(issues, func(i, j int) bool {
		return severityRank(issues[i].Severity) < severityRank(issues[j].Severity)
	})
	majorIssues := make([]staticIssue, 0)
	for _, issue := range issues {
		if issue.Severity == "critical" || issue.Severity == "high" {
			majorIssues = append(majorIssues, issue)
		}
	}

	return map[string]any{
		"repo_path":           r.repoRoot,
		"languages_detected":  sortedLanguageNames(languages),
		"commands":            commandMaps(commands),
		"issues":              issueMaps(issues),
		"major_issues":        issueMaps(majorIssues),
		"summary":             staticSummary(commands, issues, time.Since(started)),
		"static_check_engine": "native_go",
	}
}

func (r *staticRunner) files() []string {
	if len(r.targetFiles) > 0 {
		return append([]string(nil), r.targetFiles...)
	}
	files := make([]string, 0)
	_ = filepath.WalkDir(r.repoRoot, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if entry.IsDir() {
			if ignoredStaticDirs[entry.Name()] && path != r.repoRoot {
				return filepath.SkipDir
			}
			return nil
		}
		files = append(files, path)
		return nil
	})
	sort.Strings(files)
	return files
}

func (r *staticRunner) runJSONChecks(files []string) ([]commandExecution, []staticIssue) {
	executions := make([]commandExecution, 0)
	issues := make([]staticIssue, 0)
	for _, file := range filterByExt(files, ".json") {
		started := time.Now()
		raw, err := os.ReadFile(file)
		record := commandExecution{
			Language:   "json",
			Tool:       "json-valid",
			Command:    "native json validation " + relToSlash(r.repoRoot, file),
			ReturnCode: 0,
			Status:     "ok",
			DurationMS: time.Since(started).Milliseconds(),
		}
		if err != nil {
			record.ReturnCode = 1
			record.Status = "error"
			record.Stderr = truncateOutput(err.Error())
			issues = append(issues, staticIssue{
				Severity: "high",
				Language: "json",
				Tool:     record.Tool,
				File:     relToSlash(r.repoRoot, file),
				Message:  err.Error(),
			})
		} else if !json.Valid(raw) {
			record.ReturnCode = 1
			record.Status = "failed"
			record.Stderr = "invalid JSON"
			issues = append(issues, staticIssue{
				Severity: "high",
				Language: "json",
				Tool:     record.Tool,
				File:     relToSlash(r.repoRoot, file),
				Message:  "Invalid JSON document.",
			})
		}
		executions = append(executions, record)
	}
	return executions, issues
}

func (r *staticRunner) runNodeChecks(ctx context.Context, files []string) ([]commandExecution, []staticIssue) {
	node, ok := findExecutable("node")
	if !ok {
		return []commandExecution{skippedCommand("javascript", "node-check", "node --check <file>", "node not found in PATH; JavaScript syntax checks skipped.")}, nil
	}
	executions := make([]commandExecution, 0)
	issues := make([]staticIssue, 0)
	for _, file := range filterByExt(files, ".js", ".mjs", ".cjs") {
		record := runCommand(ctx, r.repoRoot, "javascript", "node-check", node, "--check", file)
		executions = append(executions, record)
		if record.ReturnCode != 0 {
			issues = append(issues, genericIssues(record, "javascript", relToSlash(r.repoRoot, file))...)
		}
	}
	return executions, issues
}

func (r *staticRunner) runTypeScriptChecks(ctx context.Context) ([]commandExecution, []staticIssue) {
	npx, ok := findExecutable("npx")
	if !ok {
		return []commandExecution{skippedCommand("typescript", "tsc", "npx tsc --noEmit --pretty false -p <tsconfig>", "npx not found in PATH; TypeScript checks skipped.")}, nil
	}
	configs := discoverTSConfigs(r.repoRoot)
	if len(configs) == 0 {
		return []commandExecution{skippedCommand("typescript", "tsc", "npx tsc --noEmit --pretty false -p <tsconfig>", "No tsconfig*.json found; TypeScript checks skipped.")}, nil
	}
	executions := make([]commandExecution, 0, len(configs))
	issues := make([]staticIssue, 0)
	for _, config := range configs {
		record := runCommand(ctx, r.repoRoot, "typescript", "tsc", npx, "tsc", "--noEmit", "--pretty", "false", "-p", config)
		executions = append(executions, record)
		if record.ReturnCode != 0 {
			issues = append(issues, parseTSCIssues(record)...)
		}
	}
	return executions, issues
}

func (r *staticRunner) runPythonChecks(ctx context.Context, files []string) ([]commandExecution, []staticIssue) {
	python, ok := findExecutable("python")
	if !ok {
		return []commandExecution{skippedCommand("python", "py_compile", "python -m py_compile <file>", "python not found in PATH; Python syntax checks skipped.")}, nil
	}
	executions := make([]commandExecution, 0)
	issues := make([]staticIssue, 0)
	for _, file := range filterByExt(files, ".py") {
		record := runCommand(ctx, r.repoRoot, "python", "py_compile", python, "-m", "py_compile", file)
		executions = append(executions, record)
		if record.ReturnCode != 0 {
			issues = append(issues, genericIssues(record, "python", relToSlash(r.repoRoot, file))...)
		}
	}
	return executions, issues
}

func (r *staticRunner) runGoChecks(ctx context.Context) (commandExecution, []staticIssue) {
	goBin, ok := findExecutable("go")
	if !ok {
		return skippedCommand("go", "go-test", "go test ./...", "go not found in PATH; Go checks skipped."), nil
	}
	if _, err := os.Stat(filepath.Join(r.repoRoot, "go.mod")); err != nil {
		return skippedCommand("go", "go-test", "go test ./...", "No go.mod found; Go checks skipped."), nil
	}
	record := runCommand(ctx, r.repoRoot, "go", "go-test", goBin, "test", "./...")
	if record.ReturnCode != 0 {
		return record, genericIssues(record, "go", "")
	}
	return record, nil
}

func resolveTargetFiles(repoRoot string, filePaths []string) ([]string, error) {
	if len(filePaths) == 0 {
		return nil, nil
	}
	targets := make([]string, 0, len(filePaths))
	seen := map[string]bool{}
	for _, item := range filePaths {
		item = strings.TrimSpace(item)
		if item == "" {
			continue
		}
		candidate := filepath.Clean(filepath.FromSlash(item))
		if !filepath.IsAbs(candidate) {
			candidate = filepath.Join(repoRoot, candidate)
		}
		abs, err := filepath.Abs(candidate)
		if err != nil {
			return nil, err
		}
		rel, err := filepath.Rel(repoRoot, abs)
		if err != nil {
			return nil, err
		}
		if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
			return nil, errors.New("static check file path is outside repo: " + item)
		}
		info, err := os.Stat(abs)
		if err != nil || info.IsDir() {
			continue
		}
		if !seen[abs] {
			targets = append(targets, abs)
			seen[abs] = true
		}
	}
	sort.Strings(targets)
	return targets, nil
}

func detectLanguages(repoRoot string, files []string) map[string]bool {
	languages := map[string]bool{}
	for _, file := range files {
		switch strings.ToLower(filepath.Ext(file)) {
		case ".json":
			languages["json"] = true
		case ".js", ".mjs", ".cjs":
			languages["javascript"] = true
		case ".ts", ".tsx":
			languages["typescript"] = true
		case ".py":
			languages["python"] = true
		case ".go":
			languages["go"] = true
		}
	}
	if _, err := os.Stat(filepath.Join(repoRoot, "angular.json")); err == nil {
		languages["angular"] = true
		languages["typescript"] = true
	}
	return languages
}

func filterByExt(files []string, extensions ...string) []string {
	allowed := map[string]bool{}
	for _, ext := range extensions {
		allowed[strings.ToLower(ext)] = true
	}
	matches := make([]string, 0)
	for _, file := range files {
		if allowed[strings.ToLower(filepath.Ext(file))] {
			matches = append(matches, file)
			if len(matches) >= maxFilesPerCheck {
				break
			}
		}
	}
	return matches
}

func discoverTSConfigs(repoRoot string) []string {
	configs := make([]string, 0)
	_ = filepath.WalkDir(repoRoot, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if entry.IsDir() {
			if ignoredStaticDirs[entry.Name()] && path != repoRoot {
				return filepath.SkipDir
			}
			return nil
		}
		name := strings.ToLower(entry.Name())
		if strings.HasPrefix(name, "tsconfig") && strings.HasSuffix(name, ".json") {
			configs = append(configs, path)
		}
		return nil
	})
	sort.Slice(configs, func(i, j int) bool {
		iBase := filepath.Base(configs[i]) == "tsconfig.json"
		jBase := filepath.Base(configs[j]) == "tsconfig.json"
		if iBase != jBase {
			return iBase
		}
		return configs[i] < configs[j]
	})
	if len(configs) > 10 {
		return configs[:10]
	}
	return configs
}

func findExecutable(name string) (string, bool) {
	candidates := []string{name}
	if os.PathListSeparator == ';' {
		candidates = []string{name + ".cmd", name + ".exe", name + ".bat", name}
	}
	for _, candidate := range candidates {
		if resolved, err := exec.LookPath(candidate); err == nil {
			return resolved, true
		}
	}
	return "", false
}

func runCommand(ctx context.Context, cwd, language, tool string, args ...string) commandExecution {
	started := time.Now()
	commandCtx, cancel := context.WithTimeout(ctx, 3*time.Minute)
	defer cancel()
	cmd := exec.CommandContext(commandCtx, args[0], args[1:]...)
	cmd.Dir = cwd
	output, err := cmd.CombinedOutput()
	duration := time.Since(started)
	status := "ok"
	exitCode := 0
	if err != nil {
		status = "failed"
		exitCode = 1
		if cmd.ProcessState != nil {
			exitCode = cmd.ProcessState.ExitCode()
		}
	}
	if commandCtx.Err() == context.DeadlineExceeded {
		status = "timeout"
		exitCode = 124
	}
	text := truncateOutput(string(output))
	return commandExecution{
		Language:   language,
		Tool:       tool,
		Command:    strings.Join(args, " "),
		ReturnCode: exitCode,
		Status:     status,
		DurationMS: duration.Milliseconds(),
		Stdout:     text,
		Stderr:     text,
	}
}

func skippedCommand(language, tool, command, reason string) commandExecution {
	return commandExecution{
		Language:   language,
		Tool:       tool,
		Command:    command,
		ReturnCode: 0,
		Status:     "skipped",
		DurationMS: 0,
		Stdout:     "",
		Stderr:     reason,
	}
}

func parseTSCIssues(record commandExecution) []staticIssue {
	pattern := regexp.MustCompile(`(?m)^(?P<file>.*\.(?:ts|tsx|js|jsx))\((?P<line>\d+),(?P<column>\d+)\):\s*error\s*(?P<code>TS\d+):\s*(?P<message>.+)$`)
	matches := pattern.FindAllStringSubmatch(record.Stdout+"\n"+record.Stderr, 150)
	issues := make([]staticIssue, 0, len(matches))
	for _, match := range matches {
		issues = append(issues, staticIssue{
			Severity: "high",
			Language: "typescript",
			Tool:     record.Tool,
			File:     match[1],
			Line:     safeInt(match[2]),
			Column:   safeInt(match[3]),
			Message:  match[4] + ": " + match[5],
		})
	}
	if len(issues) == 0 {
		return genericIssues(record, "typescript", "")
	}
	return issues
}

func genericIssues(record commandExecution, language, defaultFile string) []staticIssue {
	text := strings.TrimSpace(record.Stdout + "\n" + record.Stderr)
	if text == "" {
		return []staticIssue{{
			Severity: "high",
			Language: language,
			Tool:     record.Tool,
			File:     defaultFile,
			Message:  record.Tool + " failed without diagnostics.",
		}}
	}
	issues := make([]staticIssue, 0)
	fileLine := regexp.MustCompile(`(?P<file>[^:\s][^:]*)[:(](?P<line>\d+)(?:[: ,](?P<column>\d+))?[):]?\s*(?P<message>.*)`)
	for _, rawLine := range strings.Split(text, "\n") {
		line := strings.TrimSpace(rawLine)
		if line == "" {
			continue
		}
		issue := staticIssue{
			Severity: inferSeverity(line, record.ReturnCode),
			Language: language,
			Tool:     record.Tool,
			File:     defaultFile,
			Message:  line,
		}
		if match := fileLine.FindStringSubmatch(line); match != nil {
			issue.File = match[1]
			issue.Line = safeInt(match[2])
			issue.Column = safeInt(match[3])
			issue.Message = strings.TrimSpace(match[4])
			if issue.Message == "" {
				issue.Message = line
			}
		}
		issues = append(issues, issue)
		if len(issues) >= 150 {
			break
		}
	}
	return issues
}

func staticSummary(commands []commandExecution, issues []staticIssue, duration time.Duration) map[string]any {
	summary := map[string]any{
		"commands_total":   len(commands),
		"commands_failed":  0,
		"issues_total":     len(issues),
		"issues_critical":  0,
		"issues_high":      0,
		"issues_medium":    0,
		"issues_low":       0,
		"duration_ms":      duration.Milliseconds(),
		"commands_skipped": 0,
	}
	for _, command := range commands {
		if command.Status == "failed" || command.Status == "error" || command.Status == "timeout" {
			summary["commands_failed"] = summary["commands_failed"].(int) + 1
		}
		if command.Status == "skipped" {
			summary["commands_skipped"] = summary["commands_skipped"].(int) + 1
		}
	}
	for _, issue := range issues {
		key := "issues_" + issue.Severity
		if current, ok := summary[key].(int); ok {
			summary[key] = current + 1
		}
	}
	return summary
}

func commandMaps(commands []commandExecution) []map[string]any {
	items := make([]map[string]any, 0, len(commands))
	for _, command := range commands {
		items = append(items, map[string]any{
			"language":    command.Language,
			"tool":        command.Tool,
			"command":     command.Command,
			"return_code": command.ReturnCode,
			"status":      command.Status,
			"duration_ms": command.DurationMS,
			"stdout":      command.Stdout,
			"stderr":      command.Stderr,
		})
	}
	return items
}

func issueMaps(issues []staticIssue) []map[string]any {
	items := make([]map[string]any, 0, len(issues))
	for _, issue := range issues {
		item := map[string]any{
			"severity": issue.Severity,
			"language": issue.Language,
			"tool":     issue.Tool,
			"file":     issue.File,
			"message":  issue.Message,
		}
		if issue.Line > 0 {
			item["line"] = issue.Line
		}
		if issue.Column > 0 {
			item["column"] = issue.Column
		}
		items = append(items, item)
	}
	return items
}

func sortedLanguageNames(languages map[string]bool) []string {
	names := make([]string, 0, len(languages))
	for name := range languages {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func relToSlash(root, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return filepath.ToSlash(path)
	}
	return filepath.ToSlash(rel)
}

func inferSeverity(line string, returnCode int) string {
	text := strings.ToLower(line)
	if strings.Contains(text, "syntaxerror") || strings.Contains(text, "fatal") {
		return "critical"
	}
	if strings.Contains(text, "error") || returnCode != 0 {
		return "high"
	}
	if strings.Contains(text, "warning") {
		return "medium"
	}
	return "low"
}

func severityRank(value string) int {
	switch value {
	case "critical":
		return 0
	case "high":
		return 1
	case "medium":
		return 2
	case "low":
		return 3
	default:
		return 99
	}
}

func truncateOutput(text string) string {
	if len(text) <= maxCommandOutputChars {
		return text
	}
	return text[:maxCommandOutputChars] + "\n...[truncated]..."
}

func safeInt(value string) int {
	value = strings.TrimSpace(value)
	if value == "" {
		return 0
	}
	parsed, err := strconv.Atoi(value)
	if err != nil {
		return 0
	}
	return parsed
}
