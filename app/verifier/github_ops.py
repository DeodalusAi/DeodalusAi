import asyncio
import os
import uuid

from dotenv import load_dotenv
from github import Github, GithubException

from app.schemas import CodePatch


class GitHubOps:
    async def create_pull_request(
        self,
        title: str,
        body: str,
        patch: CodePatch,
        repository: str | None = None,
        base_branch: str | None = None,
    ) -> str:
        """Create a PR from a new branch containing the patch contents."""
        load_dotenv()

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("Missing required environment variable: GITHUB_TOKEN")

        repo_identifier = (repository or os.environ.get("GITHUB_REPO", "")).strip()
        if not repo_identifier:
            raise RuntimeError("Missing required environment variable: GITHUB_REPO")
        if "://" in repo_identifier or repo_identifier.endswith(".git") or repo_identifier.count("/") != 1:
            raise RuntimeError("GITHUB_REPO must use the owner/repository format, for example DeodalusAi/DeodulusAi")

        base_branch = (base_branch or os.environ.get("GITHUB_BASE_BRANCH", "main")).strip() or "main"
        new_branch_name = f"auto-fix-{uuid.uuid4().hex[:8]}"

        def _do_create_pull_request() -> str:
            try:
                github_client = Github(token)
                repo = github_client.get_repo(repo_identifier)
                try:
                    base_ref = repo.get_git_ref(f"heads/{base_branch}")
                except GithubException as exc:
                    if exc.status not in (404, 409) or repo.size != 0 or not patch.files:
                        raise
                    # GitHub cannot create a branch from an empty repository. Seed
                    # the requested base branch with the first generated file.
                    first_file = patch.files[0]
                    repo.create_file(
                        path=first_file.path,
                        message="Initialize repository with generated project",
                        content=first_file.content,
                        branch=base_branch,
                    )
                    base_ref = repo.get_git_ref(f"heads/{base_branch}")
                repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_ref.object.sha)

                for file_patch in patch.files:
                    try:
                        existing = repo.get_contents(file_patch.path, ref=new_branch_name)
                        if isinstance(existing, list):
                            raise RuntimeError(f"Expected a file at '{file_patch.path}', received a directory.")
                        repo.update_file(
                            path=file_patch.path,
                            message=f"Apply fix: {file_patch.path}",
                            content=file_patch.content,
                            sha=existing.sha,
                            branch=new_branch_name,
                        )
                    except GithubException as exc:
                        if exc.status != 404:
                            raise
                        repo.create_file(
                            path=file_patch.path,
                            message=f"Create file: {file_patch.path}",
                            content=file_patch.content,
                            branch=new_branch_name,
                        )

                pull_request = repo.create_pull(title=title, body=body, head=new_branch_name, base=base_branch)
                return pull_request.html_url
            except GithubException as exc:
                raise RuntimeError(
                    f"GitHub API request failed ({exc.status}) while creating the pull request: "
                    f"{getattr(exc, 'data', {})}. Check GITHUB_REPO, GITHUB_BASE_BRANCH, "
                    "token permissions, and patch contents."
                ) from exc

        return await asyncio.to_thread(_do_create_pull_request)
