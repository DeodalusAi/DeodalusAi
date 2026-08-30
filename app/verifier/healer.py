from __future__ import annotations

from typing import Type

from app.producer.gateway import LLMGateway
from app.schemas import CodePatch, FilePatch

MAX_HEAL_ATTEMPTS = 3


class MaxRetriesExceeded(RuntimeError):
    """Raised when the healing loop exceeds the safety cap."""


async def heal(
    original_patch: CodePatch,
    failure_summary: str,
    iteration: int,
    gateway: LLMGateway | None = None,
) -> CodePatch:
    """Generate a corrected patch for a failing test while enforcing a hard retry cap.

    This safety cap exists because a persistently broken test could otherwise loop until
    an API rate limit, token budget, or demo timeout is hit. The project planning
    explicitly flagged this as a critical risk, so the repair loop must stop after a
    bounded number of retries even if upstream callers forget to enforce it.
    """
    if iteration >= MAX_HEAL_ATTEMPTS:
        raise MaxRetriesExceeded(
            "Healing loop exceeded the hard safety cap of 3 attempts. "
            "The test suite remains broken after the permitted retries."
        )

    if gateway is None:
        gateway = LLMGateway()

    source_code = "\n\n".join(
        f"### {file_patch.path}\n{file_patch.content}" for file_patch in original_patch.files
    )

    prompt = f"""
You are repairing a broken code patch generated for a software task.

Original code:
{source_code}

Observed test failure summary:
{failure_summary}

Instructions:
- Fix the root cause of the failing behavior.
- Preserve the same overall project structure and file names whenever possible.
- Return a corrected CodePatch matching the same schema used in app.schemas.CodePatch.
- Do not add unrelated refactors; focus only on the failing behavior.
- Return valid structured output only.
"""

    return await gateway.generate_structured(prompt, CodePatch)


if __name__ == "__main__":
    import asyncio

    class FakeGateway:
        def __init__(self):
            self.calls = 0

        async def generate_structured(self, prompt: str, schema: Type[CodePatch]) -> CodePatch:
            self.calls += 1
            return CodePatch(
                summary=f"Attempt {self.calls} fix",
                files=[
                    FilePatch(
                        path="calc.py",
                        content="def add(a, b):\n    return a + b\n",
                    )
                ],
            )

    async def _self_test():
        original = CodePatch(
            summary="Initial broken patch",
            files=[
                FilePatch(
                    path="calc.py",
                    content="def add(a, b):\n    return a - b\n",
                )
            ],
        )

        fake_gateway = FakeGateway()
        attempts = 0

        for iteration in range(4):
            try:
                result = await heal(
                    original_patch=original,
                    failure_summary="AssertionError: expected 5 but got 1",
                    iteration=iteration,
                    gateway=fake_gateway,
                )
                attempts += 1
                print(f"iteration={iteration}, success={result.summary}, calls={fake_gateway.calls}")
            except MaxRetriesExceeded as exc:
                print(f"MaxRetriesExceeded reached as expected: {exc}")
                break

        assert fake_gateway.calls == 3, f"Expected 3 generated fixes before cap, got {fake_gateway.calls}"
        assert attempts == 3, f"Expected exactly 3 successful attempts before cap, got {attempts}"
        print("PASS: healing loop stops at 3 attempts, not 4.")

    asyncio.run(_self_test())
