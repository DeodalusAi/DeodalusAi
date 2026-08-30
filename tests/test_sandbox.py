import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas import CodePatch, FilePatch
from app.verifier.sandbox import SandboxRunner


def test_apply_patch_writes_file_content(tmp_path):
    runner = SandboxRunner(str(tmp_path / "workspace"))
    patch = CodePatch(
        summary="Write a simple Python file",
        files=[
            FilePatch(path="example.py", content="VALUE = 42\n"),
        ],
    )

    written = runner.apply_patch(patch)

    assert written == [str(tmp_path / "workspace" / "example.py")]
    assert (tmp_path / "workspace" / "example.py").read_text(encoding="utf-8") == "VALUE = 42\n"


def test_apply_patch_creates_nested_directories(tmp_path):
    runner = SandboxRunner(str(tmp_path / "workspace"))
    patch = CodePatch(
        summary="Write nested file",
        files=[
            FilePatch(path="src/utils/helper.py", content="def add(a, b):\n    return a + b\n"),
        ],
    )

    written = runner.apply_patch(patch)

    target = tmp_path / "workspace" / "src" / "utils" / "helper.py"
    assert written == [str(target)]
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"


def test_execute_tests_returns_passed_true_for_passing_test(tmp_path):
    runner = SandboxRunner(str(tmp_path))
    patch = CodePatch(
        summary="Create passing arithmetic code",
        files=[
            FilePatch(path="math_utils.py", content="def add(a, b):\n    return a + b\n"),
            FilePatch(
                path="test_math_utils.py",
                content=(
                    "from math_utils import add\n\n"
                    "def test_add():\n"
                    "    assert add(2, 3) == 5\n"
                ),
            ),
        ],
    )

    runner.apply_patch(patch)
    result = runner.execute_tests(timeout=30)

    assert result["passed"] is True
    assert "1 passed" in result["stdout"]
    assert result["stderr"] == ""


def test_execute_tests_returns_failed_for_failing_test(tmp_path):
    runner = SandboxRunner(str(tmp_path))
    patch = CodePatch(
        summary="Create failing arithmetic code",
        files=[
            FilePatch(path="math_utils.py", content="def add(a, b):\n    return a + b\n"),
            FilePatch(
                path="test_math_utils.py",
                content=(
                    "from math_utils import add\n\n"
                    "def test_add():\n"
                    "    assert add(2, 3) == 99\n"
                ),
            ),
        ],
    )

    runner.apply_patch(patch)
    result = runner.execute_tests(timeout=30)

    assert result["passed"] is False
    assert "FAILED" in result["stdout"] or "AssertionError" in result["stdout"]


def test_execute_tests_times_out_and_reports_timeout(tmp_path):
    runner = SandboxRunner(str(tmp_path))
    patch = CodePatch(
        summary="Create a test that hangs",
        files=[
            FilePatch(
                path="test_hang.py",
                content=(
                    "import time\n\n"
                    "def test_hang():\n"
                    "    time.sleep(5)\n"
                    "    assert True\n"
                ),
            ),
        ],
    )

    runner.apply_patch(patch)
    result = runner.execute_tests(timeout=2)

    assert result["passed"] is False
    assert "Execution timed out after 2s" in result["stderr"]
