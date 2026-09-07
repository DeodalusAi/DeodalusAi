# DaedalusOS

**Turn a product requirement into a tested GitHub pull request.**

DaedalusOS is an autonomous software-engineering workflow built for teams that want an AI agent to do more than generate a code snippet. Give it a requirement and it plans the work, retrieves relevant engineering guidance, writes code and tests, executes those tests in an isolated workspace, repairs failures, and can deliver the verified patch as a GitHub pull request.

The repository name is `DeodulusAi`; the product and workflow are called **DaedalusOS**.

## Why it is interesting

- **A complete engineering loop:** planning, research, implementation, testing, review, healing, and delivery are connected in one workflow.
- **Evidence before delivery:** generated code is run through real `pytest` execution before a pull request is created.
- **Bounded autonomy:** healing has a maximum retry limit, and the workflow has a configurable iteration cap.
- **Provider resilience:** Gemini, Groq, and a local Ollama model can be used through one structured-output gateway.
- **Visible execution:** the FastAPI service streams each workflow step to the browser with Server-Sent Events.
- **Operationally observable:** Prometheus metrics and a ready-to-run Grafana dashboard expose node timing, test results, healing cycles, HTTP traffic, and token usage.

## How a run works

```text
Requirement
      -> Planner -> Researcher -> Developer -> Pytest sandbox
                                                         ^             |
                                                         |       failure review
                                                         +--------- Healer
                                                                              |
                                                         passing tests -> GitHub PR
```

The workflow is implemented as a cyclic LangGraph state machine. A failed test goes through the reviewer and healer before returning to the sandbox. The graph stops when tests pass, the configured iteration limit is reached, or delivery fails.

## Quickstart

### 1. Install

```bash
git clone <repo-url>
cd DeodulusAi
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

At minimum, configure one LLM provider. Add `GITHUB_TOKEN` and `GITHUB_REPO` only when you want the workflow to open pull requests. The gateway and researcher include local fallbacks, so the test suite can run without cloud credentials.

### 3. Start the API and UI

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>. The browser UI starts a run and follows its live event stream.

To call the API directly:

```bash
curl -X POST http://127.0.0.1:8000/api/run ^
   -H "Content-Type: application/json" ^
   -d "{\"prompt\":\"Add input validation to the calculator\",\"max_iterations\":3,\"target_repo\":\"owner/repository\"}"
```

The response contains a `run_id`. Subscribe to `GET /api/events?run_id=<run_id>` to receive newline-delimited SSE events. API metrics are available at `GET /metrics`.

## Provider configuration

The gateway chooses a provider from the model setting and falls back when a provider is unavailable:

| Setting | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Gemini structured generation and embeddings |
| `GROQ_API_KEY` | Groq-compatible fallback generation |
| `DEVELOPER_MODEL` | Model used to generate source and tests |
| `PLANNER_MODEL` | Model used to turn a prompt into tasks |
| `HEALER_MODEL` | Model used to repair a failing patch |
| `LOCAL_LLM_MODEL` | Ollama model name when using a `local:` model |
| `QDRANT_URL` / `QDRANT_API_KEY` | Optional hosted vector search |
| `MAG_MEMORY_PATH` | SQLite path for persistent research memory |
| `GITHUB_TOKEN` / `GITHUB_REPO` | Optional pull-request delivery |

For a local Ollama developer, use a model selector such as `DEVELOPER_MODEL=local:qwen2.5:7b`. LoRA adapters are managed by Ollama when building a custom model; DaedalusOS only receives the resulting model name.

## Run tests

```bash
python -m pytest -q
```

The tests cover the gateway, local-model routing, research and memory behavior, sandbox execution, and GitHub configuration. Generated code is tested separately inside `sandbox/workspace`.

## Monitoring

Start Prometheus and Grafana with Docker Compose:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000> (`admin` / `admin` for the local default)

See [infra/README.md](infra/README.md) for the scrape configuration and dashboard details.

## Repository map

- [app/README.md](app/README.md): API, graph, schemas, and application boundaries.
- [app/producer/README.md](app/producer/README.md): planning, research, memory, and model gateway.
- [app/verifier/README.md](app/verifier/README.md): testing, failure review, healing, and GitHub delivery.
- [app/observability/README.md](app/observability/README.md): Prometheus instrumentation.
- [tests/README.md](tests/README.md): test suite guide.
- [static/README.md](static/README.md): browser client guide.
- [sandbox/README.md](sandbox/README.md): generated-workspace and persistent-memory behavior.
- [infra/README.md](infra/README.md): Prometheus and Grafana setup.

## Project status

This is an active prototype for exploring autonomous software delivery. Treat generated patches as proposed changes: review the resulting pull request, keep credentials out of `.env` files committed to Git, and use a restricted GitHub token for demonstrations.