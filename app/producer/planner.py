from __future__ import annotations

import asyncio
from typing import Optional

from app.producer.gateway import LLMGateway
from app.schemas import TaskBreakdown

PLANNER_SYSTEM_PROMPT = """
You are a Staff Software Architect and Engineering Lead.
Your responsibility is to analyze software requirements and break them down into an execution-ready, dependency-ordered technical task graph.

Strict Planning Rules:
1. Break down the project into 3 to 6 logical, atomic tasks.
2. Every task MUST have a deterministic ID formatted as 'TASK-1', 'TASK-2', etc.
3. Explicitly link dependencies using task IDs (e.g., schemas/models must be created before business logic, and business logic before API routes).
4. Provide a concrete 'architecture_overview' describing data flow, modules, database choices, and key libraries.
5. Emphasize standard Python/FastAPI conventions and ensure dedicated tasks for unit testing.
6. Keep the scope clean and production-ready.
"""

class PlannerAgent:
    def __init__(self, gateway: Optional[LLMGateway] = None):
        """Initializes the Planner Agent with the unified resilient LLM Gateway."""
        self.gateway = gateway or LLMGateway()

    async def plan(self, user_requirement: str) -> TaskBreakdown:
        """
        Transforms a raw user requirement string into a structured TaskBreakdown.
        Guaranteed to return a valid Pydantic TaskBreakdown via LLMGateway.
        """
        user_prompt = f"""
{PLANNER_SYSTEM_PROMPT}

User Requirement:
"{user_requirement.strip()}"

Analyze the requirement and generate the complete architecture overview and task breakdown.
"""
        return await self.gateway.generate_structured(
            prompt=user_prompt,
            schema=TaskBreakdown,
            model="gemini-2.0-flash"
        )


# --- Standalone Verification Test for Person 1 ---
if __name__ == "__main__":
    async def run_standalone_test():
        planner = PlannerAgent()
        print("=== [Person 1] Testing Planner Agent ===")
        test_requirement = "Build a FastAPI rate-limiter middleware using Redis with configurable token bucket limits."
        
        result: TaskBreakdown = await planner.plan(test_requirement)
        
        print("\n✅ Task Plan Successfully Generated!")
        print(f"Epic Title: {result.epic_title}")
        print(f"\nArchitecture Overview:\n{result.architecture_overview}\n")
        print("Task Dependency Graph:")
        for task in result.tasks:
            deps = f" -> Depends on: {', '.join(task.dependencies)}" if task.dependencies else " -> Root Task"
            print(f"  [{task.id}] {task.title}{deps}")
            print(f"       Details: {task.description}")

    asyncio.run(run_standalone_test())