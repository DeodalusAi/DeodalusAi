#  DaedalusOS — Autonomous AI Software Engineering Team

DaedalusOS is an autonomous multi-agent engineering platform that translates high-level product requirements into planned, researched, coded, tested, and self-healed implementations delivered directly as GitHub Pull Requests.

##  Architecture
- **Orchestration**: LangGraph cyclic state machine
- **LLM Gateway**: Dual-provider resilient gateway (Google Gemini 2.0 Flash ↔ Groq Llama-3.3-70B)
- **Verification**: Subprocess sandbox with real `pytest` execution and auto-healing error recovery
- **Real-Time Streaming**: Server-Sent Events (SSE) live telemetry feed

##  Quickstart

1. **Clone & Setup Environment:**
   ```bash
   git clone <repo-url>
   cd daedalus-os
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt