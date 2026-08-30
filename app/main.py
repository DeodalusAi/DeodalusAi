import asyncio
import json
from typing import Any

from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="DaedalusOS Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory queue for streaming real-time events to the UI
event_queue: asyncio.Queue = asyncio.Queue()

class RunRequest(BaseModel):
    prompt: str


async def _emit_event(step: str, status: str, message: str | None = None, **extra: Any):
    payload: dict[str, Any] = {"step": step, "status": status}
    if message is not None:
        payload["message"] = message
    payload.update(extra)
    await event_queue.put(payload)


async def _run_real_workflow(prompt_text: str):
    """Run the actual graph workflow and emit the live state updates as SSE events."""
    try:
        from app.graph import daedalus_engine
    except Exception as exc:  # pragma: no cover - fallback if graph import fails
        await _emit_event("ERROR", "error", f"Workflow import failed: {exc}")
        return

    initial_state = {
        "prompt": prompt_text,
        "plan": None,
        "code_patch": None,
        "test_output": None,
        "review": None,
        "iteration": 0,
        "max_iterations": 3,
        "pr_url": None,
        "logs": [],
    }

    latest_state = initial_state
    try:
        async for state_update in daedalus_engine.astream(initial_state):
            for node_name, partial_state in state_update.items():
                latest_state = partial_state
                if node_name == "reviewer":
                    review = partial_state.get("review")
                    status = "analyzed" if review else "skipped"
                    await _emit_event(
                        node_name,
                        status,
                        "Failure summary analyzed" if review else "No failure summary produced",
                        review=review,
                    )
                elif node_name == "tester":
                    test_output = partial_state.get("test_output") or {}
                    await _emit_event(
                        node_name,
                        "passed" if test_output.get("passed") else "failed",
                        "Test execution completed",
                        test_output=test_output,
                    )
                elif node_name == "github_pr":
                    await _emit_event(
                        node_name,
                        "done" if partial_state.get("pr_url") else "skipped",
                        "PR workflow complete",
                        pr_url=partial_state.get("pr_url"),
                    )
                else:
                    await _emit_event(node_name, "done", f"{node_name} node completed")

        final_test_output = latest_state.get("test_output") or {}
        success = bool(final_test_output.get("passed")) or bool(latest_state.get("pr_url"))
        await _emit_event(
            "COMPLETE",
            "done" if success else "failed",
            "Workflow complete" if success else "Workflow ended without success criteria",
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await _emit_event("ERROR", "error", str(exc))


@app.post("/api/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Triggers the agent workflow in the background and sends events to the UI."""
    background_tasks.add_task(_run_real_workflow, req.prompt)
    return {"status": "started", "prompt": req.prompt}

@app.get("/api/events")
async def stream_events():
    """Streams live events to the frontend via HTTP Server-Sent Events (SSE)."""
    async def event_generator():
        while True:
            data = await event_queue.get()
            yield f"data: {json.dumps(data)}\n\n"
            if data.get("step") == "COMPLETE":
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Serve the static UI dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)