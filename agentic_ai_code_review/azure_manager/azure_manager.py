import base64
import logging
from typing import Dict, List, Optional, Any
from venv import logger
import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException
import json
import difflib



class AzureDevOpsError(Exception):
    """Base exception for Azure DevOps API errors."""


class AzureDevOpsClient:
    """
    Azure DevOps REST API client with PAT authentication,
    retries, and structured error handling.
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    def __init__(
        self,
        organization: str,
        project: str,
        pat_token: str,
        timeout: int = 30,
    ) -> None:
        self.organization = organization
        self.project = project
        self.base_url = f"https://dev.azure.com/{organization}/{project}"
        self.timeout = timeout
        token = f"{self.organization}:{pat_token}".encode("utf-8")
        self._auth_header = base64.b64encode(token).decode("utf-8")
        self.session = self._create_session(pat_token)

    @staticmethod
    def _create_session(pat_token: str) -> Session:
        session = requests.Session()

        auth_token = base64.b64encode(f":{pat_token}".encode()).decode()
        session.headers.update(
            {
                "Authorization": f"Basic {auth_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        return session
    def _post(
        self,
        url: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Performs a POST request to Azure DevOps REST API.

        Args:
            url: API path (relative) or full URL
            payload: JSON body
            params: Optional query params

        Returns:
            Parsed JSON response

        Raises:
            AzureDevOpsError: On any HTTP or API failure
        """

        full_url = url if url.startswith("http") else f"{self.base_url}{url}"

        headers = {
            "Authorization": f"Basic {self._auth_header}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            self.logger.debug(
                "Azure DevOps POST %s | params=%s | payload=%s",
                full_url,
                params,
                json.dumps(payload, indent=2),
            )

            response: Response = requests.post(
                full_url,
                headers=headers,
                params=params,
                json=payload,
                timeout=self.timeout,
            )

        except RequestException as exc:
            self.logger.exception("Network error calling Azure DevOps POST %s", full_url)
            raise AzureDevOpsError(f"Network error: {exc}") from exc

        # Handle non-2xx responses
        if not response.ok:
            try:
                error_body = response.json()
            except ValueError:
                error_body = response.text

            self.logger.error(
                "Azure DevOps POST failed [%s] %s | response=%s",
                response.status_code,
                full_url,
                error_body,
            )

            raise AzureDevOpsError(
                f"API call failed ({response.status_code}): {error_body}"
            )

        # Parse JSON safely
        try:
            return response.json()
        except ValueError as exc:
            self.logger.exception("Invalid JSON response from Azure DevOps")
            raise AzureDevOpsError("Invalid JSON response") from exc
    def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        logger.debug("GET %s params=%s", url, params)

        response: Response = self.session.get(
            url, params=params, timeout=self.timeout
        )

        if not response.ok:
            logger.error(
                "Azure DevOps API failed [%s]: %s",
                response.status_code,
                response.text,
            )
            raise AzureDevOpsError(
                f"API call failed ({response.status_code}): {response.text}"
            )

        return response.json()

    def get_pr_changes(
        self,
        repository_name: str,
        pull_request_id: int,
    ) -> List[Dict]:
        """
        Fetch all file-level changes for a pull request.

        Returns:
            List of changes with file paths and change types.
        """
        repository_id = self.get_repository_id(repository_name=repository_name)
        url = (
            f"{self.base_url}/_apis/git/repositories/"
            f"{repository_id}/pullRequests/{pull_request_id}/iterations"
        )

        url = url+f"/{self.get_last_iteration_id(repository_name, pull_request_id)}/changes"
        params = {"api-version": "7.1-preview.1",
                  "$top":5000,
                  "includeContent": "true",
                }

        data = self._get(url, params)
        

        logger.info(
            "Fetched %d file changes for PR %s",
            len(data.get("changeEntries", [])),
            pull_request_id,
        )
        return data.get("changeEntries", [])

    def get_file_diff(
        self,
        repository_name: str,
        base_object_id: str,
        target_object_id: str,
        file_path: str,
    ) -> List[Dict]:
        """
        Fetch file contents using blob OIDs, compute diff using difflib,
        and return structured hunks with line numbers.
        """

        # Fetch file contents by OID
        base_content = self.get_file_by_oid(
            repository_name=repository_name,
            oid=base_object_id,
        )
        target_content = self.get_file_by_oid(
            repository_name=repository_name,
            oid=target_object_id,
        )
        excluded_files = [".DS_Store", "thumbs.db",".env",".db",".sqlite3",".log",".pyc",".json",".ini","environment.instance.ts","requirements.txt",".png",".feature"]

        base_lines = base_content.splitlines()
        target_lines = target_content.splitlines()

        matcher = difflib.SequenceMatcher(None, base_lines, target_lines)

        hunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            avoid = any(file_path.endswith(f) for f in excluded_files)
            if tag == "equal" or avoid:
                continue

            hunk = {
                "file": file_path,
                "hunk": {
                    "old_start": i1 + 1 if i1 < len(base_lines) else None,
                    "new_start": j1 + 1 if j1 < len(target_lines) else None,
                    "context": base_lines[
                        max(0, i1 - 5) :
                        min(len(base_lines), i2 + 5)
                    ] if i1 > 0 else [],
                    "removed": [],
                    "added": [],
                },
            }

            # Removed lines
            if tag in ("replace", "delete"):
                for idx, line in enumerate(base_lines[i1:i2], start=i1 + 1):
                    hunk["hunk"]["removed"].append(
                        {
                            "line": line,
                            "old_line": idx,
                        }
                    )

            # Added lines
            if tag in ("replace", "insert"):
                for idx, line in enumerate(target_lines[j1:j2], start=j1 + 1):
                    hunk["hunk"]["added"].append(
                        {
                            "line": line,
                            "new_line": idx,
                        }
                    )

            if hunk["hunk"]["added"] or hunk["hunk"]["removed"]:
                hunks.append(hunk)

        return hunks
    
    def get_file_by_oid(
        self,
        repository_name: str,
        oid: str,
    ) -> str:
        """
        Fetch raw file content from Azure DevOps Git blob API using OID.
        """

        repository_id = self.get_repository_id(repository_name=repository_name)

        url = (
            f"{self.base_url}/_apis/git/repositories/"
            f"{repository_id}/blobs/{oid}"
        )

        params = {
            "api-version": "7.0",
        }

        headers = {
            "Authorization": f"Basic {self._auth_header}",
            "Accept": "application/octet-stream",
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.text

        except requests.RequestException as exc:
            raise AzureDevOpsError(
                f"Failed to fetch blob {oid}: {exc}"
            ) from exc

    def get_pr_content_changes(
        self,
        repository_name: str,
        pull_request_id: int,
        instruction: str,
    ) -> list:
        """
        Returns full PR content changes with line numbers and hunks.
        """
        changes = self.get_pr_changes(repository_name=repository_name, pull_request_id=pull_request_id)
        results = []

        for change in changes:
            item = change.get("item")
            if not item or change["changeType"] != "edit":
                continue

            diff = self.get_file_diff(
                repository_name=repository_name,
                base_object_id=item["originalObjectId"],
                target_object_id=item["objectId"],
                file_path=item["path"],
            )
            results.extend(diff)

        return results

    def normalize_change_entries(self, change_entries: list) -> list:
        normalized = []

        for entry in change_entries:
            file_path = entry["item"]["path"]

            for diff in entry.get("diffs", []):
                for hunk in diff.get("hunks", []):
                    context, added, removed = [], [], []

                    for line in hunk["lines"]:
                        if line["lineType"] == "context":
                            context.append(line["content"])
                        elif line["lineType"] == "add":
                            added.append({
                                "line": line["content"],
                                "new_line": line["newLineNumber"]
                            })
                        elif line["lineType"] == "remove":
                            removed.append({
                                "line": line["content"],
                                "old_line": line["oldLineNumber"]
                            })

                    normalized.append({
                        "file": file_path.split("/")[-1],
                        "hunk": {
                            "old_start": hunk["oldStartLine"],
                            "new_start": hunk["newStartLine"],
                            "context": context,
                            "removed": removed,
                            "added": added
                        }
                    })

        return normalized


    def get_last_iteration_id(
        self,
        repository_name: str,
        pull_request_id: int,
    ) -> int:
        """
        Fetch the last iteration ID for a pull request.

        Returns:
            Last iteration ID as an integer.
        """
        repository_id = self.get_repository_id(repository_name=repository_name)
        url = (
            f"{self.base_url}/_apis/git/repositories/"
            f"{repository_id}/pullRequests/{pull_request_id}/iterations"
        )

        params = {"api-version": "7.1-preview.1"}

        data = self._get(url, params)
        iterations = data.get("value", [])
        if not iterations:
            raise AzureDevOpsError(f"No iterations found for PR {pull_request_id}")

        last_iteration = iterations[-1]
        return last_iteration.get("id")

    def get_pr_comments(
        self,
        repository_name: str,
        pull_request_id: int,
    ) -> List[Dict]:
        """
        Fetch all comment threads and comments for a pull request.

        Returns:
            List of threads with comments and metadata.
        """
        
        repository_id = self.get_repository_id(repository_name=repository_name)
        url = (
            f"{self.base_url}/_apis/git/repositories/"
            f"{repository_id}/pullRequests/{pull_request_id}/threads"
        )

        params = {"api-version": "7.1-preview.1"}

        data = self._get(url, params)
        threads = []

        for thread in data.get("value", []):
            comments = []
            for comment in thread.get("comments", []):
                if comment.get("commentType","") == "system" :
                    continue  # Skip system comments
                comments.append(
                    {
                        "id": comment.get("id"),
                        "content": comment.get("content"),
                        "author": comment.get("author", {}).get("displayName"),
                        "publishedDate": comment.get("publishedDate"),
                        "commentType": comment.get("commentType"),
                    }
                )
            if thread.get("isDeleted", False) or thread.get("status") != "active" or not comments:
                continue  # Skip deleted or closed threads
            threads.append(
                {
                    "threadId": thread.get("id"),
                    "status": thread.get("status"),
                    "isDeleted": thread.get("isDeleted"),
                    "comments": comments,
                }
            )

        logger.info(
            "Fetched %d comment threads for PR %s",
            len(threads),
            pull_request_id,
        )
        return threads

    def get_repository_id(
        self,
        repository_name: str,
    ) -> str:
        """
        Fetch repository ID (GUID) by repository name.

        Args:
            client: AzureDevOpsClient instance
            repository_name: Repo name as seen in Azure DevOps

        Returns:
            Repository ID (GUID)

        Raises:
            ValueError if repository is not found
        """
        url = f"{self.base_url}/_apis/git/repositories"
        params = {"api-version": "7.1"}

        data = self._get(url, params)

        for repo in data.get("value", []):
            if repo.get("name") == repository_name:
                return repo["id"]

        raise ValueError(f"Repository '{repository_name}' not found")