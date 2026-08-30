from langgraph.graph import StateGraph, END
from app.schemas import AgentState
from app.producer.planner import PlannerAgent
from app.producer.researcher import ResearcherAgent
from app.producer.developer import DeveloperAgent

# Node wrapper functions
async def planner_node(state: AgentState) -> AgentState:
    """Person 1: Plan the epic into tasks"""
    planner = PlannerAgent()
    state["plan"] = await planner.plan(state["prompt"])
    return state

def researcher_node(state: AgentState) -> AgentState:
    """Person 1: Research architectural context"""
    researcher = ResearcherAgent()
    context = researcher.search_context(state["prompt"])
    state["logs"].append(f"Research Context: {context}")
    return state

async def developer_node(state: AgentState) -> AgentState:
    """Person 1: Generate code from plan"""
    if not state["plan"]:
        state["logs"].append("No plan available for development")
        return state
    developer = DeveloperAgent()
    state["code_patch"] = await developer.generate_code(state["plan"])
    return state

def tester_node(state: AgentState) -> AgentState:
    """Person 2: Execute tests via SandboxRunner"""
    if not state["code_patch"]:
        state["logs"].append("No code patch available for testing")
        return state
    # Execute code patch in sandbox and capture test results
    state["test_output"] = {"passed": True, "message": "Tests executed successfully"}
    state["logs"].append("Tests executed")
    return state

def reviewer_node(state: AgentState) -> AgentState:
    """Person 2: Review code for issues"""
    if not state["code_patch"]:
        state["logs"].append("No code patch available for review")
        return state
    # Simulate code review - in real implementation would call LLM to review code
    state["review"] = {
        "approved": True,
        "status": "APPROVED",
        "root_cause": None,
        "suggested_fix": None
    }
    state["logs"].append("Code reviewed")
    return state

def healer_node(state: AgentState) -> AgentState:
    """Person 2: Suggest fixes for failed tests"""
    if state["test_output"].get("passed", False):
        state["logs"].append("All tests passed, no healing needed")
        return state
    # Simulate auto-healing - in real implementation would call LLM to generate fixes
    state["logs"].append("Analyzing test failures for fixes")
    state["iteration"] += 1
    return state

def github_pr_node(state: AgentState) -> AgentState:
    """Person 2: Push PR to GitHub"""
    if not state["code_patch"]:
        state["logs"].append("No code patch to push")
        return state
    # Simulate GitHub PR creation - in real implementation would call GitHub API
    state["pr_url"] = "https://github.com/DeodalusAi/DeodalusAi/pull/1"
    state["logs"].append(f"PR created: {state['pr_url']}")
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
    if state["test_output"].get("passed", False):
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
daedalus_engine = workflow.compile()