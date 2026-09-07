# Producer Agents

The producer side turns a natural-language requirement into a structured implementation patch. It is intentionally separated from verification so planning and generation can evolve without changing test execution or GitHub delivery.

## Pipeline

- `planner.py` converts the requirement into an epic, architecture overview, and ordered tasks.
- `researcher.py` retrieves relevant engineering guidance from Qdrant. Without hosted Qdrant credentials it uses an in-memory collection and deterministic local embeddings.
- `memory.py` persists retrieved context in SQLite so repeated requirements can reuse recent research after a restart.
- `developer.py` asks the gateway for complete source files and matching pytest files.
- `gateway.py` provides structured Pydantic responses, provider fallback, bounded caching, and the offline behavior used by local tests.

## Three context layers

- **CAG:** validated gateway responses are cached in memory with a TTL and size limit.
- **RAG:** the researcher searches seeded or hosted Qdrant documents and caches formatted context.
- **MAG:** `AgentMemory` stores research context in `MAG_MEMORY_PATH` (SQLite) with expiry.

## Model selectors

Use explicit prefixes when routing a role:

```env
PLANNER_MODEL=gemini-3.5-flash-lite
DEVELOPER_MODEL=local:qwen2.5:7b
HEALER_MODEL=groq:openai/gpt-oss-120b
```

The provider gateway expects structured JSON matching the Pydantic models in `app.schemas`. Keep prompts and generated output compatible with the installed dependency set.