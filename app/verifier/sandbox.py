import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any
from app.schemas import CodePatch

class SandboxRunner:
    def __init__(self, workspace_dir: str = "./sandbox/workspace"):
        self.workspace = Path(workspace_dir).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def reset_workspace(self):
        """Cleans and recreates the isolated execution directory."""
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def apply_patch(self, patch: CodePatch) -> list[str]:
        """Writes all generated files to the local workspace folder."""
        written = []
        for file_spec in patch.files:
            dest = self.workspace / file_spec.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(file_spec.content, encoding="utf-8")
            written.append(str(file_spec.path))
        return written

    def execute_tests(self, timeout: int = 30) -> Dict[str, Any]:
        """Executes pytest directly inside the workspace."""
        try:
            res = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "passed": res.returncode == 0,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "returncode": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "returncode": -1
            }

# Standalone verification script for Person 2
if __name__ == "__main__":
    from app.schemas import FileSpec

    runner = SandboxRunner()
    runner.reset_workspace()

    mock_patch = CodePatch(
        summary="Test Calculator Run",
        files=[
            FileSpec(path="calc.py", content="def add(a, b):\n    return a + b\n"),
            FileSpec(path="test_calc.py", content="from calc import add\ndef test_add():\n    assert add(2, 2) == 4\n")
        ]
    )

    runner.apply_patch(mock_patch)
    results = runner.execute_tests()
    print("=== [Person 2] Testing Sandbox Pytest Execution ===")
    print(f"Passed: {results['passed']}")
    print(f"Stdout:\n{results['stdout']}")
    if results['passed']:
        print("✅ Sandbox & Pytest Runner Verified!")