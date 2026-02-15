"""Command-based static checks for repository hygiene and syntax safety.

Supported language families and checks:
- Python:
  - `python -m py_compile <file>` (per-file for accurate file/line syntax errors)
  - Optional `ruff check <repo>` when `ruff` is available.
- TypeScript:
  - `npx tsc --noEmit --pretty false -p <tsconfig>`
- Angular:
  - Detected by `angular.json`, uses TypeScript compiler checks.
  - Optional `npx ng lint --configuration production` when Angular CLI is available.
- JavaScript:
  - `node --check` on each discovered `.js/.mjs/.cjs` file.
- JSON:
  - `python -m json.tool <file>` on each discovered `.json` file.

The runner executes checks using subprocess commands only (no AI, no AST parsing),
captures outputs, classifies issues, and returns a structured report suitable for UI.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandExecution:
    """One command execution record."""

    language: str
    tool: str
    command: str
    return_code: int
    status: str
    duration_ms: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class StaticIssue:
    """Normalized issue extracted from command output."""

    severity: str
    language: str
    tool: str
    file: str
    message: str
    line: int | None = None
    column: int | None = None


class StaticCheckRunner:
    """Runs deterministic static checks using language-specific CLI commands."""

    MAX_OUTPUT_CHARS = 12_000
    MAX_ISSUES_PER_COMMAND = 150
    MAX_JS_FILES_FOR_NODE_CHECK = 2_000
    MAX_JSON_FILES_FOR_JSON_CHECK = 2_000

    JS_EXTENSIONS = {".js", ".mjs", ".cjs"}
    TS_EXTENSIONS = {".ts", ".tsx"}
    PY_EXTENSIONS = {".py"}

    IGNORE_DIRS = {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        "out",
        ".next",
        ".angular",
        ".idea",
        ".vscode",
    }

    def __init__(self, repo_path: str) -> None:
        """
        Initialize checker with repository path.

        Args:
            repo_path: Repository root directory.
        """
        self.repo_path = Path(repo_path).expanduser().resolve()
        if not self.repo_path.exists() or not self.repo_path.is_dir():
            raise ValueError(f"Invalid repository path: {self.repo_path}")

    def run_checks(self, file_paths: Optional[List[str]] = None) -> Dict[str, object]:
        """
        Run all applicable static checks for the repository.

        Returns:
            Dictionary with:
            - `repo_path`
            - `languages_detected`
            - `commands`
            - `issues`
            - `major_issues`
            - `summary`
        """
        started_at = time.monotonic()
        target_files = self._resolve_target_files(file_paths)
        languages = self._detect_languages(target_files=target_files)
        executions: List[CommandExecution] = []
        issues: List[StaticIssue] = []

        try:
            if "python" in languages:
                py_exec, py_issues = self._run_python_checks(target_files=target_files)
                executions.extend(py_exec)
                issues.extend(py_issues)

            if "typescript" in languages or "angular" in languages:
                ts_exec, ts_issues = self._run_typescript_checks(
                    is_angular="angular" in languages,
                    target_files=target_files,
                )
                executions.extend(ts_exec)
                issues.extend(ts_issues)

            if "javascript" in languages:
                js_exec, js_issues = self._run_javascript_checks(target_files=target_files)
                executions.extend(js_exec)
                issues.extend(js_issues)

            if "json" in languages:
                json_exec, json_issues = self._run_json_checks(target_files=target_files)
                executions.extend(json_exec)
                issues.extend(json_issues)
        except Exception:
            LOGGER.exception("Unexpected static check failure")
            issues.append(
                StaticIssue(
                    severity="high",
                    language="system",
                    tool="static-check-runner",
                    file="",
                    message="Static checks aborted due to an internal runner failure.",
                )
            )

        summary = self._build_summary(executions, issues, started_at)
        major_issues = [issue for issue in issues if issue.severity in {"critical", "high"}]
        major_issues.sort(key=self._severity_sort_key)
        issues.sort(key=self._severity_sort_key)

        return {
            "repo_path": str(self.repo_path),
            "languages_detected": sorted(languages),
            "commands": [asdict(record) for record in executions],
            "issues": [asdict(issue) for issue in issues],
            "major_issues": [asdict(issue) for issue in major_issues],
            "summary": summary,
        }

    def _detect_languages(self, *, target_files: Optional[List[Path]] = None) -> set[str]:
        """Detect repository language families by extensions and config files."""
        languages: set[str] = set()
        has_angular_json = (self.repo_path / "angular.json").exists()

        file_iterable = target_files if target_files is not None else list(self._iter_repo_files())
        for file_path in file_iterable:
            suffix = file_path.suffix.lower()
            if suffix in self.PY_EXTENSIONS:
                languages.add("python")
            elif suffix in self.TS_EXTENSIONS:
                languages.add("typescript")
            elif suffix in self.JS_EXTENSIONS:
                languages.add("javascript")
            elif suffix == ".json":
                languages.add("json")

        if has_angular_json and (
            target_files is None
            or any(path.suffix.lower() in self.TS_EXTENSIONS.union(self.JS_EXTENSIONS) for path in file_iterable)
        ):
            languages.add("angular")
            languages.add("typescript")

        return languages

    def _iter_repo_files(self):
        """Yield repository files while excluding known large/vendor folders."""
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
            for filename in files:
                yield Path(root) / filename

    def _resolve_target_files(self, file_paths: Optional[List[str]]) -> Optional[List[Path]]:
        """Resolve optional caller-provided file paths within repository root."""
        if not file_paths:
            return None

        resolved: List[Path] = []
        seen: set[Path] = set()
        for item in file_paths:
            if not item or not str(item).strip():
                continue
            candidate = Path(item)
            if not candidate.is_absolute():
                candidate = (self.repo_path / str(item).lstrip("/\\")).resolve()
            else:
                candidate = candidate.resolve()

            if self.repo_path not in candidate.parents and candidate != self.repo_path:
                LOGGER.warning("Skipping path outside repository: %s", item)
                continue
            if not candidate.exists() or not candidate.is_file():
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            resolved.append(candidate)

        return resolved

    def _files_for_language(
        self,
        target_files: Optional[List[Path]],
        suffixes: set[str],
    ) -> List[Path]:
        """Get language files either from full repo scan or provided targets."""
        return self._discover_files_by_suffixes(suffixes, limit=50_000, target_files=target_files)

    def _run_python_checks(
        self,
        *,
        target_files: Optional[List[Path]] = None,
    ) -> tuple[List[CommandExecution], List[StaticIssue]]:
        """Execute Python syntax/lint checks."""
        executions: List[CommandExecution] = []
        issues: List[StaticIssue] = []
        python_files = self._files_for_language(target_files, self.PY_EXTENSIONS)
        python_exec = self._python_executable()

        for file_path in python_files:
            compile_cmd = [python_exec, "-m", "py_compile", str(file_path)]
            compile_exec = self._run_command(language="python", tool="py_compile", args=compile_cmd)
            executions.append(compile_exec)
            if compile_exec.return_code != 0:
                issues.extend(self._parse_py_compile_output(compile_exec, default_file=str(file_path)))

        if shutil.which("ruff") and (target_files is None or python_files):
            ruff_cmd = ["ruff", "check"]
            if target_files is None:
                ruff_cmd.append(str(self.repo_path))
            else:
                ruff_cmd.extend(str(path) for path in python_files)
            ruff_exec = self._run_command(language="python", tool="ruff", args=ruff_cmd)
            executions.append(ruff_exec)
            issues.extend(self._parse_ruff_output(ruff_exec))
        else:
            executions.append(
                CommandExecution(
                    language="python",
                    tool="ruff",
                    command="ruff check <repo>",
                    return_code=0,
                    status="skipped",
                    duration_ms=0,
                    stdout="",
                    stderr=(
                        "ruff not found in PATH; skipped."
                        if not shutil.which("ruff")
                        else "No Python files in selected target scope; skipped."
                    ),
                )
            )

        return executions, issues

    def _run_typescript_checks(
        self,
        *,
        is_angular: bool,
        target_files: Optional[List[Path]] = None,
    ) -> tuple[List[CommandExecution], List[StaticIssue]]:
        """Execute TypeScript (and Angular optional) checks."""
        executions: List[CommandExecution] = []
        issues: List[StaticIssue] = []

        tsconfig_paths = self._discover_tsconfig_paths(target_files=target_files)
        npx_executable = self._resolve_node_cli("npx")
        if not npx_executable:
            executions.append(
                CommandExecution(
                    language="typescript",
                    tool="tsc",
                    command="npx tsc --noEmit --pretty false -p <tsconfig>",
                    return_code=0,
                    status="skipped",
                    duration_ms=0,
                    stdout="",
                    stderr="npx not found in PATH; TypeScript checks skipped.",
                )
            )
        elif not tsconfig_paths:
            executions.append(
                CommandExecution(
                    language="typescript",
                    tool="tsc",
                    command="npx tsc --noEmit --pretty false -p <tsconfig>",
                    return_code=0,
                    status="skipped",
                    duration_ms=0,
                    stdout="",
                    stderr="No tsconfig*.json found; TypeScript compiler check skipped.",
                )
            )
        else:
            for tsconfig in tsconfig_paths:
                tsc_cmd = [npx_executable, "tsc", "--noEmit", "--pretty", "false", "-p", str(tsconfig)]
                exec_rec = self._run_command(language="typescript", tool="tsc", args=tsc_cmd)
                executions.append(exec_rec)
                issues.extend(self._parse_tsc_output(exec_rec))

        if is_angular:
            if npx_executable and (self.repo_path / "angular.json").exists():
                ng_cmd = [npx_executable, "ng", "lint", "--configuration", "production"]
                ng_exec = self._run_command(language="angular", tool="ng-lint", args=ng_cmd)
                executions.append(ng_exec)
                issues.extend(self._parse_generic_errors(ng_exec, language="angular"))
            else:
                executions.append(
                    CommandExecution(
                        language="angular",
                        tool="ng-lint",
                        command="npx ng lint --configuration production",
                        return_code=0,
                        status="skipped",
                        duration_ms=0,
                        stdout="",
                        stderr="Angular CLI checks skipped (npx/angular.json missing).",
                    )
                )

        return executions, issues

    def _run_javascript_checks(
        self,
        *,
        target_files: Optional[List[Path]] = None,
    ) -> tuple[List[CommandExecution], List[StaticIssue]]:
        """Execute JavaScript syntax checks via Node parser."""
        executions: List[CommandExecution] = []
        issues: List[StaticIssue] = []

        node_executable = self._resolve_node_cli("node")
        if not node_executable:
            executions.append(
                CommandExecution(
                    language="javascript",
                    tool="node-check",
                    command="node --check <file>",
                    return_code=0,
                    status="skipped",
                    duration_ms=0,
                    stdout="",
                    stderr="node not found in PATH; JavaScript syntax checks skipped.",
                )
            )
            return executions, issues

        js_files = self._discover_files_by_suffixes(
            self.JS_EXTENSIONS,
            limit=self.MAX_JS_FILES_FOR_NODE_CHECK,
            target_files=target_files,
        )
        for js_file in js_files:
            args = [node_executable, "--check", str(js_file)]
            exec_rec = self._run_command(language="javascript", tool="node-check", args=args)
            executions.append(exec_rec)
            if exec_rec.return_code != 0:
                issues.extend(self._parse_generic_errors(exec_rec, language="javascript", default_file=str(js_file)))

        return executions, issues

    def _run_json_checks(
        self,
        *,
        target_files: Optional[List[Path]] = None,
    ) -> tuple[List[CommandExecution], List[StaticIssue]]:
        """Execute JSON validity checks using python json.tool."""
        executions: List[CommandExecution] = []
        issues: List[StaticIssue] = []

        json_files = self._discover_files_by_suffixes(
            {".json"},
            limit=self.MAX_JSON_FILES_FOR_JSON_CHECK,
            target_files=target_files,
        )
        python_exec = self._python_executable()
        for json_file in json_files:
            args = [python_exec, "-m", "json.tool", str(json_file)]
            exec_rec = self._run_command(language="json", tool="json.tool", args=args)
            executions.append(exec_rec)
            if exec_rec.return_code != 0:
                issues.extend(self._parse_generic_errors(exec_rec, language="json", default_file=str(json_file)))

        return executions, issues

    def _discover_tsconfig_paths(self, *, target_files: Optional[List[Path]] = None) -> List[Path]:
        """Find TypeScript config files, preferring primary project configs."""
        if target_files is not None:
            candidate_configs: set[Path] = set()
            ts_related = self._files_for_language(target_files, self.TS_EXTENSIONS.union(self.JS_EXTENSIONS))
            for file_path in ts_related:
                for parent in [file_path.parent, *file_path.parents]:
                    if not str(parent).startswith(str(self.repo_path)):
                        continue
                    for tsconfig_name in (
                        "tsconfig.json",
                        "tsconfig.app.json",
                        "tsconfig.spec.json",
                        "tsconfig.ci.json",
                        "tsconfig.e2e.json",
                    ):
                        candidate = parent / tsconfig_name
                        if candidate.exists() and candidate.is_file():
                            candidate_configs.add(candidate.resolve())
                    if parent == self.repo_path:
                        break
            configs = sorted(candidate_configs, key=lambda p: (0 if p.name == "tsconfig.json" else 1, len(p.parts), str(p)))
            return configs[:10]

        configs = [
            path
            for path in self._iter_repo_files()
            if path.name.startswith("tsconfig") and path.suffix.lower() == ".json"
        ]
        configs.sort(key=lambda p: (0 if p.name == "tsconfig.json" else 1, len(p.parts), str(p)))
        return configs[:10]

    def _discover_files_by_suffixes(
        self,
        suffixes: set[str],
        *,
        limit: int,
        target_files: Optional[List[Path]] = None,
    ) -> List[Path]:
        """Find files by extension with deterministic ordering and cap."""
        if target_files is not None:
            discovered = [path for path in target_files if path.suffix.lower() in suffixes]
        else:
            discovered = [path for path in self._iter_repo_files() if path.suffix.lower() in suffixes]
        discovered.sort(key=lambda p: str(p))
        return discovered[:limit]

    def _run_command(self, *, language: str, tool: str, args: List[str]) -> CommandExecution:
        """Run one command with timeout and robust exception handling."""
        started = time.monotonic()
        command_text = " ".join(args)
        LOGGER.info("Static check command [%s/%s]: %s", language, tool, command_text)
        try:
            completed = subprocess.run(
                args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            status = "ok" if completed.returncode == 0 else "failed"
            return CommandExecution(
                language=language,
                tool=tool,
                command=command_text,
                return_code=completed.returncode,
                status=status,
                duration_ms=duration_ms,
                stdout=self._truncate_output(completed.stdout),
                stderr=self._truncate_output(completed.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            LOGGER.warning("Static check timeout [%s/%s]: %s", language, tool, command_text)
            return CommandExecution(
                language=language,
                tool=tool,
                command=command_text,
                return_code=124,
                status="timeout",
                duration_ms=duration_ms,
                stdout=self._truncate_output(exc.stdout or ""),
                stderr=self._truncate_output((exc.stderr or "") + "\nCommand timed out."),
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            LOGGER.exception("Static check execution failed [%s/%s]", language, tool)
            return CommandExecution(
                language=language,
                tool=tool,
                command=command_text,
                return_code=1,
                status="error",
                duration_ms=duration_ms,
                stdout="",
                stderr=self._truncate_output(f"Runner failed to execute command: {exc}"),
            )

    def _resolve_node_cli(self, command: str) -> str | None:
        """
        Resolve Node-related executables robustly on Windows and Unix shells.

        Args:
            command: Base command name, e.g. `node` or `npx`.

        Returns:
            Resolved executable path/name, or `None` if unavailable.
        """
        candidates = [command]
        if os.name == "nt":
            candidates = [f"{command}.cmd", f"{command}.exe", f"{command}.bat", command]

        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def _parse_tsc_output(self, execution: CommandExecution) -> List[StaticIssue]:
        """Parse TypeScript compiler output into issues."""
        issues: List[StaticIssue] = []
        if execution.return_code == 0:
            return issues

        text = "\n".join([execution.stdout, execution.stderr]).strip()
        if not text:
            return issues

        pattern = re.compile(
            r"^(?P<file>.*\.(?:ts|tsx|js|jsx))\((?P<line>\d+),(?P<column>\d+)\):\s*error\s*(?P<code>TS\d+):\s*(?P<message>.+)$"
        )
        for line in text.splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            issues.append(
                StaticIssue(
                    severity="high",
                    language="typescript",
                    tool=execution.tool,
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("column")),
                    message=f"{match.group('code')}: {match.group('message')}",
                )
            )
            if len(issues) >= self.MAX_ISSUES_PER_COMMAND:
                break

        if not issues:
            issues.extend(self._parse_generic_errors(execution, language="typescript"))
        return issues

    def _parse_ruff_output(self, execution: CommandExecution) -> List[StaticIssue]:
        """Parse Ruff output into normalized issues."""
        issues: List[StaticIssue] = []
        if execution.return_code == 0:
            return issues

        text = "\n".join([execution.stdout, execution.stderr]).strip()
        pattern = re.compile(
            r"^(?P<file>.*?):(?P<line>\d+):(?P<column>\d+):\s*(?P<code>[A-Z]\d+)\s+(?P<message>.+)$"
        )

        for line in text.splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            issues.append(
                StaticIssue(
                    severity="medium",
                    language="python",
                    tool="ruff",
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("column")),
                    message=f"{match.group('code')}: {match.group('message')}",
                )
            )
            if len(issues) >= self.MAX_ISSUES_PER_COMMAND:
                break

        if not issues:
            issues.extend(self._parse_generic_errors(execution, language="python"))
        return issues

    def _parse_py_compile_output(
        self,
        execution: CommandExecution,
        *,
        default_file: str,
    ) -> List[StaticIssue]:
        """Parse `python -m py_compile` output to recover file/line syntax errors."""
        if execution.return_code == 0:
            return []

        text = "\n".join([execution.stdout, execution.stderr]).strip()
        if not text:
            return [
                StaticIssue(
                    severity="critical",
                    language="python",
                    tool="py_compile",
                    file=default_file,
                    message="Python syntax check failed without diagnostics.",
                )
            ]

        file_match = re.search(r'File "(?P<file>.+?)", line (?P<line>\d+)', text)
        syntax_line = None
        for line in text.splitlines():
            if "SyntaxError" in line:
                syntax_line = line.strip()
                break

        message = syntax_line or text.splitlines()[-1].strip()
        return [
            StaticIssue(
                severity="critical",
                language="python",
                tool="py_compile",
                file=file_match.group("file") if file_match else default_file,
                line=int(file_match.group("line")) if file_match else None,
                message=message,
            )
        ]

    def _parse_generic_errors(
        self,
        execution: CommandExecution,
        *,
        language: str,
        default_file: str = "",
    ) -> List[StaticIssue]:
        """Fallback parser for command stderr/stdout lines."""
        issues: List[StaticIssue] = []
        text = "\n".join([execution.stdout, execution.stderr]).strip()
        if execution.return_code == 0 and execution.status not in {"timeout", "error"}:
            return issues

        if not text:
            issues.append(
                StaticIssue(
                    severity="high",
                    language=language,
                    tool=execution.tool,
                    file=default_file,
                    message=f"{execution.tool} failed with return code {execution.return_code}.",
                )
            )
            return issues

        file_line_pattern = re.compile(
            r"(?P<file>[^:\s][^:]*)[:(](?P<line>\d+)(?:[: ,](?P<column>\d+))?[):]?\s*(?P<message>.*)"
        )

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            severity = self._infer_severity(line, execution.return_code)
            match = file_line_pattern.search(line)
            if match:
                file_value = match.group("file")
                line_num = self._safe_int(match.group("line"))
                col_num = self._safe_int(match.group("column"))
                msg = match.group("message").strip() or line
                issues.append(
                    StaticIssue(
                        severity=severity,
                        language=language,
                        tool=execution.tool,
                        file=file_value,
                        line=line_num,
                        column=col_num,
                        message=msg,
                    )
                )
            else:
                issues.append(
                    StaticIssue(
                        severity=severity,
                        language=language,
                        tool=execution.tool,
                        file=default_file,
                        message=line,
                    )
                )

            if len(issues) >= self.MAX_ISSUES_PER_COMMAND:
                break

        return issues

    def _build_summary(
        self,
        executions: List[CommandExecution],
        issues: List[StaticIssue],
        started_at: float,
    ) -> Dict[str, int]:
        """Build top-level static check summary counters."""
        total_duration_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "commands_total": len(executions),
            "commands_failed": sum(1 for item in executions if item.status in {"failed", "error", "timeout"}),
            "issues_total": len(issues),
            "issues_critical": sum(1 for item in issues if item.severity == "critical"),
            "issues_high": sum(1 for item in issues if item.severity == "high"),
            "issues_medium": sum(1 for item in issues if item.severity == "medium"),
            "issues_low": sum(1 for item in issues if item.severity == "low"),
            "duration_ms": total_duration_ms,
        }

    def _severity_sort_key(self, issue: StaticIssue) -> tuple[int, str, int]:
        """Stable severity ordering for UI consumption."""
        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return (
            priority.get(issue.severity, 99),
            issue.file or "",
            issue.line or 0,
        )

    def _infer_severity(self, line: str, return_code: int) -> str:
        """Infer severity from output line content and command outcome."""
        text = line.lower()
        if "syntaxerror" in text or "fatal" in text:
            return "critical"
        if "error" in text or return_code != 0:
            return "high"
        if "warning" in text:
            return "medium"
        return "low"

    def _truncate_output(self, text: str) -> str:
        """Bound command output for API transport/UI rendering."""
        if len(text) <= self.MAX_OUTPUT_CHARS:
            return text
        return text[: self.MAX_OUTPUT_CHARS] + "\n...[truncated]..."

    def _python_executable(self) -> str:
        """Resolve python executable for consistent subprocess commands."""
        return shutil.which("python") or "python"

    def _safe_int(self, value: str | None) -> int | None:
        """Safely parse optional integers."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None
