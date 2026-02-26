"""Step-wise PR workflow service for branch creation, commit/push, and Azure DevOps PR raise."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure_manager.azure_manager import AzureDevOpsClient

LOGGER = logging.getLogger(__name__)


class PRWorkflowError(RuntimeError):
    """Raised when the PR workflow fails validation or Git/Azure operation execution."""


@dataclass
class FileSnapshot:
    """Captured file payload from user workspace for replay in workspace repository."""

    relative_path: str
    status: str
    content: bytes | None


@dataclass
class WorkflowDefaults:
    """Backend-configurable defaults used by PR workflow actions."""

    main_base_branch: str
    prerelease_base_branch: str
    main_branch_template: str
    prerelease_branch_template: str
    commit_message_template: str
    pr_title_template: str
    pr_description_template: str
    month_source: str
    workspace_repo_path: str
    base_branches: dict[str, str]
    branch_templates: dict[str, str]


class PRWorkflowService:
    """Coordinates feature context lookup, local file snapshots, Git push, and PR creation."""

    def __init__(
        self,
        *,
        repo_path: str,
        organization: str,
        project: str,
        repository_name: str,
        azure_pat: str,
        defaults_path: str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).expanduser().resolve()
        if not self.repo_path.exists():
            raise PRWorkflowError(f"Repository path not found: {self.repo_path}")

        self.repository_name = repository_name
        self.defaults = self._load_defaults(defaults_path)
        self.workspace_repo_path = Path(self.defaults.workspace_repo_path).expanduser().resolve()
        self.azure_client = AzureDevOpsClient(
            organization=organization,
            project=project,
            pat_token=azure_pat,
        )

    def get_feature_context(self, feature_id: int) -> dict[str, Any]:
        """Return feature title and one-level parent/child hierarchy for the given work item ID."""
        family = self._get_work_item_family(int(feature_id))
        branches = self.build_branch_names_by_target(
            feature_id=feature_id,
            feature_title=family["feature"]["title"],
        )
        return {
            "feature": family["feature"],
            "parent": family["parent"],
            "children": family["children"],
            "all_related_item_ids": family["all_related_item_ids"],
            "branches": branches,
            "target_base_branches": self._get_target_base_branches(),
        }

    def list_changed_files(self) -> list[dict[str, Any]]:
        """
        List changed files from local repo with stable serial numbers and relative paths.

        Includes staged, unstaged, deleted, and untracked items.
        """
        source_repo = self._resolve_changes_source_repo()
        return self._list_changed_files_for_repo(source_repo)

    def list_reviewer_candidates(
        self,
        limit: int = 50,
        preferred_emails: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """List candidate reviewers from Azure DevOps identities for UI selection."""
        try:
            users = self.azure_client.list_identity_users(
                limit=max(1, int(limit)),
                preferred_emails=preferred_emails or [],
            )
        except Exception as exc:
            raise PRWorkflowError(f"Unable to load reviewer candidates: {exc}") from exc
        normalized: list[dict[str, str]] = []
        for user in users[: max(1, int(limit))]:
            reviewer_id = str(user.get("id", "") or "").strip()
            if not reviewer_id:
                continue
            normalized.append(
                {
                    "id": reviewer_id,
                    "display_name": str(user.get("display_name", "") or "").strip(),
                    "email": str(user.get("email", "") or "").strip(),
                }
            )
        return normalized

    def collect_work_item_family(self, work_item_id: int) -> dict[str, Any]:
        """Expose one-level hierarchy resolution for ad-hoc extra work item addition."""
        return self._get_work_item_family(work_item_id)

    def execute_raise_new_pr(
        self,
        *,
        feature_id: int,
        selected_serials: list[int],
        reviewer_ids: list[str] | None = None,
        reviewer_ids_by_branch: dict[str, list[str]] | None = None,
        target_branches: list[str] | None = None,
        additional_work_item_ids: list[int] | None = None,
        commit_message: str | None = None,
        before_stage_approval: Any | None = None,
    ) -> dict[str, Any]:
        """
        Create two branches, commit selected files, push, and raise PRs for both target branches.

        The selected files are captured from current workspace and replayed in a persistent workspace repo.
        """
        if not selected_serials:
            raise PRWorkflowError("Select at least one changed file before raising PR.")
        step_logs: list[str] = []

        feature_family = self._get_work_item_family(int(feature_id))
        feature_title = feature_family["feature"]["title"]
        branch_names = self.build_branch_names_by_target(feature_id=feature_id, feature_title=feature_title)
        target_base_branches = self._get_target_base_branches()
        selected_target_keys = self._normalize_target_branch_keys(target_branches)
        base_targets = [
            (key, target_base_branches[key], branch_names[key])
            for key in selected_target_keys
        ]
        step_logs.append(f"Selected PR target groups: {', '.join(selected_target_keys)}")

        source_repo = self._resolve_changes_source_repo()
        changed_files = self._list_changed_files_for_repo(source_repo)
        serial_lookup = {int(item["serial"]): item for item in changed_files}
        selected_rows: list[dict[str, Any]] = []
        for serial in selected_serials:
            entry = serial_lookup.get(int(serial))
            if not entry:
                raise PRWorkflowError(f"Invalid file serial selected: {serial}")
            selected_rows.append(entry)

        snapshots = self._capture_snapshots(selected_rows, source_repo)
        if not snapshots:
            raise PRWorkflowError("No valid file snapshots captured from selection.")
        step_logs.append(
            f"Captured {len(snapshots)} selected file snapshots from repository '{self.repository_name}'."
        )
        step_logs.append(f"Source repo for selected file content: {source_repo}")

        all_work_item_ids = list(feature_family["all_related_item_ids"])
        for item_id in additional_work_item_ids or []:
            family = self._get_work_item_family(int(item_id))
            for resolved_id in family["all_related_item_ids"]:
                if resolved_id not in all_work_item_ids:
                    all_work_item_ids.append(resolved_id)
        step_logs.append(f"Prepared {len(all_work_item_ids)} work item links for PR association.")

        fallback_reviewers = [value.strip() for value in (reviewer_ids or []) if value and value.strip()]
        normalized_reviewers_by_branch: dict[str, list[str]] = {
            key: [] for key in selected_target_keys
        }
        incoming_map = reviewer_ids_by_branch or {}
        for branch_key in selected_target_keys:
            branch_values = incoming_map.get(branch_key, fallback_reviewers)
            if branch_values is None:
                branch_values = fallback_reviewers
            normalized_reviewers_by_branch[branch_key] = [
                value.strip()
                for value in (branch_values or [])
                if value and value.strip()
            ]
        computed_commit_message = (
            (commit_message or "").strip()
            or self.defaults.commit_message_template.format(
                feature_id=feature_id,
                feature_title=feature_title,
            )
        )
        pr_title = self.defaults.pr_title_template.format(
            feature_id=feature_id,
            feature_title=feature_title,
        )
        pr_description = self.defaults.pr_description_template.format(
            feature_id=feature_id,
            feature_title=feature_title,
        )

        pushed: list[dict[str, Any]] = []
        prs: list[dict[str, Any]] = []
        try:
            with self._workspace_repo_session(
                step_logs,
                final_branch_before_pop="main",
                restore_initial_branch=False,
            ) as workspace_repo:
                required_branches = [item[1] for item in base_targets]
                self._fetch_required_branches(workspace_repo, required_branches, step_logs)

                for branch_key, target_branch, source_branch in base_targets:
                    self._sync_target_branch_with_origin(workspace_repo, target_branch, step_logs)
                    step_logs.append(
                        f"Creating branch '{source_branch}' from latest '{target_branch}'."
                    )
                    push_result = self._commit_snapshots_to_branch(
                        repo_path=workspace_repo,
                        target_branch=target_branch,
                        source_branch=source_branch,
                        snapshots=snapshots,
                        commit_message=computed_commit_message,
                        target_key=branch_key,
                        workspace_repo_path=workspace_repo,
                        step_logs=step_logs,
                        before_stage_approval=before_stage_approval,
                    )
                    pushed.append(push_result)
                    step_logs.append(
                        f"Branch pushed successfully: {source_branch} (base: {target_branch}, commit: {push_result.get('commit', '')})."
                    )

                    step_logs.append(
                        f"Raising PR for '{source_branch}' -> '{target_branch}' with "
                        f"{len(normalized_reviewers_by_branch.get(branch_key, []))} reviewers."
                    )
                    pr = self.azure_client.create_pull_request(
                        repository_name=self.repository_name,
                        source_branch=source_branch,
                        target_branch=target_branch,
                        title=pr_title,
                        description=pr_description,
                        reviewer_ids=normalized_reviewers_by_branch.get(branch_key, []),
                        work_item_ids=all_work_item_ids,
                    )
                    prs.append(
                        {
                            "pull_request_id": pr.get("pullRequestId"),
                            "url": pr.get("url") or pr.get("remoteUrl") or "",
                            "source_branch": source_branch,
                            "target_branch": target_branch,
                            "reviewer_ids": normalized_reviewers_by_branch.get(branch_key, []),
                            "status": pr.get("status", ""),
                        }
                    )
                    step_logs.append(
                        f"PR created successfully: #{pr.get('pullRequestId', '?')} {source_branch} -> {target_branch}."
                    )
        except Exception as exc:
            LOGGER.exception("Raise new PR workflow failed after steps: %s", step_logs)
            raise PRWorkflowError(
                f"PR workflow failed: {exc}. Completed steps: " + " | ".join(step_logs[-6:])
            ) from exc

        return {
            "repository": self.repository_name,
            "feature": feature_family["feature"],
            "parent": feature_family["parent"],
            "children": feature_family["children"],
            "selected_files": selected_rows,
            "work_item_ids": all_work_item_ids,
            "reviewer_ids_by_branch": normalized_reviewers_by_branch,
            "commit_message": computed_commit_message,
            "branches": pushed,
            "pull_requests": prs,
            "step_logs": step_logs,
            "target_branches": selected_target_keys,
        }

    def execute_cherry_pick(
        self,
        *,
        source_branch: str,
        target_branch: str,
        commit_hashes: list[str],
    ) -> dict[str, Any]:
        """Cherry-pick provided commits into target branch and push."""
        normalized_hashes = [value.strip() for value in commit_hashes if value and value.strip()]
        if not normalized_hashes:
            raise PRWorkflowError("Provide at least one commit hash to cherry-pick.")

        step_logs: list[str] = []
        with self._workspace_repo_session(step_logs) as workspace_repo:
            self._fetch_required_branches(workspace_repo, [source_branch, target_branch], step_logs)
            self._checkout_branch_from_remote(workspace_repo, target_branch, target_branch)
            self._run_git(["cherry-pick", *normalized_hashes], cwd=workspace_repo)
            head_commit = self._run_git(["rev-parse", "HEAD"], cwd=workspace_repo).stdout.strip()
            self._run_git(["push", "-u", "origin", target_branch], cwd=workspace_repo)
            self._assert_remote_branch_exists(workspace_repo, target_branch)

        return {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "commit_hashes": normalized_hashes,
            "head_commit": head_commit,
            "step_logs": step_logs,
        }

    def execute_commit_and_push(
        self,
        *,
        branch_name: str,
        base_branch: str,
        selected_serials: list[int],
        commit_message: str,
    ) -> dict[str, Any]:
        """Commit selected local changed files to the provided branch and push."""
        if not selected_serials:
            raise PRWorkflowError("Select at least one changed file before commit/push.")
        if not branch_name.strip():
            raise PRWorkflowError("Branch name is required.")
        if not base_branch.strip():
            raise PRWorkflowError("Base branch is required.")

        source_repo = self._resolve_changes_source_repo()
        changed_files = self._list_changed_files_for_repo(source_repo)
        serial_lookup = {int(item["serial"]): item for item in changed_files}
        selected_rows: list[dict[str, Any]] = []
        for serial in selected_serials:
            entry = serial_lookup.get(int(serial))
            if not entry:
                raise PRWorkflowError(f"Invalid file serial selected: {serial}")
            selected_rows.append(entry)
        snapshots = self._capture_snapshots(selected_rows, source_repo)
        step_logs: list[str] = []
        with self._workspace_repo_session(step_logs) as workspace_repo:
            self._fetch_required_branches(workspace_repo, [base_branch], step_logs)
            push_result = self._commit_snapshots_to_branch(
                repo_path=workspace_repo,
                target_branch=base_branch,
                source_branch=branch_name,
                snapshots=snapshots,
                commit_message=commit_message.strip(),
                target_key="commit_and_push",
                workspace_repo_path=workspace_repo,
                step_logs=step_logs,
                before_stage_approval=None,
            )
        return {
            "selected_files": selected_rows,
            "push_result": push_result,
            "step_logs": step_logs,
        }

    def build_branch_names(self, *, feature_id: int, feature_title: str) -> dict[str, str]:
        """Backward-compatible branch-name payload for UI callers."""
        by_target = self.build_branch_names_by_target(feature_id=feature_id, feature_title=feature_title)
        legacy: dict[str, str] = {}
        if "main" in by_target:
            legacy["main_branch"] = by_target["main"]
        if "prerelease" in by_target:
            legacy["prerelease_branch"] = by_target["prerelease"]
        legacy["by_target"] = by_target
        return legacy

    def build_branch_names_by_target(self, *, feature_id: int, feature_title: str) -> dict[str, str]:
        """Build deterministic source branch names for each configured target key."""
        slug = self._slugify(feature_title)
        month_abbr = self._resolve_month_abbreviation()
        context = {
            "feature_id": feature_id,
            "feature_slug": slug,
            "feature_title": feature_title,
            "month_abbr": month_abbr,
        }
        result: dict[str, str] = {}
        for key in self._get_target_base_branches().keys():
            template = self._get_branch_template_for_key(key)
            result[key] = template.format(**context)
        return result

    def _commit_snapshots_to_branch(
        self,
        *,
        repo_path: Path,
        target_branch: str,
        source_branch: str,
        snapshots: list[FileSnapshot],
        commit_message: str,
        target_key: str,
        workspace_repo_path: Path,
        step_logs: list[str],
        before_stage_approval: Any | None = None,
    ) -> dict[str, Any]:
        """Create source branch from target branch, replay snapshots, commit, and push."""
        self._checkout_branch_from_remote(repo_path, source_branch, target_branch)
        self._apply_snapshots(repo_path, snapshots)
        if before_stage_approval:
            step_logs.append(
                f"Applied selected changes to '{source_branch}'. Waiting for manual review before staging."
            )
            before_stage_approval(
                {
                    "target_key": target_key,
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "workspace_repo_path": str(workspace_repo_path),
                    "selected_files": [snapshot.relative_path for snapshot in snapshots],
                    "message": (
                        f"Review the branch '{source_branch}' in workspace "
                        f"'{workspace_repo_path}' and click Proceed to continue."
                    ),
                }
            )
            step_logs.append(
                f"Manual review approved for '{source_branch}'. Continuing with stage/commit/push."
            )
        self._run_git(
            ["add", "--all", "--", *[snapshot.relative_path for snapshot in snapshots]],
            cwd=repo_path,
        )
        staged = self._run_git(["diff", "--cached", "--name-only"], cwd=repo_path).stdout.strip()
        if not staged:
            raise PRWorkflowError(
                f"No staged changes to commit for branch '{source_branch}'. "
                "Make sure selected files include modified content."
            )

        self._run_git(["commit", "-m", commit_message], cwd=repo_path)
        commit_hash = self._run_git(["rev-parse", "HEAD"], cwd=repo_path).stdout.strip()
        self._run_git(["push", "-u", "origin", source_branch], cwd=repo_path)
        self._assert_remote_branch_exists(repo_path, source_branch)
        return {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "commit": commit_hash,
            "files_committed": [snapshot.relative_path for snapshot in snapshots],
        }

    def _cherry_pick_commit_to_branch(
        self,
        *,
        repo_path: Path,
        target_branch: str,
        source_branch: str,
        commit_hash: str,
    ) -> dict[str, Any]:
        """Create source branch from target branch by cherry-picking an existing commit."""
        if not commit_hash.strip():
            raise PRWorkflowError("Cherry-pick source commit hash is empty.")
        self._checkout_branch_from_remote(repo_path, source_branch, target_branch)
        self._run_git(["cherry-pick", commit_hash], cwd=repo_path)
        pushed_commit = self._run_git(["rev-parse", "HEAD"], cwd=repo_path).stdout.strip()
        self._run_git(["push", "-u", "origin", source_branch], cwd=repo_path)
        self._assert_remote_branch_exists(repo_path, source_branch)
        return {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "commit": pushed_commit,
        }

    def _resolve_clone_source_url(self) -> str:
        """Resolve clone source URL, preferring repository origin remote URL."""
        origin_url = self._read_git_remote_url(self.repo_path, "origin")
        if origin_url:
            return origin_url
        LOGGER.warning("Git origin URL not found, falling back to local repo path clone.")
        return str(self.repo_path)

    def _read_git_remote_url(self, repo_path: Path, remote_name: str) -> str:
        """Read Git remote URL with safe fallback."""
        result = self._run_git(["remote", "get-url", remote_name], cwd=repo_path, check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _assert_remote_branch_exists(self, repo_path: Path, branch_name: str) -> None:
        """Ensure pushed branch exists in remote heads before calling PR API."""
        result = self._run_git(
            ["ls-remote", "--heads", "origin", branch_name],
            cwd=repo_path,
            check=False,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            raise PRWorkflowError(
                "Source branch push did not appear on Azure remote. "
                f"branch={branch_name}. Verify origin remote points to Azure repository."
            )

    def _ensure_workspace_repo(self, step_logs: list[str]) -> tuple[Path, bool]:
        """Ensure persistent workspace repository exists and is configured."""
        workspace_repo = self.workspace_repo_path
        clone_source = self._resolve_clone_source_url()
        created_now = False
        if not workspace_repo.exists():
            workspace_repo.parent.mkdir(parents=True, exist_ok=True)
            self._run_git(["clone", clone_source, str(workspace_repo)], cwd=workspace_repo.parent)
            step_logs.append(f"Initialized workspace repo at '{workspace_repo}' from '{clone_source}'.")
            created_now = True
        self._assert_is_git_repo(workspace_repo)

        workspace_origin = self._read_git_remote_url(workspace_repo, "origin")
        if not workspace_origin:
            self._run_git(["remote", "add", "origin", clone_source], cwd=workspace_repo)
            step_logs.append("Added missing origin remote to workspace repo.")
        elif workspace_origin != clone_source and clone_source != str(self.repo_path):
            self._run_git(["remote", "set-url", "origin", clone_source], cwd=workspace_repo)
            step_logs.append("Updated workspace origin remote URL to match source repository origin.")

        user_name = self._read_git_config(self.repo_path, "user.name")
        user_email = self._read_git_config(self.repo_path, "user.email")
        self._run_git(
            ["config", "user.name", user_name or "Agentic PR Workflow"],
            cwd=workspace_repo,
        )
        self._run_git(
            ["config", "user.email", user_email or "agentic-pr-workflow@example.com"],
            cwd=workspace_repo,
        )
        return workspace_repo, created_now

    @contextmanager
    def _workspace_repo_session(
        self,
        step_logs: list[str],
        *,
        final_branch_before_pop: str | None = None,
        restore_initial_branch: bool = True,
    ):
        """Open workspace session and stash/pop local workspace changes safely."""
        workspace_repo, created_now = self._ensure_workspace_repo(step_logs)
        initial_branch = self._current_branch_name(workspace_repo)
        stash_created, stash_ref = self._stash_workspace_changes(workspace_repo, step_logs)
        try:
            yield workspace_repo
        finally:
            if final_branch_before_pop:
                switched = self._switch_workspace_branch(
                    workspace_repo,
                    final_branch_before_pop,
                    step_logs,
                    fetch_if_missing=True,
                )
                if switched:
                    step_logs.append(
                        f"Switched workspace branch to '{final_branch_before_pop}' before applying stash."
                    )
            elif restore_initial_branch:
                self._restore_workspace_branch(workspace_repo, initial_branch, step_logs)
            if stash_created and stash_ref:
                self._restore_workspace_stash(workspace_repo, stash_ref, step_logs)
            if final_branch_before_pop and restore_initial_branch:
                self._restore_workspace_branch(workspace_repo, initial_branch, step_logs)
            if created_now:
                self._cleanup_workspace_repo(workspace_repo, step_logs)

    def _stash_workspace_changes(self, workspace_repo: Path, step_logs: list[str]) -> tuple[bool, str]:
        """Stash local workspace changes before workflow actions."""
        stash_name = f"agentic-pr-workflow-{int(time.time())}"
        result = self._run_git(
            ["stash", "push", "-u", "-m", stash_name],
            cwd=workspace_repo,
            check=False,
        )
        combined = f"{result.stdout or ''}\n{result.stderr or ''}".strip()
        if result.returncode != 0:
            raise PRWorkflowError(f"Unable to stash workspace changes: {combined}")
        if "No local changes to save" in combined:
            step_logs.append("Workspace clean: no local changes to stash.")
            return False, ""

        stash_ref = self._find_stash_ref(workspace_repo, stash_name)
        if not stash_ref:
            stash_ref = "stash@{0}"
        step_logs.append(f"Stashed workspace changes before PR flow ({stash_ref}).")
        return True, stash_ref

    def _restore_workspace_stash(self, workspace_repo: Path, stash_ref: str, step_logs: list[str]) -> None:
        """Restore previously stashed workspace changes after workflow completion."""
        if not stash_ref:
            return
        pop_result = self._run_git(["stash", "pop", stash_ref], cwd=workspace_repo, check=False)
        if pop_result.returncode != 0:
            message = (pop_result.stderr or pop_result.stdout or "").strip()
            step_logs.append(f"Warning: failed to pop workspace stash '{stash_ref}': {message}")
            LOGGER.warning("Failed to pop workspace stash %s: %s", stash_ref, message)
            return
        step_logs.append(f"Restored workspace stash '{stash_ref}' after PR flow.")

    def _find_stash_ref(self, workspace_repo: Path, stash_name: str) -> str:
        """Find stash reference by stash message."""
        result = self._run_git(["stash", "list"], cwd=workspace_repo, check=False)
        if result.returncode != 0:
            return ""
        for line in (result.stdout or "").splitlines():
            if stash_name not in line:
                continue
            if ":" not in line:
                continue
            return line.split(":", 1)[0].strip()
        return ""

    def _current_branch_name(self, repo_path: Path) -> str:
        """Get currently checked-out branch name."""
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, check=False)
        if result.returncode != 0:
            return ""
        return (result.stdout or "").strip()

    def _restore_workspace_branch(self, repo_path: Path, branch_name: str, step_logs: list[str]) -> None:
        """Return workspace repo to original branch if possible."""
        normalized = str(branch_name or "").strip()
        if not normalized or normalized == "HEAD":
            return
        switched = self._switch_workspace_branch(
            repo_path,
            normalized,
            step_logs,
            fetch_if_missing=True,
        )
        if switched:
            step_logs.append(f"Restored workspace branch to '{normalized}'.")

    def _switch_workspace_branch(
        self,
        repo_path: Path,
        branch_name: str,
        step_logs: list[str],
        *,
        fetch_if_missing: bool,
    ) -> bool:
        """Switch workspace to branch from local or origin, optionally fetching first."""
        normalized = str(branch_name or "").strip()
        if not normalized:
            return False

        result = self._run_git(["checkout", normalized], cwd=repo_path, check=False)
        if result.returncode == 0:
            return True

        has_remote = self._run_git(
            ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{normalized}"],
            cwd=repo_path,
            check=False,
        ).returncode == 0
        if not has_remote and fetch_if_missing:
            self._run_git(
                [
                    "fetch",
                    "--prune",
                    "--no-tags",
                    "origin",
                    f"+refs/heads/{normalized}:refs/remotes/origin/{normalized}",
                ],
                cwd=repo_path,
                check=False,
            )
            has_remote = self._run_git(
                ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{normalized}"],
                cwd=repo_path,
                check=False,
            ).returncode == 0

        if has_remote:
            checkout_remote = self._run_git(
                ["checkout", "-B", normalized, f"origin/{normalized}"],
                cwd=repo_path,
                check=False,
            )
            if checkout_remote.returncode == 0:
                return True

        message = (result.stderr or result.stdout or "").strip()
        step_logs.append(f"Warning: unable to switch workspace branch '{normalized}': {message}")
        LOGGER.warning("Unable to switch workspace branch %s: %s", normalized, message)
        return False

    def _cleanup_workspace_repo(self, repo_path: Path, step_logs: list[str]) -> None:
        """Delete workspace repo only when it was auto-created by this run."""
        try:
            if repo_path.exists():
                shutil.rmtree(repo_path)
                step_logs.append(f"Deleted auto-created workspace repo '{repo_path}' after completion.")
        except Exception as exc:
            step_logs.append(f"Warning: unable to delete auto-created workspace repo '{repo_path}': {exc}")
            LOGGER.warning("Unable to delete auto-created workspace repo %s: %s", repo_path, exc)

    def _fetch_required_branches(
        self,
        workspace_repo: Path,
        branch_names: list[str],
        step_logs: list[str],
    ) -> None:
        """Fetch only required branches into workspace remote refs."""
        unique_branches: list[str] = []
        seen: set[str] = set()
        for branch in branch_names:
            normalized = str(branch or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_branches.append(normalized)

        for branch in unique_branches:
            fetch_args = [
                "fetch",
                "--prune",
                "--no-tags",
                "origin",
                f"+refs/heads/{branch}:refs/remotes/origin/{branch}",
            ]
            try:
                self._run_git(fetch_args, cwd=workspace_repo)
                step_logs.append(f"Fetched branch from origin: {branch}")
            except PRWorkflowError as exc:
                message = str(exc)
                if "non-fast-forward" not in message.lower():
                    raise

                # Recover from stale/broken tracking ref and retry targeted fetch once.
                self._run_git(
                    ["update-ref", "-d", f"refs/remotes/origin/{branch}"],
                    cwd=workspace_repo,
                    check=False,
                )
                retry_args = [
                    "fetch",
                    "--prune",
                    "--no-tags",
                    "origin",
                    f"refs/heads/{branch}:refs/remotes/origin/{branch}",
                ]
                self._run_git(retry_args, cwd=workspace_repo)
                step_logs.append(
                    f"Fetched branch from origin after remote-ref reset: {branch}"
                )

    def _sync_target_branch_with_origin(
        self,
        workspace_repo: Path,
        target_branch: str,
        step_logs: list[str],
    ) -> None:
        """Checkout target branch and hard-sync to latest origin state."""
        branch = str(target_branch or "").strip()
        if not branch:
            raise PRWorkflowError("Target branch name is empty.")

        self._fetch_required_branches(workspace_repo, [branch], step_logs)
        switched = self._switch_workspace_branch(
            workspace_repo,
            branch,
            step_logs,
            fetch_if_missing=False,
        )
        if not switched:
            raise PRWorkflowError(
                f"Unable to switch to target branch '{branch}' before PR branch creation."
            )
        self._run_git(["reset", "--hard", f"origin/{branch}"], cwd=workspace_repo)
        self._run_git(["clean", "-fd"], cwd=workspace_repo)
        step_logs.append(f"Synchronized target branch '{branch}' to latest origin state.")

    def _get_target_base_branches(self) -> dict[str, str]:
        """Return configured target base branches keyed by logical target name."""
        from_config = self.defaults.base_branches or {}
        normalized: dict[str, str] = {}
        for key, value in from_config.items():
            normalized_key = str(key or "").strip().lower()
            normalized_value = str(value or "").strip()
            if not normalized_key or not normalized_value:
                continue
            normalized[normalized_key] = normalized_value
        if normalized:
            return normalized
        return {
            "main": self.defaults.main_base_branch,
            "prerelease": self.defaults.prerelease_base_branch,
        }

    def _get_branch_template_for_key(self, key: str) -> str:
        """Resolve branch source-name template for a target key."""
        templates = self.defaults.branch_templates or {}
        normalized_templates: dict[str, str] = {}
        for item_key, item_value in templates.items():
            template_key = str(item_key or "").strip().lower()
            template_value = str(item_value or "").strip()
            if not template_key or not template_value:
                continue
            normalized_templates[template_key] = template_value

        normalized_key = str(key or "").strip().lower()
        if normalized_key in normalized_templates:
            return normalized_templates[normalized_key]
        if "main" in normalized_templates:
            return normalized_templates["main"]
        if normalized_templates:
            first_key = next(iter(normalized_templates.keys()))
            return normalized_templates[first_key]
        return self.defaults.main_branch_template

    def _normalize_target_branch_keys(self, target_branches: list[str] | None) -> list[str]:
        """Normalize selected target branch keys and apply defaults."""
        allowed = set(self._get_target_base_branches().keys())
        if not target_branches:
            return list(self._get_target_base_branches().keys())
        normalized: list[str] = []
        seen: set[str] = set()
        for value in target_branches:
            key = str(value or "").strip().lower()
            if key not in allowed or key in seen:
                continue
            seen.add(key)
            normalized.append(key)
        if not normalized:
            allowed_text = ", ".join(sorted(allowed))
            raise PRWorkflowError(f"Select at least one target branch from: {allowed_text}")
        return normalized

    def _checkout_branch_from_remote(
        self,
        clone_path: Path,
        source_branch: str,
        target_branch: str,
    ) -> None:
        """Create/reset source branch from remote target branch."""
        normalized_target_ref = f"origin/{target_branch}"
        has_remote_target = self._run_git(
            ["show-ref", "--verify", "--quiet", f"refs/remotes/{normalized_target_ref}"],
            cwd=clone_path,
            check=False,
        ).returncode == 0
        if has_remote_target:
            self._run_git(["checkout", "-B", source_branch, normalized_target_ref], cwd=clone_path)
            return

        has_local_target = self._run_git(
            ["show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
            cwd=clone_path,
            check=False,
        ).returncode == 0
        if has_local_target:
            self._run_git(["checkout", "-B", source_branch, target_branch], cwd=clone_path)
            return

        raise PRWorkflowError(
            f"Target branch '{target_branch}' not found in remote/local refs while creating '{source_branch}'."
        )

    def _capture_snapshots(
        self,
        selected_rows: list[dict[str, Any]],
        source_repo: Path | None = None,
    ) -> list[FileSnapshot]:
        """Capture selected file byte content from current workspace for later replay."""
        snapshots: list[FileSnapshot] = []
        resolved_source_repo = source_repo or self._resolve_changes_source_repo()
        for row in selected_rows:
            relative_path = str(row.get("path", "")).strip().replace("\\", "/")
            if not relative_path:
                continue
            absolute_path = resolved_source_repo / relative_path
            status = str(row.get("status", "")).strip().lower()
            if absolute_path.exists() and absolute_path.is_file():
                snapshots.append(
                    FileSnapshot(
                        relative_path=relative_path,
                        status=status,
                        content=absolute_path.read_bytes(),
                    )
                )
            else:
                snapshots.append(
                    FileSnapshot(
                        relative_path=relative_path,
                        status="deleted",
                        content=None,
                    )
                )
        return snapshots

    def _list_changed_files_for_repo(self, source_repo: Path) -> list[dict[str, Any]]:
        """List changed files for a specific repository path."""
        self._assert_is_git_repo(source_repo)
        status_output = self._run_git(
            ["-c", "core.quotepath=false", "status", "--porcelain=1", "--untracked-files=all"],
            cwd=source_repo,
        ).stdout

        rows: list[dict[str, Any]] = []
        for raw_line in status_output.splitlines():
            if not raw_line.strip():
                continue
            parsed = self._parse_status_line(raw_line)
            if not parsed:
                continue
            rows.append(parsed)

        rows.sort(key=lambda item: item["path"].lower())
        for index, item in enumerate(rows, start=1):
            item["serial"] = index
        return rows

    def _resolve_changes_source_repo(self) -> Path:
        """Resolve repository path to read selected changed files/snapshots from."""
        if self._is_git_repo(self.repo_path):
            return self.repo_path
        if self._is_git_repo(self.workspace_repo_path):
            return self.workspace_repo_path

        bootstrap_logs: list[str] = []
        try:
            workspace_repo, _ = self._ensure_workspace_repo(bootstrap_logs)
            if self._is_git_repo(workspace_repo):
                return workspace_repo
        except Exception:
            LOGGER.exception("Unable to bootstrap workspace repository for changes source")

        raise PRWorkflowError(
            "No valid git repository found for selected files. "
            f"repo_path={self.repo_path}, workspace_repo_path={self.workspace_repo_path}."
        )

    def _apply_snapshots(self, clone_path: Path, snapshots: list[FileSnapshot]) -> None:
        """Replay selected snapshots onto temp clone working tree."""
        for snapshot in snapshots:
            file_path = (clone_path / snapshot.relative_path).resolve()
            if not str(file_path).startswith(str(clone_path.resolve())):
                raise PRWorkflowError(f"Unsafe file path outside repository: {snapshot.relative_path}")

            if snapshot.content is None or snapshot.status == "deleted":
                if file_path.exists():
                    file_path.unlink()
                continue

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(snapshot.content)

    def _get_work_item_family(self, work_item_id: int) -> dict[str, Any]:
        """Resolve one-level work item family (self, parent, direct children)."""
        root = self.azure_client.get_work_item(work_item_id)
        parent_ids, child_ids = self._extract_parent_child_ids(root.get("relations", []))

        parent = self._safe_get_work_item_summary(parent_ids[0]) if parent_ids else None
        children = [self._safe_get_work_item_summary(item_id) for item_id in child_ids]
        valid_children = [item for item in children if item is not None]

        all_ids = [work_item_id]
        if parent and parent["id"] not in all_ids:
            all_ids.append(parent["id"])
        for child in valid_children:
            if child["id"] not in all_ids:
                all_ids.append(child["id"])

        return {
            "feature": self._to_work_item_summary(root),
            "parent": parent,
            "children": valid_children,
            "all_related_item_ids": all_ids,
        }

    def _extract_parent_child_ids(self, relations: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
        """Extract parent and child work item IDs from Azure relation links."""
        parent_ids: list[int] = []
        child_ids: list[int] = []
        for relation in relations or []:
            relation_type = str(relation.get("rel", "") or "").strip().lower()
            url = str(relation.get("url", "") or "")
            item_id = self._extract_work_item_id_from_url(url)
            if not item_id:
                continue
            if relation_type == "system.linktypes.hierarchy-reverse":
                parent_ids.append(item_id)
            elif relation_type == "system.linktypes.hierarchy-forward":
                child_ids.append(item_id)
        return parent_ids, child_ids

    def _safe_get_work_item_summary(self, work_item_id: int) -> dict[str, Any] | None:
        """Fetch summary for one work item ID and suppress individual lookup failures."""
        try:
            item = self.azure_client.get_work_item(work_item_id)
            return self._to_work_item_summary(item)
        except Exception:
            LOGGER.exception("Unable to resolve related work item id=%s", work_item_id)
            return None

    def _to_work_item_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Normalize Azure work item payload to compact summary object."""
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        return {
            "id": int(payload.get("id", 0)),
            "title": str(fields.get("System.Title", "") or "").strip(),
            "type": str(fields.get("System.WorkItemType", "") or "").strip(),
            "state": str(fields.get("System.State", "") or "").strip(),
        }

    def _extract_work_item_id_from_url(self, url: str) -> int | None:
        """Extract numeric work item ID from relation URL."""
        match = re.search(r"/workItems/(\d+)", url or "", flags=re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1))

    def _resolve_month_abbreviation(self) -> str:
        """Resolve month abbreviation for branch naming template variables."""
        source = (self.defaults.month_source or "").strip().lower()
        if source == "prerelease_base_branch":
            month = self._extract_month_from_branch_name(self.defaults.prerelease_base_branch)
            if month:
                return month
        if source == "current_utc":
            return datetime.now(timezone.utc).strftime("%b")
        return datetime.now().strftime("%b")

    def _extract_month_from_branch_name(self, branch_name: str) -> str:
        """Extract month abbreviation from configured prerelease base branch path."""
        month_aliases = {
            "jan": "Jan",
            "january": "Jan",
            "feb": "Feb",
            "february": "Feb",
            "mar": "Mar",
            "march": "Mar",
            "apr": "Apr",
            "april": "Apr",
            "may": "May",
            "jun": "Jun",
            "june": "Jun",
            "jul": "Jul",
            "july": "Jul",
            "aug": "Aug",
            "august": "Aug",
            "sep": "Sep",
            "sept": "Sep",
            "september": "Sep",
            "oct": "Oct",
            "october": "Oct",
            "nov": "Nov",
            "november": "Nov",
            "dec": "Dec",
            "december": "Dec",
        }
        tokens = [part.strip() for part in str(branch_name or "").split("/") if part and part.strip()]
        for token in reversed(tokens):
            normalized = token.strip().lower()
            if normalized in month_aliases:
                return month_aliases[normalized]
        return ""

    def _slugify(self, value: str) -> str:
        """Build safe and human-readable branch slug from work item title."""
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_")
        if not normalized:
            return "feature"
        return normalized[:80]

    def _read_git_config(self, repo_path: Path, key: str) -> str:
        """Read local Git config value without raising for missing keys."""
        result = self._run_git(["config", "--get", key], cwd=repo_path, check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _assert_is_git_repo(self, repo_path: Path) -> None:
        """Validate repo path points to an initialized Git repository."""
        if not self._is_git_repo(repo_path):
            raise PRWorkflowError(f"Not a valid git repository: {repo_path}")

    def _is_git_repo(self, repo_path: Path) -> bool:
        """Return True if path points to an initialized Git working tree."""
        if not repo_path.exists():
            return False
        result = self._run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_path, check=False)
        return result.returncode == 0 and result.stdout.strip().lower() == "true"

    def _parse_status_line(self, line: str) -> dict[str, Any] | None:
        """Parse one porcelain status line into status label + relative path."""
        if len(line) < 3:
            return None

        xy = line[:2]
        raw_path = line[3:].strip()
        if not raw_path:
            return None

        if " -> " in raw_path:
            _, destination_path = raw_path.split(" -> ", 1)
            raw_path = destination_path.strip()

        normalized_path = raw_path.replace("\\", "/").lstrip("/")
        if not normalized_path:
            return None

        if xy == "??":
            status = "untracked"
        elif "D" in xy:
            status = "deleted"
        elif "A" in xy:
            status = "added"
        elif "R" in xy:
            status = "renamed"
        else:
            status = "modified"

        return {"status": status, "path": normalized_path}

    def _run_git(
        self,
        args: list[str],
        *,
        cwd: Path,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run Git command and return process result, raising workflow error for failures."""
        command = ["git", *args]
        result = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            details = stderr or stdout or "unknown git error"
            raise PRWorkflowError(f"Git command failed: {' '.join(command)} :: {details}")
        return result

    def _load_defaults(self, defaults_path: str | None) -> WorkflowDefaults:
        """Load workflow defaults from JSON file with safe fallbacks."""
        fallback = WorkflowDefaults(
            main_base_branch="main",
            prerelease_base_branch="PreRelease/3.13/2026/Mar/18",
            main_branch_template="Feature/#{feature_id}/{feature_slug}",
            prerelease_branch_template="Feature/#{feature_id}/{feature_slug}_{month_abbr}",
            commit_message_template="[Feature #{feature_id}] {feature_title}",
            pr_title_template="[Feature #{feature_id}] {feature_title}",
            pr_description_template="Auto-created by Agentic AI PR workflow for Feature #{feature_id}.",
            month_source="prerelease_base_branch",
            workspace_repo_path="D:\\Product\\Infraon_debug",
            base_branches={
                "main": "main",
                "prerelease": "PreRelease/3.13/2026/Mar/18",
            },
            branch_templates={
                "main": "Feature/#{feature_id}/{feature_slug}",
                "prerelease": "Feature/#{feature_id}/{feature_slug}_{month_abbr}",
            },
        )

        candidate = (
            Path(defaults_path).expanduser().resolve()
            if defaults_path
            else Path(__file__).resolve().parent.parent / "config" / "pr_workflow_defaults.json"
        )
        if not candidate.exists():
            LOGGER.warning("PR workflow defaults file not found. Using built-in defaults. path=%s", candidate)
            return fallback

        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            base_branches = data.get("base_branches", {}) if isinstance(data, dict) else {}
            branch_templates = data.get("branch_templates", {}) if isinstance(data, dict) else {}
            return WorkflowDefaults(
                main_base_branch=str(base_branches.get("main", fallback.main_base_branch)),
                prerelease_base_branch=str(base_branches.get("prerelease", fallback.prerelease_base_branch)),
                main_branch_template=str(branch_templates.get("main", fallback.main_branch_template)),
                prerelease_branch_template=str(
                    branch_templates.get("prerelease", fallback.prerelease_branch_template)
                ),
                commit_message_template=str(
                    data.get("commit_message_template", fallback.commit_message_template)
                ),
                pr_title_template=str(data.get("pr_title_template", fallback.pr_title_template)),
                pr_description_template=str(
                    data.get("pr_description_template", fallback.pr_description_template)
                ),
                month_source=str(data.get("month_source", fallback.month_source)),
                workspace_repo_path=str(data.get("workspace_repo_path", fallback.workspace_repo_path)),
                base_branches={
                    str(key): str(value)
                    for key, value in (base_branches if isinstance(base_branches, dict) else {}).items()
                    if str(key).strip() and str(value).strip()
                }
                or dict(fallback.base_branches),
                branch_templates={
                    str(key): str(value)
                    for key, value in (branch_templates if isinstance(branch_templates, dict) else {}).items()
                    if str(key).strip() and str(value).strip()
                }
                or dict(fallback.branch_templates),
            )
        except Exception:
            LOGGER.exception("Failed to parse PR workflow defaults file. Using built-in defaults.")
            return fallback
