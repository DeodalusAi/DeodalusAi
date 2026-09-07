import asyncio
from collections import OrderedDict
from unittest.mock import Mock

from app.producer.gateway import GenerationUnavailable, LLMGateway
from app.schemas import TaskBreakdown


def make_gateway(url):
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.gemini_client = None
    gateway.gemini_model = "gemini-model"
    gateway.gemini_fallback_model = "gemini-fallback"
    gateway.groq_key = None
    gateway.local_llm_url = url
    gateway.local_llm_key = "ollama"
    gateway.local_llm_model = "llama3.2"
    gateway.local_llm_timeout = 1
    gateway.local_llm_max_tokens = 12000
    gateway.groq_model = "groq-model"
    gateway.groq_max_tokens = 12000
    gateway.cache_ttl = 900
    gateway.cache_size = 64
    gateway._cache = OrderedDict()
    return gateway


def test_local_llm_is_used_when_groq_is_unavailable(monkeypatch):
    gateway = make_gateway("http://localhost:11434/api/chat")

    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "choices": [{"message": {"content": '{"epic_title":"Local","architecture_overview":"Fast","tasks":[]}'}}]
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("plan this", TaskBreakdown))

    assert result.epic_title == "Local"


def test_explicit_local_model_routes_directly_to_qwen(monkeypatch):
    gateway = make_gateway("http://localhost:11434/v1/chat/completions")
    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "choices": [{"message": {"content": '{"epic_title":"Qwen","architecture_overview":"Local","tasks":[]}'}}]
    }
    captured = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("implement this", TaskBreakdown, model="local:qwen2.5:7b"))

    assert result.epic_title == "Qwen"
    assert captured["json"]["model"] == "qwen2.5:7b"


def test_local_model_failure_falls_back_to_groq(monkeypatch):
    gateway = make_gateway("http://localhost:11434/v1/chat/completions")
    gateway.groq_key = "groq-key"
    gateway.groq_url = "https://groq.test/chat/completions"

    async def fail_local(*args, **kwargs):
        raise GenerationUnavailable("Qwen timed out")

    async def groq_result(*args, **kwargs):
        return TaskBreakdown(
            epic_title="Groq fallback",
            architecture_overview="Provider fallback",
            tasks=[],
        )

    monkeypatch.setattr(gateway, "_fallback_local", fail_local)
    monkeypatch.setattr(gateway, "_fallback_groq", groq_result)

    result = asyncio.run(
        gateway.generate_structured("plan this", TaskBreakdown, model="local:qwen2.5:7b")
    )

    assert result.epic_title == "Groq fallback"


def test_groq_failure_falls_back_to_gemini_for_healing(monkeypatch):
    gateway = make_gateway("http://localhost:11434/v1/chat/completions")
    gateway.groq_key = "groq-key"
    gateway.groq_model = "groq-model"
    gateway.gemini_model = "gemini-model"
    gateway.gemini_timeout = 1
    gateway.gemini_client = Mock()
    gateway.gemini_client.models.generate_content.return_value = Mock(
        text='{"epic_title":"Gemini recovery","architecture_overview":"Fixed","tasks":[]}'
    )

    async def fail_groq(*args, **kwargs):
        return None

    monkeypatch.setattr(gateway, "_fallback_groq", fail_groq)

    result = asyncio.run(
        gateway.generate_structured("repair this", TaskBreakdown, model="groq:groq-model")
    )

    assert result.epic_title == "Gemini recovery"


def test_ollama_payload_and_response_format(monkeypatch):
    gateway = make_gateway("http://localhost:11434/api/chat")
    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "message": {"content": '{"epic_title":"Ollama","architecture_overview":"Local","tasks":[]}'},
    }
    captured = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("plan this", TaskBreakdown))

    assert result.epic_title == "Ollama"
    assert captured["json"]["format"] == "json"
    assert captured["json"]["options"]["num_predict"] == 12000
    assert "response_format" not in captured["json"]


def test_openai_compatible_payload_and_response_format(monkeypatch):
    gateway = make_gateway("http://localhost:11434/v1/chat/completions")
    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "choices": [{"message": {"content": '{"epic_title":"OpenAI","architecture_overview":"Local","tasks":[]}'}}]
    }
    captured = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("plan this", TaskBreakdown))

    assert result.epic_title == "OpenAI"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["max_tokens"] == 12000
    assert "format" not in captured["json"]


def test_local_llm_accepts_ollama_response_field(monkeypatch):
    gateway = make_gateway("http://localhost:11434/api/generate")
    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "response": '{"epic_title":"Generate","architecture_overview":"Local","tasks":[]}'
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("plan this", TaskBreakdown))

    assert result.epic_title == "Generate"


def test_local_llm_normalizes_string_tasks(monkeypatch):
    gateway = make_gateway("http://localhost:11434/v1/chat/completions")
    response = Mock()
    response.is_error = False
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"epic_title":"Small model","architecture_overview":"Local","tasks":[{"id":1,"title":"Add endpoint","description":2,"dependencies":[1]}]}'
            }
        }]
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr("app.producer.gateway.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = asyncio.run(gateway.generate_structured("plan this", TaskBreakdown))

    assert result.tasks[0].title == "Add endpoint"
    assert result.tasks[0].dependencies == ["1"]
