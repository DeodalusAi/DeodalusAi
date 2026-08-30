import shutil
import subprocess
import sys
from pathlib import Path

from app.schemas import CodePatch, FilePatch


class SandboxRunner:
    def __init__(self, workspace_dir: str = "./sandbox/workspace") -> None:
        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def reset_workspace(self) -> None:
        """Cleans and recreates the isolated execution directory."""
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def apply_patch(self, patch: CodePatch) -> list[str]:
        """Writes all generated files to the local workspace folder."""
        written: list[str] = []
        files = getattr(patch, "files", [])
        for file_spec in files:
            target = self.workspace / file_spec.path
            # Known risk: path traversal such as ../../etc/passwd is not blocked here; a
            # hardened version should reject absolute or parent-directory paths before writing.
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_spec.content, encoding="utf-8")
            written.append(str(target))
        return written

    def execute_tests(self, timeout: int = 30) -> dict:
        """Executes pytest directly inside the workspace."""
        commands = [
            ["pytest", "-v", "--tb=short"],
            [sys.executable, "-m", "pytest", "-v", "--tb=short"],
        ]

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "passed": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                return {
                    "passed": False,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s",
                }

        return {
            "passed": False,
            "stdout": "",
            "stderr": "pytest is not available in the current environment",
        }


if __name__ == "__main__":
    runner = SandboxRunner("./sandbox/workspace")
    runner.reset_workspace()

    patch = CodePatch(
        summary="Add a small calculator and a passing pytest check",
        files=[
            FilePatch(path="calculator.py", content="def add(a, b):\n    return a + b\n"),
            FilePatch(
                path="test_calculator.py",
                content=(
                    "from calculator import add\n\n"
                    "def test_add():\n"
                    "    assert add(2, 3) == 5\n"
                ),
            ),
        ],
    )

    runner.apply_patch(patch)
    print(runner.execute_tests())