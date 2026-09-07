import asyncio
from collections import OrderedDict
from unittest.mock import Mock
import pytest

from app.producer.gateway import GenerationUnavailable, LLMGateway
from app.schemas import TaskBreakdown


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
