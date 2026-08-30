from __future__ import annotations

from typing import Any


def analyze_failure(test_result: dict) -> str:
    """Return a concise pytest failure summary from a sandbox test_result dict.

    The full pytest output can be very long and noisy; when this text is sent to the
    LLM we want only the actionable failure section so the model can focus on the root
    cause instead of raw traceback noise.
    """
    stdout = str(test_result.get("stdout", "") or "")
    stderr = str(test_result.get("stderr", "") or "")
    combined = "\n".join(part for part in [stdout, stderr] if part).strip()

    if not combined:
        return "No pytest output was captured. The test run may have failed before assertions or stdout/stderr were emitted."

    # Prefer the pytest failure block, which contains the actual failing test names and
    # assertion details. This is the most useful part for the healing prompt.
    failure_markers = [
        "=================================== FAILURES ====================================",
        "=========================== short test summary info ===========================",
        "=========== short test summary info ===========",
        "=== FAILURES ===",
        "FAILURES",
    ]

    failure_section: str | None = None
    for marker in failure_markers:
        if marker in combined:
            prefix, suffix = combined.split(marker, 1)
            if marker in [
                "=================================== FAILURES ====================================",
                "=== FAILURES ===",
                "FAILURES",
            ]:
                candidate = suffix
            else:
                candidate = suffix
            if "short test summary info" in candidate.lower():
                candidate = candidate.split("short test summary info", 1)[0]
            if "====" in candidate:
                candidate = candidate.split("====", 1)[0]
            failure_section = candidate.strip()
            break

    if failure_section:
        lines = [line.strip() for line in failure_section.splitlines() if line.strip()]
        summary_lines: list[str] = []
        for line in lines:
            if not summary_lines or len(summary_lines) < 20:
                if line.startswith("="):
                    continue
                if "pytest" in line.lower() and "summary" in line.lower():
                    continue
                summary_lines.append(line)
            else:
                break

        summary = "\n".join(summary_lines[:12])
        if summary:
            return summary

    # Fallback: keep only the lines most likely to describe the failure.
    lines = []
    for raw in combined.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("="):
            continue
        if stripped.startswith("INFO") or stripped.startswith("collected "):
            continue
        if stripped.startswith("pytest"):
            continue
        if "passed" in stripped.lower() and "failed" not in stripped.lower():
            continue
        lines.append(stripped)

    shortlist = []
    for line in lines:
        if any(token in line for token in ["FAILED", "ERROR", "AssertionError", "E   ", "assert "]):
            shortlist.append(line)

    if shortlist:
        return "\n".join(shortlist[:12])

    return "\n".join(combined.splitlines()[-12:])
