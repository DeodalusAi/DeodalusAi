from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field
from typing import Dict, Optional, TypedDict

# --- Verifier & Auto-Healer Contract ---
class ReviewResult(BaseModel):
    approved: bool
    status: str = Field(description="'APPROVED' or 'REJECTED'")
    root_cause: Optional[str] = Field(default=None, description="Detailed explanation of failure if rejected")
    suggested_fix: Optional[str] = Field(default=None, description="Instructions on how to patch the bug")


# --- LangGraph Shared State (State Graph Boundary) ---
class AgentState(TypedDict):
    prompt: str
    plan: Optional[TaskBreakdown]
    code_patch: Optional[CodePatch]
    test_output: Optional[Dict[str, str]]
    review: Optional[str]  # Changed from ReviewResult to str (holds failure summary from analyze_failure)
    iteration: int
    max_iterations: int
    pr_url: Optional[str]
    logs: List[str]
    research_context: Optional[str] = None  # Added to track research results from researcher node

class TaskItem(BaseModel):
    id: str
    title: str
    description: str
    dependencies: List[str] = Field(default_factory=list)


class TaskBreakdown(BaseModel):
    epic_title: str
    architecture_overview: str
    tasks: List[TaskItem] = Field(default_factory=list)


class FilePatch(BaseModel):
    path: str
    content: str


class CodePatch(BaseModel):
    summary: str
    files: List[FilePatch] = Field(default_factory=list)


__all__ = [
    "ReviewResult",
    "AgentState",
    "TaskItem",
    "TaskBreakdown",
    "FilePatch",
    "CodePatch",
]
