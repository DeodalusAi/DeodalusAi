from app.producer.memory import AgentMemory


def test_agent_memory_persists_context(tmp_path):
    path = tmp_path / "memory.sqlite3"
    first = AgentMemory(str(path), ttl_seconds=60)
    first.remember("rate limiter architecture", "Use a token bucket and return HTTP 429.")

    second = AgentMemory(str(path), ttl_seconds=60)

    assert second.recall("rate limiter architecture") == "Use a token bucket and return HTTP 429."


def test_agent_memory_normalizes_query_whitespace(tmp_path):
    memory = AgentMemory(str(tmp_path / "memory.sqlite3"), ttl_seconds=60)
    memory.remember("  Roman   numeral converter ", "Use subtractive notation.")

    assert memory.recall("roman numeral converter") == "Use subtractive notation."