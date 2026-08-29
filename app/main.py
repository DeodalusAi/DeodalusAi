import asyncio
import json
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

@app.post("/api/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Triggers the agent workflow in the background and sends events to the UI."""
    async def mock_agent_workflow(prompt_text: str):
        await event_queue.put({"step": "PLANNER", "message": f"Analyzing requirement: {prompt_text}"})
        await asyncio.sleep(1)
        await event_queue.put({"step": "DEVELOPER", "message": "Generating code and unit tests in sandbox..."})
        await asyncio.sleep(1)
        await event_queue.put({"step": "TESTER", "message": "Executing pytest suite: 1 Failed, 2 Passed."})
        await asyncio.sleep(1)
        await event_queue.put({"step": "HEALER", "message": "Auto-patching bug: updated auth token validation logic."})
        await asyncio.sleep(1)
        await event_queue.put({"step": "COMPLETE", "message": "All unit tests PASSED (3/3). GitHub PR Ready."})

    background_tasks.add_task(mock_agent_workflow, req.prompt)
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