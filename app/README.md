# `app/`

The `app` package is the DaedalusOS runtime. It contains the HTTP API, the LangGraph workflow, shared Pydantic contracts, agent-producing components, verification components, and metrics.

## Runtime path

1. `main.py` accepts a requirement at `POST /api/run` and starts a background workflow.
2. `graph.py` runs planner, researcher, developer, tester, reviewer, healer, and GitHub delivery nodes.
3. Each workflow event is placed in a per-run queue and streamed through `GET /api/events`.
4. `schemas.py` keeps the state and structured LLM outputs consistent across node boundaries.

## Modules

| Path | Responsibility |
| --- | --- |
| `main.py` | FastAPI app, request validation, SSE events, static UI, and `/metrics` mount |
| `graph.py` | LangGraph state machine and retry/termination rules |
| `schemas.py` | `AgentState`, plans, file patches, and delivery models |
| `producer/` | Planning, research, memory, and structured LLM calls |
| `verifier/` | Sandbox tests, failure review, healing, and GitHub PR creation |
| `observability/` | Prometheus counters, histograms, and node timing decorators |

## Development

Run the service from the repository root so imports resolve correctly:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Keep generated file contracts in `schemas.py` stable: producer nodes create them, verifier nodes consume them, and the API serializes them into live events.