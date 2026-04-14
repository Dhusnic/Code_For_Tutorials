from __future__ import annotations

import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_module = types.ModuleType("requests")
    requests_exceptions = types.ModuleType("requests.exceptions")
    requests_adapters = types.ModuleType("requests.adapters")

    class DummyRequestException(Exception):
        pass

    class DummyJSONDecodeError(ValueError):
        pass

    class DummyResponse:
        ok = False
        status_code = 500
        text = ""
        headers = {}
        content = b""

        def json(self):
            return {}

        def raise_for_status(self):
            raise DummyRequestException("requests is unavailable in this test environment")

    class DummySession:
        def __init__(self):
            self.headers = {}

        def mount(self, *_args, **_kwargs):
            return None

        def request(self, *_args, **_kwargs):
            raise DummyRequestException("requests is unavailable in this test environment")

    class DummyHTTPAdapter:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    def dummy_get(*_args, **_kwargs):
        raise DummyRequestException("requests is unavailable in this test environment")

    requests_module.Response = DummyResponse
    requests_module.Session = DummySession
    requests_module.get = dummy_get
    requests_module.RequestException = DummyRequestException
    requests_module.JSONDecodeError = DummyJSONDecodeError
    requests_module.adapters = requests_adapters
    requests_module.exceptions = requests_exceptions

    requests_exceptions.JSONDecodeError = DummyJSONDecodeError
    requests_exceptions.RequestException = DummyRequestException
    requests_adapters.HTTPAdapter = DummyHTTPAdapter

    sys.modules["requests"] = requests_module
    sys.modules["requests.exceptions"] = requests_exceptions
    sys.modules["requests.adapters"] = requests_adapters

from pr_manager.pr_workflow import PRWorkflowService

try:
    from fastapi.testclient import TestClient
    import main as app_module
