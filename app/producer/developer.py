from __future__ import annotations

import asyncio
from typing import Optional

from app.producer.gateway import LLMGateway
from app.schemas import CodePatch, TaskBreakdown

DEVELOPER_SYSTEM_PROMPT = """
You are a Principal Software Engineer and Python Core Developer.
Your responsibility is to generate complete, production-grade Python implementations and their corresponding pytest test suites based on a structured TaskBreakdown.

Strict Code Synthesis Rules:
1. Complete Implementations: Write full, self-contained files. NEVER use placeholders such as 'TODO', 'pass', or '...'.
2. Paired Test Suite: Always generate a matching 'tests/test_*.py' file for every module created.
3. Path Conventions:
   - Place source modules in 'app/' (e.g., 'app/main.py', 'app/models.py', 'app/utils.py').
   - Place test modules in 'tests/' (e.g., 'tests/test_main.py').
4. Import Correctness:
   - Use relative or standard package imports assuming the workspace root is the base directory.
   - Use standard library, fastapi, pydantic, pytest, and httpx where applicable.
5. Deterministic Test Design:
   - Tests must cover core functionality, boundary conditions, and error cases (e.g., 404, 422, invalid payloads).
   - If writing FastAPI tests, use `starlette.testclient.TestClient` or `fastapi.testclient.TestClient`.
6. Return Format:
   - Return strictly a valid CodePatch containing a summary and an array of FilePatch objects (with 'path' and 'content').
"""

class DeveloperAgent:
    def __init__(self, gateway: Optional[LLMGateway] = None):
        """Initializes the Developer Agent with the unified resilient LLM Gateway."""
        self.gateway = gateway or LLMGateway()

    async def generate_code(self, plan: TaskBreakdown, context_docs: str = "") -> CodePatch:
        """
        Transforms an architectural TaskBreakdown into a complete, multi-file CodePatch
        containing both source code and executable pytest suites.
        """
        tasks_text = "\n".join(
            f"  - [{t.id}] {t.title}: {t.description} (Prerequisites: {', '.join(t.dependencies) if t.dependencies else 'None'})"
            for t in plan.tasks
        )

        user_prompt = f"""
{DEVELOPER_SYSTEM_PROMPT}

Epic Title:
"{plan.epic_title}"

Architecture Overview:
"{plan.architecture_overview}"

Planned Tasks:
{tasks_text}

Additional Architectural Context / Guidelines:
"{context_docs if context_docs else 'Follow standard clean architecture with isolated modular components.'}"

Generate all necessary source code files and comprehensive pytest suites.
"""
        return await self.gateway.generate_structured(
            prompt=user_prompt,
            schema=CodePatch,
            model="gemini-2.0-flash"
        )


# --- Standalone Verification Test for Person 1 ---
if __name__ == "__main__":
    from app.schemas import TaskItem

    async def run_standalone_test():
        developer = DeveloperAgent()
        print("=== [Person 1] Testing Developer Agent ===")

        mock_plan = TaskBreakdown(
            epic_title="FastAPI In-Memory Token Bucket Rate Limiter",
            architecture_overview="A lightweight rate limiting middleware with an in-memory bucket store and unit tests.",
            tasks=[
                TaskItem(
                    id="TASK-1",
                    title="Define TokenBucket Class",
                    description="Implement TokenBucket with capacity, fill_rate, and consume() method."
                ),
                TaskItem(
                    id="TASK-2",
                    title="Build FastAPI Middleware",
                    description="Create BaseHTTPMiddleware intercepting requests and returning 429 when exhausted.",
                    dependencies=["TASK-1"]
                ),
                TaskItem(
                    id="TASK-3",
                    title="Write Pytest Suite",
                    description="Test normal request flow, rate limit triggers (429), and token refill behavior.",
                    dependencies=["TASK-2"]
                )
            ]
        )

        patch: CodePatch = await developer.generate_code(mock_plan)

        print("\n✅ CodePatch Successfully Generated!")
        print(f"Summary: {patch.summary}")
        print(f"Total Files Synthesized: {len(patch.files)}\n")

        for file in patch.files:
            print(f"📁 Path: {file.path}")
            preview_lines = file.content.strip().split("\n")[:8]
            print("   " + "\n   ".join(preview_lines))
            if len(file.content.strip().split("\n")) > 8:
                print("   ...")
            print("-" * 50)

    asyncio.run(run_standalone_test())