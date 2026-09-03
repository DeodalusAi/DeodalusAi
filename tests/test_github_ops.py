import asyncio
import os
import unittest
from unittest.mock import Mock, patch

from github import GithubException

from app.schemas import CodePatch, FilePatch
from app.verifier.github_ops import GitHubOps


class GitHubOpsTests(unittest.TestCase):
    @patch.dict(os.environ, {"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "owner/repo-name"}, clear=True)
    @patch("app.verifier.github_ops.load_dotenv")
    @patch("app.verifier.github_ops.Github")
    def test_create_pull_request_success(self, mock_github_cls, mock_load_dotenv):
        repo = Mock()
        base_ref = Mock()
        base_ref.object.sha = "base-sha"
        repo.get_git_ref.return_value = base_ref
        existing_file = Mock()
        existing_file.sha = "existing-sha"
        repo.get_contents.side_effect = [existing_file, GithubException(404, {"message": "Not Found"}, None)]
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/owner/repo-name/pull/42"
        repo.create_pull.return_value = mock_pr
        mock_github_cls.return_value.get_repo.return_value = repo
        patch_obj = CodePatch(
            summary="Fix the app",
            files=[FilePatch(path="app/example.py", content="print('fixed')\n"), FilePatch(path="README.md", content="# Updated\n")],
        )

        result = asyncio.run(GitHubOps().create_pull_request("Fix app", "Fixes the bug.", patch_obj))

        self.assertEqual(result, "https://github.com/owner/repo-name/pull/42")
        mock_load_dotenv.assert_called_once_with()
        mock_github_cls.assert_called_once_with("fake-token")
        repo.create_git_ref.assert_called_once()
        branch = repo.create_git_ref.call_args.kwargs["ref"].split("/")[-1]
        repo.update_file.assert_called_once_with(path="app/example.py", message="Apply fix: app/example.py", content="print('fixed')\n", sha="existing-sha", branch=branch)
        repo.create_file.assert_called_once_with(path="README.md", message="Create file: README.md", content="# Updated\n", branch=branch)
        repo.create_pull.assert_called_once_with(title="Fix app", body="Fixes the bug.", head=branch, base="main")


if __name__ == "__main__":
    unittest.main()
