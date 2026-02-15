"""Azure DevOps REST client with retry, logging, and structured diff extraction."""

from __future__ import annotations

import base64
import difflib
import logging
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util.retry import Retry

LOGGER = logging.getLogger(__name__)


class AzureDevOpsError(RuntimeError):
    """Raised when an Azure DevOps API call fails."""


class AzureDevOpsClient:
    """Thin typed wrapper over Azure DevOps Git pull request APIs."""

    def __init__(
        self,
        organization: str,
        project: str,
        pat_token: str,
        timeout: int = 30,
    ) -> None:
        """
        Initialize API client.

        Args:
            organization: Azure DevOps organization.
            project: Azure DevOps project.
            pat_token: Personal access token.
            timeout: Default API timeout in seconds.
        """
        self.organization = organization
        self.project = project
        self.timeout = timeout
        self.base_url = f"https://dev.azure.com/{organization}/{project}"
        self._auth_header = self._build_auth_header(pat_token)
        self.session = self._create_session()
        self._repository_id_cache: Dict[str, str] = {}
        self._excluded_suffixes = {
            ".ds_store",
            "thumbs.db",
            ".env",
            ".db",
            ".sqlite3",
            ".log",
            ".pyc",
            ".json",
            ".ini",
            "environment.instance.ts",
            "requirements.txt",
            ".png",
            ".feature",
        }

    def _build_auth_header(self, pat_token: str) -> str:
        """Build HTTP Basic auth header for Azure DevOps PAT."""
        if not pat_token or not pat_token.strip():
            raise AzureDevOpsError(
                "Azure DevOps PAT is missing. Provide `azure_pat` in request or set AZURE_DEVOPS_PAT."
            )
        token = base64.b64encode(f":{pat_token}".encode("utf-8")).decode("utf-8")
        return f"Basic {token}"

    def _create_session(self) -> Session:
        """Create a `requests` session with retry behavior."""
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": self._auth_header,
                "Accept": "application/json",
                "User-Agent": "agentic-ai-code-review/2.0",
            }
        )

        retries = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
        )

        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        return session

    def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute GET request and decode JSON response."""
        return self._request_json("GET", url, params=params)

    def _post(
        self,
        url: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute POST request and decode JSON response."""
        return self._request_json("POST", url, params=params, json_payload=payload)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an API request and parse JSON body.

        Args:
            method: HTTP method.
            url: Relative Azure API path or full URL.
            params: Query params.
            json_payload: Optional JSON body for POST.

        Returns:
            JSON-decoded response dictionary.
        """
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        try:
            LOGGER.debug(
                "Azure request method=%s url=%s params=%s",
                method,
                full_url,
                params,
            )
            response = self.session.request(
                method=method,
                url=full_url,
                params=params,
                json=json_payload,
                timeout=self.timeout,
            )
            self._raise_for_status(response, method, full_url)
            if response.status_code == 204 or not response.text.strip():
                return {}

            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" not in content_type and "text/json" not in content_type:
                body = self._truncate_text(response.text)
                LOGGER.error(
                    "Azure API returned non-JSON response method=%s status=%s content_type=%s url=%s body=%s",
                    method,
                    response.status_code,
                    content_type,
                    full_url,
                    body,
                )
                raise AzureDevOpsError(
                    "Azure DevOps returned a non-JSON response. "
                    f"status={response.status_code}, content_type={content_type or 'unknown'}. "
                    "This usually indicates invalid organization/project URL, missing permission, or auth challenge."
                )

            try:
                return response.json()
            except (ValueError, RequestsJSONDecodeError) as exc:
                body = self._truncate_text(response.text)
                LOGGER.error(
                    "Azure API returned invalid JSON method=%s status=%s url=%s body=%s",
                    method,
                    response.status_code,
                    full_url,
                    body,
                )
                raise AzureDevOpsError(
                    "Azure DevOps returned malformed JSON response. "
                    f"status={response.status_code}, body_snippet={body}"
                ) from exc
        except RequestException as exc:
            LOGGER.exception("Azure request failed method=%s url=%s", method, full_url)
            raise AzureDevOpsError(f"Network failure calling Azure DevOps: {exc}") from exc
        except AzureDevOpsError:
            raise

    def _raise_for_status(self, response: Response, method: str, full_url: str) -> None:
        """Raise `AzureDevOpsError` on non-success status codes."""
        if response.ok:
            return
        try:
            error_details: Any = response.json()
        except ValueError:
            error_details = self._truncate_text(response.text)

        LOGGER.error(
            "Azure API failure method=%s status=%s url=%s body=%s",
            method,
            response.status_code,
            full_url,
            error_details,
        )
        if response.status_code == 401:
            raise AzureDevOpsError(
                "Azure DevOps authentication failed (401). Check PAT value and token scopes."
            )
        if response.status_code == 403:
            raise AzureDevOpsError(
                "Azure DevOps authorization failed (403). PAT may lack repo/PR read permissions."
            )
        if response.status_code == 404:
            raise AzureDevOpsError(
                "Azure DevOps endpoint not found (404). Verify organization, project, and repository names."
            )
        raise AzureDevOpsError(
            f"Azure DevOps API call failed ({response.status_code}): {error_details}"
        )

    def _truncate_text(self, value: str, limit: int = 600) -> str:
        """Truncate large response body snippets used in error diagnostics."""
        if len(value) <= limit:
            return value
        return value[:limit] + "...[truncated]"

    def get_repository_id(self, repository_name: str) -> str:
        """
        Resolve repository ID by repository name.

        Args:
            repository_name: Repository display name.

        Returns:
            Repository GUID.
        """
        if repository_name in self._repository_id_cache:
            return self._repository_id_cache[repository_name]

        data = self._get("/_apis/git/repositories", params={"api-version": "7.1"})
        for repository in data.get("value", []):
            if repository.get("name") == repository_name:
                repository_id = repository.get("id", "")
                self._repository_id_cache[repository_name] = repository_id
                return repository_id

        raise AzureDevOpsError(f"Repository not found: {repository_name}")

    def get_last_iteration_id(self, repository_name: str, pull_request_id: int) -> int:
        """
        Get the latest iteration ID for a pull request.

        Args:
            repository_name: Repository name.
            pull_request_id: PR ID.

        Returns:
            Latest iteration integer ID.
        """
        repository_id = self.get_repository_id(repository_name)
        data = self._get(
            f"/_apis/git/repositories/{repository_id}/pullRequests/{pull_request_id}/iterations",
            params={"api-version": "7.1-preview.1"},
        )
        iterations = data.get("value", [])
        if not iterations:
            raise AzureDevOpsError(f"No iterations found for PR {pull_request_id}")
        return int(iterations[-1]["id"])

    def get_pr_changes(self, repository_name: str, pull_request_id: int) -> List[Dict[str, Any]]:
        """
        Fetch file-level change entries for the latest PR iteration.

        Args:
            repository_name: Repository name.
            pull_request_id: PR ID.

        Returns:
            List of Azure change entries.
        """
        repository_id = self.get_repository_id(repository_name)
        iteration_id = self.get_last_iteration_id(repository_name, pull_request_id)
        data = self._get(
            f"/_apis/git/repositories/{repository_id}/pullRequests/{pull_request_id}/iterations/{iteration_id}/changes",
            params={"api-version": "7.1-preview.1", "$top": 5000, "includeContent": "true"},
        )
        changes = data.get("changeEntries", [])
        LOGGER.info("Fetched %s PR change entries for PR %s", len(changes), pull_request_id)
        return changes

    def get_file_by_oid(self, repository_name: str, oid: str) -> str:
        """
        Fetch a file blob by object ID.

        Args:
            repository_name: Repository name.
            oid: Blob object ID.

        Returns:
            Text content decoded as UTF-8 (best-effort).
        """
        repository_id = self.get_repository_id(repository_name)
        url = f"{self.base_url}/_apis/git/repositories/{repository_id}/blobs/{oid}"
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/octet-stream",
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params={"api-version": "7.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.content.decode("utf-8", errors="ignore")
        except RequestException as exc:
            LOGGER.exception("Failed to fetch blob by oid=%s", oid)
            raise AzureDevOpsError(f"Failed to fetch blob {oid}: {exc}") from exc

    def get_file_diff(
        self,
        repository_name: str,
        base_object_id: str,
        target_object_id: str,
        file_path: str,
    ) -> List[Dict[str, Any]]:
        """
        Compute per-hunk line-level diff between old and new blob contents.

        Args:
            repository_name: Repository name.
            base_object_id: Source blob object ID.
            target_object_id: Target blob object ID.
            file_path: Changed file path.

        Returns:
            Structured list of hunks.
        """
        try:
            if self._is_excluded_file(file_path):
                return []

            base_content = self.get_file_by_oid(repository_name, base_object_id)
            target_content = self.get_file_by_oid(repository_name, target_object_id)

            base_lines = base_content.splitlines()
            target_lines = target_content.splitlines()
            matcher = difflib.SequenceMatcher(None, base_lines, target_lines)

            hunks: List[Dict[str, Any]] = []
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue

                hunk = {
                    "file": file_path,
                    "hunk": {
                        "old_start": i1 + 1 if i1 < len(base_lines) else None,
                        "new_start": j1 + 1 if j1 < len(target_lines) else None,
                        "context": base_lines[max(0, i1 - 3) : min(len(base_lines), i2 + 3)],
                        "removed": [],
                        "added": [],
                    },
                }

                if tag in ("replace", "delete"):
                    for index, removed_line in enumerate(base_lines[i1:i2], start=i1 + 1):
                        hunk["hunk"]["removed"].append({"line": removed_line, "old_line": index})

                if tag in ("replace", "insert"):
                    for index, added_line in enumerate(target_lines[j1:j2], start=j1 + 1):
                        hunk["hunk"]["added"].append({"line": added_line, "new_line": index})

                if hunk["hunk"]["removed"] or hunk["hunk"]["added"]:
                    hunks.append(hunk)
            return hunks
        except Exception as exc:
            LOGGER.exception("Failed to compute file diff for %s", file_path)
            raise AzureDevOpsError(f"Failed to compute file diff for {file_path}") from exc

    def get_pr_content_changes(
        self,
        repository_name: str,
        pull_request_id: int,
        instruction: str,
    ) -> List[Dict[str, Any]]:
        """
        Build normalized list of content changes for all edited files.

        Args:
            repository_name: Repository name.
            pull_request_id: PR ID.
            instruction: Unused placeholder retained for compatibility.

        Returns:
            Flattened list of structured hunks.
        """
        del instruction
        changes = self.get_pr_changes(repository_name, pull_request_id)
        results: List[Dict[str, Any]] = []

        for change in changes:
            try:
                item = change.get("item", {})
                change_type = (change.get("changeType") or "").lower()
                if change_type != "edit":
                    continue

                file_path = item.get("path", "")
                original_object_id = item.get("originalObjectId")
                object_id = item.get("objectId")
                if not original_object_id or not object_id:
                    continue

                results.extend(
                    self.get_file_diff(
                        repository_name=repository_name,
                        base_object_id=original_object_id,
                        target_object_id=object_id,
                        file_path=file_path,
                    )
                )
            except Exception:
                LOGGER.exception("Skipping invalid change entry: %s", change)

        LOGGER.info("Computed %s diff hunks for PR %s", len(results), pull_request_id)
        return results

    def normalize_change_entries(self, change_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize Azure diff payloads from alternate APIs into local schema.

        Args:
            change_entries: Raw change entries.

        Returns:
            Normalized list compatible with downstream reviewers.
        """
        normalized: List[Dict[str, Any]] = []
        for entry in change_entries:
            file_path = entry.get("item", {}).get("path", "")
            for diff in entry.get("diffs", []):
                for hunk in diff.get("hunks", []):
                    context: List[str] = []
                    added: List[Dict[str, Any]] = []
                    removed: List[Dict[str, Any]] = []

                    for line in hunk.get("lines", []):
                        line_type = line.get("lineType")
                        if line_type == "context":
                            context.append(line.get("content", ""))
                        elif line_type == "add":
                            added.append(
                                {
                                    "line": line.get("content", ""),
                                    "new_line": line.get("newLineNumber"),
                                }
                            )
                        elif line_type == "remove":
                            removed.append(
                                {
                                    "line": line.get("content", ""),
                                    "old_line": line.get("oldLineNumber"),
                                }
                            )

                    normalized.append(
                        {
                            "file": file_path,
                            "hunk": {
                                "old_start": hunk.get("oldStartLine"),
                                "new_start": hunk.get("newStartLine"),
                                "context": context,
                                "removed": removed,
                                "added": added,
                            },
                        }
                    )
        return normalized

    def get_pr_comments(self, repository_name: str, pull_request_id: int) -> List[Dict[str, Any]]:
        """
        Fetch active non-system comment threads for a pull request.

        Args:
            repository_name: Repository name.
            pull_request_id: PR ID.

        Returns:
            List of active comment threads.
        """
        repository_id = self.get_repository_id(repository_name)
        data = self._get(
            f"/_apis/git/repositories/{repository_id}/pullRequests/{pull_request_id}/threads",
            params={"api-version": "7.1-preview.1"},
        )

        threads: List[Dict[str, Any]] = []
        for thread in data.get("value", []):
            if thread.get("isDeleted") or thread.get("status") != "active":
                continue

            comments: List[Dict[str, Any]] = []
            for comment in thread.get("comments", []):
                if comment.get("commentType") == "system":
                    continue
                comments.append(
                    {
                        "id": comment.get("id"),
                        "content": comment.get("content", ""),
                        "author": comment.get("author", {}).get("displayName"),
                        "publishedDate": comment.get("publishedDate"),
                        "commentType": comment.get("commentType"),
                    }
                )

            if comments:
                threads.append(
                    {
                        "threadId": thread.get("id"),
                        "status": thread.get("status"),
                        "isDeleted": thread.get("isDeleted"),
                        "comments": comments,
                    }
                )

        LOGGER.info("Fetched %s active comment threads for PR %s", len(threads), pull_request_id)
        return threads

    def _is_excluded_file(self, file_path: str) -> bool:
        """Determine if file path should be excluded from diff processing."""
        lowered = file_path.lower()
        return any(lowered.endswith(suffix) for suffix in self._excluded_suffixes)
