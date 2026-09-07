from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse
from prometheus_client import make_asgi_app

from app.graph import daedalus_app
from app.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.schemas import AgentState

app = FastAPI(title="DaedalusOS Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_http(request, call_next):
    started = asyncio.get_running_loop().time()
    response = await call_next(request)
    path = request.url.path
    HTTP_LATENCY.labels(request.method, path).observe(asyncio.get_running_loop().time() - started)
    HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    return response

# Each workflow gets its own queue so concurrent runs cannot consume each other's events.
event_queues: dict[str, asyncio.Queue[Dict[str, Any]]] = {}

app.mount("/metrics", make_asgi_app())


class RunRequest(BaseModel):
    prompt: str
    max_iterations: int = 3
    target_repo: str | None = None
    base_branch: str = "main"

    @field_validator("target_repo")
    @classmethod
    def validate_target_repo(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().removesuffix(".git")
        if "://" in normalized or normalized.count("/") != 1:
            raise ValueError("target_repo must use owner/repository format")
        return normalized


def _build_event_payload(node_name: str, state_update: dict) -> dict:
    """Extract and format node-specific metadata for UI events to reduce complexity."""
    payload = {
        "step": node_name.upper(),
        "message": "",
        "iteration": state_update.get("iteration", 0),
    }
    
    # Get latest log message
    if "logs" in state_update and state_update["logs"]:
        payload["message"] = state_update["logs"][-1]
    else:
        payload["message"] = f"Executed node: {node_name}"
    
    # Build node-specific data payload
    payload["data"] = _get_node_data(node_name, state_update)
    
    return payload


def _get_node_data(node_name: str, state_update: dict) -> dict:
    """Extract node-specific data to further reduce complexity."""
    if node_name == "planner" and "plan" in state_update and state_update["plan"]:
        return {
            "epic_title": state_update["plan"].epic_title,
            "task_count": len(state_update["plan"].tasks),
        }
    elif node_name == "developer" and "code_patch" in state_update and state_update["code_patch"]:
        return {
            "summary": state_update["code_patch"].summary,
            "file_count": len(state_update["code_patch"].files),
            "files": [
                {"path": file_patch.path, "content": file_patch.content}
                for file_patch in state_update["code_patch"].files
            ],
        }
    elif node_name == "tester" and "test_output" in state_update and state_update["test_output"]:
        return {
            "passed": state_update["test_output"].get("passed", False),
            "stdout": state_update["test_output"].get("stdout", ""),
        }
    elif node_name == "reviewer" and "review" in state_update and state_update["review"]:
        review = state_update["review"]
        return {"root_cause": review if isinstance(review, str) else str(review)}
    elif node_name == "healer" and "code_patch" in state_update and state_update["code_patch"]:
        return {
            "summary": state_update["code_patch"].summary,
            "file_count": len(state_update["code_patch"].files),
            "files": [
                {"path": file_patch.path, "content": file_patch.content}
                for file_patch in state_update["code_patch"].files
            ],
        }
    elif node_name == "github_pr" and "pr_url" in state_update and state_update["pr_url"]:
        return {"pr_url": state_update["pr_url"]}
    
    return {}


async def run_agent_workflow(run_id: str, prompt: str, max_iterations: int = 3, target_repo: str | None = None, base_branch: str = "main") -> None:
    """Executes the compiled LangGraph pipeline and feeds updates into the event queue."""
    # Validate max_iterations bounds
    safe_iterations = max(1, min(max_iterations, 10))
    
    initial_state: AgentState = {
        "prompt": prompt,
        "plan": None,
        "code_patch": None,
        "test_output": None,
        "review": None,
        "iteration": 0,
        "max_iterations": safe_iterations,
        "pr_url": None,
        "target_repo": target_repo or os.getenv("GITHUB_REPO"),
        "base_branch": base_branch,
        "logs": [],
    }

    event_queue = event_queues[run_id]
    final_state: dict[str, Any] = {}
    await event_queue.put({
        "step": "INITIALIZED",
        "message": f"Engine initialized for requirement: '{prompt}'",
        "data": {}
    })

    try:
        async for output in daedalus_app.astream(initial_state):
            for node_name, state_update in output.items():
                final_state.update(state_update)
                payload = _build_event_payload(node_name, state_update)
                await event_queue.put(payload)

        tests_passed = bool((final_state.get("test_output") or {}).get("passed"))
        pr_url = final_state.get("pr_url")
        if tests_passed and pr_url:
            await event_queue.put({
                "step": "COMPLETE",
                "message": "Workflow completed and delivery succeeded.",
                "data": {"pr_url": pr_url},
            })
        else:
            message = (
                "Workflow stopped before delivery because generated tests did not pass."
                if not tests_passed
                else "Workflow verified successfully but GitHub delivery failed."
            )
            await event_queue.put({
                "step": "ERROR",
                "message": message,
                "data": {"tests_passed": tests_passed, "pr_url": pr_url},
            })

    except Exception as exc:
        await event_queue.put({
            "step": "ERROR",
            "message": f"Pipeline execution failed: {str(exc)}",
            "data": {"error": str(exc)}
        })


@app.post("/api/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """Starts the LangGraph execution in a non-blocking background task."""
    run_id = uuid.uuid4().hex
    event_queues[run_id] = asyncio.Queue()
    background_tasks.add_task(run_agent_workflow, run_id, req.prompt, req.max_iterations, req.target_repo, req.base_branch)
    return {"status": "started", "prompt": req.prompt, "run_id": run_id, "target_repo": req.target_repo or os.getenv("GITHUB_REPO", "")}


@app.get("/api/events")
async def stream_events(run_id: str) -> StreamingResponse:
    """Streams server-sent events (SSE) continuously to the browser UI."""
    event_queue = event_queues.get(run_id)
    if event_queue is None:
        return StreamingResponse(iter(["data: {\"step\":\"ERROR\",\"message\":\"Unknown run_id\"}\n\n"]), media_type="text/event-stream", status_code=404)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                data = await event_queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("step") in {"COMPLETE", "ERROR"}:
                    break
        finally:
            event_queues.pop(run_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# Mount static files and serve the single-file UI
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_index() -> str:
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return "<h1>Static index.html not found in /static directory</h1>"
    return index_file.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)