from app.producer.gateway import LLMGateway
from app.schemas import TaskBreakdown

PLANNER_SYSTEM_PROMPT = """
You are a Staff Software Architect and Technical Lead.
Your job is to analyze a software requirement and create a clear, execution-ready engineering plan.

Guidelines:
1. Break down the requirement into discrete, sequential subtasks (e.g., Schema/Models -> Business Logic/Core -> API Endpoints -> Unit Tests).
2. Explicitly specify task dependencies (e.g., TASK-2 depends on TASK-1).
3. Provide a concise architectural overview describing the tech stack, data flow, and file layout.
4. Keep the scope targeted, practical, and clean for a Python/FastAPI environment.
"""

class PlannerAgent:
    def __init__(self, gateway: LLMGateway = None):
        self.gateway = gateway or LLMGateway()

    async def plan(self, user_requirement: str) -> TaskBreakdown:
        """Analyzes requirement and returns a structured TaskBreakdown."""
        prompt = f"""
{PLANNER_SYSTEM_PROMPT}

User Requirement:
"{user_requirement}"

Generate the complete architecture overview and task breakdown.
"""
        return await self.gateway.generate_structured(prompt, TaskBreakdown)

# --- Standalone Verification Test for Person 1 ---
if __name__ == "__main__":
    import asyncio

    async def test():
        planner = PlannerAgent()
        print("=== [Person 1] Testing Planner Agent ===")
        req = "Build a URL shortener with SQLite persistence, click tracking, and custom short code support."
        result = await planner.plan(req)
        
        print(f"\nEpic: {result.epic_title}")
        print(f"Architecture: {result.architecture_overview}\n")
        print("Tasks:")
        for task in result.tasks:
            deps = f" (Depends on: {', '.join(task.dependencies)})" if task.dependencies else ""
            print(f"  [{task.id}] {task.title}{deps}")
            print(f"      {task.description}")

    asyncio.run(test())