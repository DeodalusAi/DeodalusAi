import asyncio
from collections import OrderedDict
from unittest.mock import Mock
import pytest

from app.producer.gateway import GenerationUnavailable, LLMGateway
from app.schemas import TaskBreakdown


def test_persistent_cache_reuses_validated_response(tmp_path):
    cache_path = str(tmp_path / "llm_cache.sqlite3")

    first = LLMGateway.__new__(LLMGateway)
    first.cache_ttl = 900
    first.cache_size = 64
    first._cache = OrderedDict()
    first._cache_connection = first._open_cache_at_path(cache_path)
    first._store_cached(
        ("TaskBreakdown", "gemini-test", "repeat this prompt"),
        TaskBreakdown(epic_title="Cached", architecture_overview="Stored", tasks=[]),
    )

    second = LLMGateway.__new__(LLMGateway)
    second.cache_ttl = 900
    second.cache_size = 64
    second._cache = OrderedDict()
    second._cache_connection = second._open_cache_at_path(cache_path)

    result = second._load_persisted(
        ("TaskBreakdown", "gemini-test", "repeat this prompt"), TaskBreakdown
    )

    assert result is not None
    assert result.epic_title == "Cached"


def test_offline_fallback_is_persisted_for_repeated_requests(tmp_path):
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.cache_ttl = 900
    gateway.cache_size = 64
    gateway._cache = OrderedDict()
    gateway._cache_connection = gateway._open_cache_at_path(str(tmp_path / "llm_cache.sqlite3"))

    result = gateway._store_offline_result(
        ("CodePatch", "offline", "Build a simple calculator application."),
        __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
        "Build a simple calculator application.",
    )

    cached = gateway._load_persisted(
        ("CodePatch", "offline", "Build a simple calculator application."),
        __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
    )

    assert cached is not None
    assert cached.model_dump() == result.model_dump()


def test_gemini_uses_vertex_adc_by_default(monkeypatch):
    calls = []

    class FakeGenai:
        @staticmethod
        def Client(**kwargs):
            calls.append(kwargs)
            return "adc-client"

    monkeypatch.setattr("app.producer.gateway.genai", FakeGenai)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    monkeypatch.delenv("GEMINI_AUTH_MODE", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    gateway = LLMGateway()

    assert gateway.gemini_client == "adc-client"
    assert calls == [{"vertexai": True, "project": "demo-project", "location": "global"}]


def test_gemini_honors_agent_model():
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.gemini_model = "global-model"
    gateway.gemini_fallback_model = "fallback-model"
    gateway.groq_model = "groq-model"
    gateway.groq_key = None
    gateway.cache_ttl = 900
    gateway.cache_size = 64
    gateway._cache = OrderedDict()
    gateway.gemini_timeout = 1

    response = Mock()
    response.text = '{"epic_title":"Test","architecture_overview":"Fast","tasks":[]}'
    gateway.gemini_client = Mock()
    gateway.gemini_client.models.generate_content.return_value = response

    result = asyncio.run(
        gateway.generate_structured(
            "plan this", TaskBreakdown, model="planner-fast-model"
        )
    )

    assert result.epic_title == "Test"
    assert gateway.gemini_client.models.generate_content.call_args.kwargs["model"] == "planner-fast-model"


def test_offline_fallback_preserves_roman_requirement():
    gateway = LLMGateway.__new__(LLMGateway)

    result = gateway._offline_fallback(
        __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
        "Write a Roman numeral converter function with intentional off-by-one edge-case tests in pytest.",
    )

    paths = {file_patch.path for file_patch in result.files}
    assert "app/roman.py" in paths
    assert "tests/test_roman.py" in paths
    assert "(40, 'XL')" in next(file.content for file in result.files if file.path == "tests/test_roman.py")


def test_offline_fallback_rejects_generic_code_patch():
    gateway = LLMGateway.__new__(LLMGateway)

    with pytest.raises(GenerationUnavailable):
        gateway._offline_fallback(
            __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
            "Build a temperature converter",
        )


def test_offline_fallback_supports_rate_limiter_requirement():
    gateway = LLMGateway.__new__(LLMGateway)

    result = gateway._offline_fallback(
        __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
        "Build an in-memory token bucket rate limiter with FastAPI middleware and pytest tests.",
    )

    paths = {file_patch.path for file_patch in result.files}
    assert "app/token_bucket.py" in paths
    assert "app/middleware.py" in paths
    assert "tests/test_rate_limiter.py" in paths


def test_offline_fallback_supports_calculator_requirement():
    gateway = LLMGateway.__new__(LLMGateway)

    result = gateway._offline_fallback(
        __import__("app.schemas", fromlist=["CodePatch"]).CodePatch,
        "Build a simple calculator application.",
    )

    paths = {file_patch.path for file_patch in result.files}
    assert "app/calculator.py" in paths
    assert "tests/test_calculator.py" in paths
