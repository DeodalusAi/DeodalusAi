import asyncio
import os

import pytest

from app.schemas import CodePatch
from app.verifier.github_ops import GitHubOps


def test_github_repo_requires_owner_repository(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPO", "https://github.com/owner/repo.git")

    with pytest.raises(RuntimeError, match="owner/repository"):
        asyncio.run(GitHubOps().create_pull_request("title", "body", CodePatch(summary="x")))