except ModuleNotFoundError:
    TestClient = None
    app_module = None


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one git command for test repository setup."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class ApprovalPreviewBuilderTests(unittest.TestCase):
    """Validate Git diff preview normalization for pending PR approvals."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.workspace_repo = self.base_dir / "workspace"
        self._create_repository_with_origin_ref()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_repository_with_origin_ref(self) -> None:
        self.workspace_repo.mkdir(parents=True, exist_ok=True)
        run_git(["init"], cwd=self.workspace_repo)
        run_git(["config", "user.name", "Preview Tester"], cwd=self.workspace_repo)
        run_git(["config", "user.email", "preview.tester@example.com"], cwd=self.workspace_repo)
        run_git(["checkout", "-b", "main"], cwd=self.workspace_repo)

        write_text(self.workspace_repo / "mod.txt", "old value\nkeep\n")
        write_text(self.workspace_repo / "delete.txt", "remove me\n")
        write_text(self.workspace_repo / "rename_from.txt", "rename me\nstay readable\n")
        write_bytes(self.workspace_repo / "binary.bin", b"\x00\x01\x02original\x00")
        write_text(
            self.workspace_repo / "big.txt",
            "".join(f"old line {index:04d}\n" for index in range(1, 901)),
        )

        run_git(["add", "--all"], cwd=self.workspace_repo)
        run_git(["commit", "-m", "Initial content"], cwd=self.workspace_repo)
        run_git(["update-ref", "refs/remotes/origin/main", "HEAD"], cwd=self.workspace_repo)

        write_text(self.workspace_repo / "mod.txt", "new value\nkeep\n")
        write_text(self.workspace_repo / "added.txt", "brand new file\n")
        (self.workspace_repo / "delete.txt").unlink()
        (self.workspace_repo / "renamed").mkdir(exist_ok=True)
        run_git(["mv", "rename_from.txt", "renamed/rename_to.txt"], cwd=self.workspace_repo)
        write_text(self.workspace_repo / "renamed" / "rename_to.txt", "rename me\nupdated content\n")
        write_bytes(self.workspace_repo / "binary.bin", b"\x00\x01\x02changed\xff")
        write_text(
            self.workspace_repo / "big.txt",
            "".join(f"new line {index:04d}\n" for index in range(1, 901)),
        )

    def test_build_approval_preview_covers_modified_added_deleted_renamed_binary_and_truncated(self) -> None:
        preview = PRWorkflowService.build_approval_preview(
            workspace_repo_path=self.workspace_repo,
            target_branch="main",
            source_branch="feature/test-preview",
            repo_root_label="workspace",
            request_id="req-123",
            selected_files=[
                {"path": "mod.txt", "status": "modified"},
                {"path": "added.txt", "status": "added"},
                {"path": "delete.txt", "status": "deleted"},
                {
                    "path": "renamed/rename_to.txt",
                    "status": "renamed",
                    "old_path": "rename_from.txt",
                },
                {"path": "binary.bin", "status": "modified"},
                {"path": "big.txt", "status": "modified"},
            ],
        )

        self.assertEqual(preview["request_id"], "req-123")
        self.assertEqual(preview["preview_base_ref"], "origin/main")
        self.assertEqual(preview["selected_file_count"], 6)
        self.assertEqual(preview["effective_file_count"], 6)

        files_by_path = {entry["path"]: entry for entry in preview["files"]}
        self.assertEqual(files_by_path["mod.txt"]["status"], "modified")
        self.assertGreater(files_by_path["mod.txt"]["additions"], 0)
        self.assertGreater(files_by_path["mod.txt"]["deletions"], 0)

        self.assertEqual(files_by_path["added.txt"]["status"], "added")
        self.assertGreater(files_by_path["added.txt"]["additions"], 0)

        self.assertEqual(files_by_path["delete.txt"]["status"], "deleted")
        self.assertGreater(files_by_path["delete.txt"]["deletions"], 0)

        renamed = files_by_path["renamed/rename_to.txt"]
        self.assertEqual(renamed["status"], "renamed")
        self.assertEqual(renamed["old_path"], "rename_from.txt")

        binary = files_by_path["binary.bin"]
        self.assertTrue(binary["is_binary"])
        self.assertIn("Binary file changed", binary["message"])

        truncated = files_by_path["big.txt"]
        self.assertTrue(truncated["is_truncated"])
        self.assertGreater(truncated["truncated_line_count"], 0)


@unittest.skipUnless(TestClient is not None and app_module is not None, "fastapi test dependencies are not installed")
class ApprovalPreviewApiTests(unittest.TestCase):
    """Validate approval preview endpoint responses for paused jobs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def test_approval_preview_endpoint_returns_live_preview(self) -> None:
        approval_request = {
            "request_id": "req-1",
            "workspace_repo_path": "D:/workspace",
            "target_branch": "main",
            "source_branch": "feature/demo",
            "repo_root_label": "workspace",
            "selected_files": [{"path": "mod.txt", "status": "modified", "old_path": ""}],
        }
        preview_payload = {
            "request_id": "req-1",
            "files": [{"path": "mod.txt", "status": "modified", "hunks": []}],
        }

        with patch.object(app_module.job_manager, "get_pending_approval", return_value=approval_request) as get_pending:
            with patch.object(app_module.PRWorkflowService, "build_approval_preview", return_value=preview_payload) as build_preview:
                response = self.client.get("/api/jobs/job-123/approval-preview", params={"request_id": "req-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), preview_payload)
        get_pending.assert_called_once_with("job-123", "req-1")
        build_preview.assert_called_once_with(
            workspace_repo_path="D:/workspace",
            target_branch="main",
            selected_files=approval_request["selected_files"],
            source_branch="feature/demo",
            repo_root_label="workspace",
            request_id="req-1",
        )

    def test_approval_preview_endpoint_rejects_invalid_request_id(self) -> None:
        with patch.object(
            app_module.job_manager,
            "get_pending_approval",
            side_effect=ValueError("Approval request id does not match current pending request."),
        ):
            response = self.client.get("/api/jobs/job-123/approval-preview", params={"request_id": "wrong"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Approval request id does not match", response.json()["detail"])

    def test_approval_preview_endpoint_rejects_non_waiting_jobs(self) -> None:
        with patch.object(
            app_module.job_manager,
            "get_pending_approval",
            side_effect=RuntimeError("Job is not waiting for approval: job-123"),
        ):
            response = self.client.get("/api/jobs/job-123/approval-preview", params={"request_id": "req-1"})

        self.assertEqual(response.status_code, 409)
        self.assertIn("Job is not waiting for approval", response.json()["detail"])
