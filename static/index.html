from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.graph import daedalus_app
from app.schemas import AgentState

app = FastAPI(title="DaedalusOS Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory queue to broadcast live events to the SSE listener
event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()


class RunRequest(BaseModel):
    prompt: str
    max_iterations: int = 3


async def run_agent_workflow(prompt: str, max_iterations: int = 3) -> None:
    """Executes the compiled LangGraph pipeline and feeds updates into the event queue."""
    initial_state: AgentState = {
        "prompt": prompt,
        "plan": None,
        "code_patch": None,
        "test_output": None,
        "review": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "pr_url": None,
        "logs": [],
    }

    await event_queue.put({
        "step": "INITIALIZED",
        "message": f"Engine initialized for requirement: '{prompt}'",
        "data": {}
    })

    try:
        async for output in daedalus_app.astream(initial_state):
            for node_name, state_update in output.items():
                latest_log = ""
                if "logs" in state_update and state_update["logs"]:
                    latest_log = state_update["logs"][-1]

                # Format payload with node-specific metadata for the UI
                payload: Dict[str, Any] = {
                    "step": node_name.upper(),
                    "message": latest_log or f"Executed node: {node_name}",
                    "iteration": state_update.get("iteration", 0),
                }

                # Attach specific artifacts when available
                if node_name == "planner" and "plan" in state_update and state_update["plan"]:
                    payload["data"] = {
                        "epic_title": state_update["plan"].epic_title,
                        "task_count": len(state_update["plan"].tasks),
                    }
                elif node_name == "developer" and "code_patch" in state_update and state_update["code_patch"]:
                    payload["data"] = {
                        "summary": state_update["code_patch"].summary,
                        "file_count": len(state_update["code_patch"].files),
                    }
                elif node_name == "tester" and "test_output" in state_update and state_update["test_output"]:
                    payload["data"] = {
                        "passed": state_update["test_output"].get("passed", False),
                        "stdout": state_update["test_output"].get("stdout", ""),
                    }
                elif node_name == "reviewer" and "review" in state_update and state_update["review"]:
                    payload["data"] = {
                        "root_cause": state_update["review"].root_cause,
                    }
                elif node_name == "github_pr" and "pr_url" in state_update and state_update["pr_url"]:
                    payload["data"] = {
                        "pr_url": state_update["pr_url"],
                    }

                await event_queue.put(payload)

        await event_queue.put({
            "step": "COMPLETE",
            "message": "Workflow completed successfully.",
            "data": {}
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
    background_tasks.add_task(run_agent_workflow, req.prompt, req.max_iterations)
    return {"status": "started", "prompt": req.prompt}


@app.get("/api/events")
async def stream_events() -> StreamingResponse:
    """Streams server-sent events (SSE) continuously to the browser UI."""
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            data = await event_queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("step") in {"COMPLETE", "ERROR"}:
                break

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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)