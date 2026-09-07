#  DaedalusOS — Autonomous AI Software Engineering Team

DaedalusOS is an autonomous multi-agent engineering platform that translates high-level product requirements into planned, researched, coded, tested, and self-healed implementations delivered directly as GitHub Pull Requests.

##  Architecture
- **Orchestration**: LangGraph cyclic state machine
- **LLM Gateway**: Dual-provider resilient gateway (Google Gemini 2.0 Flash ↔ Groq Llama-3.3-70B)
- **Verification**: Subprocess sandbox with real `pytest` execution and auto-healing error recovery
- **Real-Time Streaming**: Server-Sent Events (SSE) live telemetry feed

## Fast Agent Context

The pipeline uses three context layers:

- **CAG**: the gateway keeps validated LLM responses in a bounded TTL cache.
- **RAG**: the researcher retrieves architecture guidance from Qdrant and caches the formatted context.
- **MAG**: retrieved context is persisted in `MAG_MEMORY_PATH` (SQLite), so repeated requirements can skip Qdrant work after a restart.

For local development, assign the developer to Qwen with `DEVELOPER_MODEL=local:qwen2.5:7b`.
LoRA adapters are loaded by Ollama when you build a custom model from a Modelfile; set
`LOCAL_LLM_MODEL` to that custom model name. The gateway does not upload adapter files or
silently apply an incompatible adapter at runtime.

##  Quickstart

1. **Clone & Setup Environment:**
   ```bash
   git clone <repo-url>
   cd daedalus-os
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt