from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

from app.producer.developer import DeveloperAgent
from app.producer.gateway import LLMGateway
from app.producer.planner import PlannerAgent
from app.producer.researcher import ResearcherAgent
from app.schemas import AgentState, CodePatch, ReviewResult, TaskBreakdown
from app.verifier.github_ops import GitHubOps
from app.verifier.healer import HealerAgent
from app.verifier.reviewer import ReviewerAgent
from app.verifier.sandbox import SandboxRunner

# Shared singletons across graph nodes
gateway = LLMGateway()
planner_agent = PlannerAgent(gateway=gateway)
researcher_agent = ResearcherAgent(gateway=gateway)
developer_agent = DeveloperAgent(gateway=gateway)
sandbox_runner = SandboxRunner()
reviewer_agent = ReviewerAgent()
healer_agent = HealerAgent(gateway=gateway)
github_ops = GitHubOps()


# --- Graph Node Definitions ---

async def planner_node(state: AgentState) -> Dict[str, Any]:
    """Person 1: Analyzes the prompt and generates a TaskBreakdown."""
    prompt = state["prompt"]
    logs = list(state.get("logs", []))
    logs.append(f"[Planner] Analyzing requirement: '{prompt}'")

    plan: TaskBreakdown = await planner_agent.plan(prompt)
    logs.append(f"[Planner] Generated {len(plan.tasks)} tasks for Epic: '{plan.epic_title}'")

    return {
        "plan": plan,
        "logs": logs,
    }


async def researcher_node(state: AgentState) -> Dict[str, Any]:
    """Person 1: Retrieves architectural patterns from Qdrant vector DB."""
    plan = state["plan"]
    logs = list(state.get("logs", []))
    query = f"{plan.epic_title} {plan.architecture_overview}"

    logs.append("[Researcher] Querying Qdrant for architectural guidelines...")
    context_docs = await researcher_agent.search_context(query)
    logs.append("[Researcher] Context retrieval complete.")

    return {
        "logs": logs,
        "_context_docs": context_docs,
    }


async def developer_node(state: AgentState) -> Dict[str, Any]:
    """Person 1: Generates source code files and pytest test suites."""
    plan = state["plan"]
    context_docs = state.get("_context_docs", "")
    logs = list(state.get("logs", []))

    logs.append("[Developer] Synthesizing source code and pytest suites...")
    patch: CodePatch = await developer_agent.generate_code(plan, context_docs=context_docs)
    logs.append(f"[Developer] Generated {len(patch.files)} files. Summary: {patch.summary}")

    return {
        "code_patch": patch,
        "logs": logs,
    }


def tester_node(state: AgentState) -> Dict[str, Any]:
    """Person 2: Writes files to sandbox and executes pytest via subprocess."""
    patch = state["code_patch"]
    logs = list(state.get("logs", []))

    logs.append("[Sandbox] Applying code patch to isolated workspace...")
    sandbox_runner.reset_workspace()
    written_files = sandbox_runner.apply_patch(patch)
    logs.append(f"[Sandbox] Written {len(written_files)} files to disk.")

    logs.append("[Tester] Running subprocess: pytest -v --tb=short ...")
    test_res = sandbox_runner.execute_tests(timeout=30)

    status_str = "PASSED" if test_res["passed"] else "FAILED"
    logs.append(f"[Tester] Pytest execution {status_str} (Exit code: {test_res['returncode']})")

    return {
        "test_output": test_res,
        "logs": logs,
    }


def reviewer_node(state: AgentState) -> Dict[str, Any]:
    """Person 2: Parses pytest failures and formulates a root cause analysis."""
    test_output = state["test_output"]
    logs = list(state.get("logs", []))

    logs.append("[Reviewer] Analyzing failed test traceback and assertions...")
    review: ReviewResult = reviewer_agent.review(
        stdout=test_output.get("stdout", ""),
        stderr=test_output.get("stderr", "")
    )
    logs.append(f"[Reviewer] Root cause identified: {review.root_cause}")

    return {
        "review": review,
        "logs": logs,
    }


async def healer_node(state: AgentState) -> Dict[str, Any]:
    """Person 2: Generates an auto-corrective CodePatch and increments iteration counter."""
    current_patch = state["code_patch"]
    review = state["review"]
    iteration = state.get("iteration", 0) + 1
    logs = list(state.get("logs", []))

    logs.append(f"[Healer] Auto-healing loop (Iteration {iteration}/{state.get('max_iterations', 3)})...")
    fixed_patch: CodePatch = await healer_agent.heal(
        failing_patch=current_patch,
        review=review
    )
    logs.append(f"[Healer] Corrective patch generated: {fixed_patch.summary}")

    return {
        "code_patch": fixed_patch,
        "iteration": iteration,
        "logs": logs,
    }


async def github_pr_node(state: AgentState) -> Dict[str, Any]:
    """Person 2: Pushes passing code to GitHub and opens a Pull Request."""
    plan = state["plan"]
    patch = state["code_patch"]
    logs = list(state.get("logs", []))

    logs.append("[GitHubOps] All verification checks passed! Publishing branch and Pull Request...")
    pr_url = await github_ops.create_pull_request(
        title=f"feat: {plan.epic_title}",
        body=f"### Architecture Overview\n{plan.architecture_overview}\n\n### Changes\n{patch.summary}",
        patch=patch
    )
    logs.append(f"[GitHubOps] Pull Request opened successfully: {pr_url}")

    return {
        "pr_url": pr_url,
        "logs": logs,
    }


# --- Conditional Routing Logic ---

def route_after_tester(state: AgentState) -> str:
    """Routes execution based on test results and iteration limits."""
    test_output = state.get("test_output", {})
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if test_output.get("passed", False):
        return "github_pr"
    
    if iteration >= max_iterations:
        return END  # Safety cutoff to avoid infinite token loops

    return "reviewer"


# --- Graph Assembly ---

def build_daedalus_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    # 1. Register Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("developer", developer_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("healer", healer_node)
    workflow.add_node("github_pr", github_pr_node)

    # 2. Linear Producer Pipeline
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "developer")
    workflow.add_edge("developer", "tester")

    # 3. Dynamic Self-Healing Cyclic Loop
    workflow.add_conditional_edges(
        "tester",
        route_after_tester,
        {
            "github_pr": "github_pr",
            "reviewer": "reviewer",
            END: END,
        }
    )

    workflow.add_edge("reviewer", "healer")
    workflow.add_edge("healer", "tester")  # Re-execute pytest in sandbox
    workflow.add_edge("github_pr", END)

    return workflow.compile()


daedalus_app = build_daedalus_graph()


# --- Standalone Verification Test for Day 3 ---
if __name__ == "__main__":
    async def run_end_to_end():
        print("=== [Integration] Running Complete DaedalusOS State Graph ===")
        initial_state: AgentState = {
            "prompt": "Create an in-memory string reverser utility with a pytest suite verifying edge cases.",
            "plan": None,
            "code_patch": None,
            "test_output": None,
            "review": None,
            "iteration": 0,
            "max_iterations": 3,
            "pr_url": None,
            "logs": [],
        }

        async for output in daedalus_app.astream(initial_state):
            for node_name, state_update in output.items():
                print(f"\n--- [Node Finished: {node_name.upper()}] ---")
                if "logs" in state_update and state_update["logs"]:
                    print("  Log:", state_update["logs"][-1])

    asyncio.run(run_end_to_end())