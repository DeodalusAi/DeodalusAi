from langgraph.graph import StateGraph, END
from app.producer.gateway import LLMGateway
from app.schemas import AgentState
from app.verifier.healer import heal
from app.verifier.reviewer import analyze_failure
from app.verifier.sandbox import SandboxRunner
from app.verifier.github_ops import GitHubOps
from app.observability.metrics import HEALING_CYCLES, observe_node, record_test_result

# Shared gateway for heal() calls that use the real LLM structure API.
gateway = LLMGateway()

try:
    from app.producer.planner import PlannerAgent
    from app.producer.researcher import ResearcherAgent
    from app.producer.developer import DeveloperAgent
except ModuleNotFoundError:
    import asyncio
    
    class PlannerAgent:
        async def plan(self):
            await asyncio.sleep(0)  # Yield control to make it a proper async function
            return None

    class ResearcherAgent:
        def search_context(self):
            return ""

    class DeveloperAgent:
        async def generate_code(self):
            await asyncio.sleep(0)  # Yield control to make it a proper async function
            return None

planner_agent = PlannerAgent(gateway=gateway)
researcher_agent = ResearcherAgent(gateway=gateway)
developer_agent = DeveloperAgent(gateway=gateway)

# Node wrapper functions
@observe_node("planner")
async def planner_node(state: AgentState) -> AgentState:
    """Person 1: Plan the epic into tasks"""
    state["plan"] = await planner_agent.plan(state["prompt"])
    state["logs"].append(f"Plan generated: {state['plan'].epic_title}")
    return state

@observe_node("researcher")
def researcher_node(state: AgentState) -> AgentState:
    """Person 1: Research architectural context"""
    context = researcher_agent.search_context(state["prompt"], limit=2)
    state["logs"].append(f"Research Context: {context}")
    # Store context for developer agent to use
    if "research_context" not in state:
        state["research_context"] = context
    return state

@observe_node("developer")
async def developer_node(state: AgentState) -> AgentState:
    """Person 1: Generate code from plan"""
    if not state["plan"]:
        state["logs"].append("No plan available for development")
        return state
    state["code_patch"] = await developer_agent.generate_code(
        state["plan"], context_docs=state.get("research_context", "")
    )
    state["logs"].append(
        f"Code generated: {len(state['code_patch'].files)} file(s) synthesized"
    )
    return state

@observe_node("tester")
def tester_node(state: AgentState) -> AgentState:
    """Person 2: Execute tests via SandboxRunner"""
    if not state["code_patch"]:
        state["logs"].append("No code patch available for testing")
        return state

    try:
        runner = SandboxRunner()
        runner.reset_workspace()
        runner.apply_patch(state["code_patch"])
        result = runner.execute_tests()
        state["test_output"] = result
        record_test_result(bool(result.get("passed", False)))
        state["logs"].append(f"Tests executed: passed={result['passed']}")
    except Exception as e:
        state["test_output"] = {"passed": False, "stdout": "", "stderr": str(e)}
        record_test_result(False)
        state["logs"].append(f"Test execution error: {str(e)}")

    return state

@observe_node("reviewer")
def reviewer_node(state: AgentState) -> AgentState:
    """Person 2: Review code for issues"""
    if not state.get("code_patch"):
        state["logs"].append("No code patch available for review")
        return state

    test_output = state.get("test_output")
    if not test_output:
        state["logs"].append("No test output available for review")
        return state

    failure_summary = analyze_failure(test_output)
    # The real reviewer helper returns a plain string, not a ReviewResult model.
    # Since AgentState has no dedicated failure_summary field, repurpose `review`
    # to hold the raw failure summary instead of inventing a fake ReviewResult object.
    state["review"] = failure_summary
    state["logs"].append(f"Failure summary captured: {failure_summary[:180]}")
    return state


