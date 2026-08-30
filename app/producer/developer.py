from app.producer.gateway import LLMGateway
from app.schemas import CodePatch, TaskBreakdown

DEVELOPER_SYSTEM_PROMPT = """
You are a Principal Software Engineer.
Your task is to write complete, production-grade Python code and comprehensive unit tests based on an architectural plan.

Strict Rules:
1. Write COMPLETE, self-contained files. Never use placeholders like 'TODO', 'pass', or '...'.
2. Always write pytest unit tests for every implementation file.
3. Place application code in appropriate paths (e.g., 'app/main.py', 'app/models.py', 'app/utils.py').
4. Place test code in 'tests/test_*.py' (e.g., 'tests/test_main.py').
5. Ensure all imports are standard library, pytest, fastapi, pydantic, or local project modules.
6. Write test assertions that verify both standard success paths and edge cases (e.g., 404s, invalid inputs).
"""

class DeveloperAgent:
    def __init__(self, gateway: LLMGateway = None):
        self.gateway = gateway or LLMGateway()

    async def generate_code(self, plan: TaskBreakdown, context_docs: str = "") -> CodePatch:
        """Generates all source files and pytest test files based on the task breakdown."""
        tasks_formatted = "\n".join(
            [f"- [{t.id}] {t.title}: {t.description}" for t in plan.tasks]
        )
        
        prompt = f"""
{DEVELOPER_SYSTEM_PROMPT}

Epic: {plan.epic_title}
Architecture: {plan.architecture_overview}

Task List:
{tasks_formatted}

Additional Architectural Context / Guidelines:
{context_docs or "Follow standard clean Python and FastAPI design patterns."}

Generate all necessary source code files and their corresponding pytest test files.
"""
        return await self.gateway.generate_structured(prompt, CodePatch)

# --- Standalone Verification Test for Person 1 ---
if __name__ == "__main__":
    import asyncio
    from app.schemas import TaskItem

    async def test():
        developer = DeveloperAgent()
        print("=== [Person 1] Testing Developer Agent ===")
        
        mock_plan = TaskBreakdown(
            epic_title="Simple String Tokenizer",
            architecture_overview="A utility module with tokenizing functions and pytest test suite.",
            tasks=[
                TaskItem(id="TASK-1", title="Create Tokenizer", description="Create string tokenizer that splits on whitespace and punctuation."),
                TaskItem(id="TASK-2", title="Create Unit Tests", description="Comprehensive pytest test suite covering edge cases.", dependencies=["TASK-1"])
            ]
        )
        
        patch = await developer.generate_code(mock_plan)
        print(f"\nGenerated Patch Summary: {patch.summary}")
        print(f"Total Files Generated: {len(patch.files)}")
        for f in patch.files:
            print(f"\n--- File: {f.path} ---")
            print(f.content[:200] + ("\n..." if len(f.content) > 200 else ""))

    asyncio.run(test())