@observe_node("healer")
async def healer_node(state: AgentState) -> AgentState:
    """Person 2: Suggest fixes for failed tests"""
    if not state.get("code_patch"):
        state["logs"].append("No code patch available for healing")
        return state

    test_output = state.get("test_output")
    if test_output and test_output.get("passed", False):
        state["logs"].append("All tests passed, no healing needed")
        return state

    failure_summary = state.get("review")
    if isinstance(failure_summary, str):
        summary = failure_summary
    else:
        summary = "No structured failure summary available."

    state["logs"].append("Analyzing test failures for fixes")
    HEALING_CYCLES.inc()

    try:
        corrected_patch = await heal(
            state["code_patch"],
            summary,
            state.get("iteration", 0),
            gateway=gateway,
        )
        state["code_patch"] = corrected_patch
        state["iteration"] = state.get("iteration", 0) + 1
        state["logs"].append("Healer generated a corrected patch")
    except Exception as exc:
        state["logs"].append(f"Healing stopped: {exc}")
        # Only increment iteration on actual heal attempt, not on exception
        if state.get("code_patch"):
            state["iteration"] = state.get("iteration", 0) + 1

    return state

@observe_node("github_pr")
async def github_pr_node(state: AgentState) -> AgentState:
    """Person 2: Push PR to GitHub"""
    if not state["code_patch"]:
        state["logs"].append("No code patch to push")
        return state
    try:
        state["pr_url"] = await GitHubOps().create_pull_request(
            title=f"Automated fix: {state['prompt'][:72]}",
            body="Generated and verified by the DaedalusOS agent workflow.",
            patch=state["code_patch"],
            repository=state.get("target_repo"),
            base_branch=state.get("base_branch", "main"),
        )
        state["logs"].append(f"PR created in {state.get('target_repo')}: {state['pr_url']}")
    except Exception as exc:
        state["logs"].append(f"PR creation skipped: {exc}")
    return state

# 1. Initialize Graph with shared AgentState
workflow = StateGraph(AgentState)

# 2. Add Producer & Verifier Nodes
workflow.add_node("planner", planner_node)         # Person 1
workflow.add_node("researcher", researcher_node)   # Person 1
workflow.add_node("developer", developer_node)     # Person 1
workflow.add_node("tester", tester_node)           # Person 2
workflow.add_node("reviewer", reviewer_node)       # Person 2
workflow.add_node("healer", healer_node)           # Person 2
workflow.add_node("github_pr", github_pr_node)     # Person 2

# 3. Define Execution Edges
workflow.set_entry_point("planner")
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "developer")
workflow.add_edge("developer", "tester")

# 4. Define Conditional Edge (The Autonomous Self-Healing Branch)
def check_test_results(state: AgentState) -> str:
    if state["test_output"] and state["test_output"].get("passed", False):
        return "github_pr"
    if state["iteration"] >= state["max_iterations"]:
        return END  # Safety cutoff
    return "reviewer"

workflow.add_conditional_edges(
    "tester",
    check_test_results,
    {
        "github_pr": "github_pr",
        "reviewer": "reviewer",
        END: END
    }
)

workflow.add_edge("reviewer", "healer")
workflow.add_edge("healer", "tester")  # Cycles back to re-run pytest
workflow.add_edge("github_pr", END)

# 5. Compile Runnable Engine
daedalus_app = workflow.compile()


if __name__ == "__main__":
    import asyncio

    async def run_demo():
        fake_gateway = LLMGateway()
        state = {
            "prompt": "Fix the failing calculator output",
            "plan": None,
            "code_patch": None,
            "test_output": {
                "passed": False,
                "stdout": """\n=================================== FAILURES ====================================\n    test_calculator.py::test_add\n    def test_add():\n>       assert add(2, 3) == 5\nE       assert 1 == 5\n""",
                "stderr": "",
            },
            "review": None,
            "iteration": 0,
            "max_iterations": 3,
            "pr_url": None,
            "logs": [],
        }

        state["review"] = analyze_failure(state["test_output"])
        print(state["review"])

        state["code_patch"] = type("Patch", (), {"summary": "Broken patch", "files": []})()
        try:
            updated = await heal(state["code_patch"], state["review"], state["iteration"], gateway=fake_gateway)
            print(updated.summary)
        except Exception as exc:
            print(type(exc).__name__, exc)

    asyncio.run(run_demo())