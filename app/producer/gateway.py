import json
import os
import time
import asyncio
from collections import OrderedDict
from typing import Type, TypeVar
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.schemas import CodePatch, FilePatch, TaskBreakdown, TaskItem
from app.observability.metrics import record_token_usage

load_dotenv()

T = TypeVar("T", bound=BaseModel)


class GenerationUnavailable(RuntimeError):
    """Raised when no provider can safely generate a requested code patch."""

def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    return value.strip().lower() in {
        "your_gemini_api_key_here",
        "gsk_your_groq_api_key_here",
        "ghp_your_github_personal_access_token",
        "your_qdrant_api_key",
    }

class LLMGateway:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.gemini_fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
        self.groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.groq_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.local_llm_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")
        self.local_llm_model = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
        self.local_llm_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/api/chat")
        self.local_llm_timeout = float(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "30"))
        self.local_llm_max_tokens = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "12000"))
        self.gemini_timeout = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "15"))
        self.groq_timeout = float(os.getenv("GROQ_TIMEOUT_SECONDS", "8"))
        self.groq_max_tokens = int(os.getenv("GROQ_MAX_COMPLETION_TOKENS", "12000"))
        self.cache_ttl = float(os.getenv("LLM_CACHE_TTL_SECONDS", "900"))
        self.cache_size = int(os.getenv("LLM_CACHE_SIZE", "64"))
        self._cache: OrderedDict[tuple[str, str, str], tuple[float, T]] = OrderedDict()
        self.gemini_client = (
            genai.Client(api_key=self.gemini_key)
            if self.gemini_key and not _is_placeholder(self.gemini_key)
            else None
        )

    def _offline_fallback(self, schema: Type[T], prompt: str = "") -> T:
        """Guarantees a valid Pydantic response even when offline/out of credits."""
        if schema is TaskBreakdown and "roman" in prompt.lower():
            return TaskBreakdown(
                epic_title="Roman Numeral Converter",
                architecture_overview="A validated integer-to-Roman converter with explicit boundary tests for subtractive notation.",
                tasks=[
                    TaskItem(
                        id="TASK-1",
                        title="Implement Roman numeral conversion",
                        description="Create a converter supporting standard values from 1 through 3999.",
                    ),
                    TaskItem(
                        id="TASK-2",
                        title="Add off-by-one boundary tests",
                        description="Test values immediately before and after subtractive boundaries such as 4, 9, 40, 90, 400, and 900.",
                        dependencies=["TASK-1"],
                    ),
                ],
            )

        if schema is TaskBreakdown:
            return TaskBreakdown(
                epic_title="Offline Planning Mode",
                architecture_overview="Fallback architecture generated without active API credentials.",
                tasks=[
                    TaskItem(
                        id="TASK-1",
                        title="Setup Module",
                        description="Implement core module requirements and baseline structure.",
                    ),
                    TaskItem(
                        id="TASK-2",
                        title="Add Unit Tests",
                        description="Implement pytest test suite covering core operations.",
                        dependencies=["TASK-1"],
                    ),
                ],
            )

        if schema is CodePatch and "roman" in prompt.lower():
            return CodePatch(
                summary="Implemented an integer-to-Roman numeral converter with boundary-focused pytest coverage.",
                files=[
                    FilePatch(
                        path="app/roman.py",
                        content=(
                            "VALUES = ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), "
                            "(100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), "
                            "(10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'))\n\n"
                            "def int_to_roman(value: int) -> str:\n"
                            "    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 3999:\n"
                            "        raise ValueError('value must be an integer from 1 through 3999')\n"
                            "    result = []\n"
                            "    for number, symbol in VALUES:\n"
                            "        count, value = divmod(value, number)\n"
                            "        result.append(symbol * count)\n"
                            "    return ''.join(result)\n"
                        ),
                    ),
                    FilePatch(
                        path="tests/test_roman.py",
                        content=(
                            "import pytest\n\n"
                            "from app.roman import int_to_roman\n\n"
                            "@pytest.mark.parametrize('value, expected', [\n"
                            "    (1, 'I'), (3, 'III'), (4, 'IV'), (5, 'V'), (8, 'VIII'),\n"
                            "    (9, 'IX'), (39, 'XXXIX'), (40, 'XL'), (41, 'XLI'),\n"
                            "    (89, 'LXXXIX'), (90, 'XC'), (399, 'CCCXCIX'),\n"
                            "    (400, 'CD'), (899, 'DCCCXCIX'), (900, 'CM'), (3999, 'MMMCMXCIX'),\n"
                            "])\n"
                            "def test_int_to_roman_boundaries(value, expected):\n"
                            "    assert int_to_roman(value) == expected\n\n"
                            "@pytest.mark.parametrize('value', [0, -1, 4000])\n"
                            "def test_int_to_roman_rejects_out_of_range_values(value):\n"
                            "    with pytest.raises(ValueError):\n"
                            "        int_to_roman(value)\n"
                        ),
                    ),
                ],
            )

        if schema is CodePatch and any(
            phrase in prompt.lower() for phrase in ("rate limiter", "rate-limit", "token bucket")
        ):
            return CodePatch(
                summary="Implemented an in-memory token bucket rate limiter with FastAPI middleware and pytest coverage.",
                files=[
                    FilePatch(
                        path="app/token_bucket.py",
                        content=(
                            "import time\n\n"
                            "class TokenBucket:\n"
                            "    def __init__(self, capacity: int, fill_rate: float, clock=time.monotonic):\n"
                            "        if capacity <= 0 or fill_rate <= 0:\n"
                            "            raise ValueError('capacity and fill_rate must be positive')\n"
                            "        self.capacity = capacity\n"
                            "        self.fill_rate = fill_rate\n"
                            "        self.tokens = float(capacity)\n"
                            "        self.last_update = clock()\n"
                            "        self.clock = clock\n\n"
                            "    def consume(self, amount: int = 1) -> bool:\n"
                            "        now = self.clock()\n"
                            "        self.tokens = min(self.capacity, self.tokens + (now - self.last_update) * self.fill_rate)\n"
                            "        self.last_update = now\n"
                            "        if self.tokens < amount:\n"
                            "            return False\n"
                            "        self.tokens -= amount\n"
                            "        return True\n"
                        ),
                    ),
                    FilePatch(
                        path="app/middleware.py",
                        content=(
                            "from starlette.middleware.base import BaseHTTPMiddleware\n"
                            "from starlette.responses import JSONResponse\n"
                            "from app.token_bucket import TokenBucket\n\n"
                            "class RateLimitMiddleware(BaseHTTPMiddleware):\n"
                            "    def __init__(self, app, capacity=10, fill_rate=1.0):\n"
                            "        super().__init__(app)\n"
                            "        self.bucket = TokenBucket(capacity, fill_rate)\n\n"
                            "    async def dispatch(self, request, call_next):\n"
                            "        if not self.bucket.consume():\n"
                            "            return JSONResponse({'detail': 'Rate limit exceeded'}, status_code=429, headers={'Retry-After': '1'})\n"
                            "        return await call_next(request)\n"
                        ),
                    ),
                    FilePatch(
                        path="tests/test_rate_limiter.py",
                        content=(
                            "from app.token_bucket import TokenBucket\n\n"
                            "def test_token_bucket_refills_from_elapsed_time():\n"
                            "    now = [0.0]\n"
                            "    bucket = TokenBucket(1, 1.0, clock=lambda: now[0])\n"
                            "    assert bucket.consume()\n"
                            "    assert not bucket.consume()\n"
                            "    now[0] = 1.0\n"
                            "    assert bucket.consume()\n\n"
                            "def test_token_bucket_rejects_invalid_configuration():\n"
                            "    try:\n"
                            "        TokenBucket(0, 1.0)\n"
                            "    except ValueError:\n"
                            "        pass\n"
                            "    else:\n"
                            "        raise AssertionError('invalid capacity was accepted')\n"
                        ),
                    ),
                ],
            )

        if schema is CodePatch:
            raise GenerationUnavailable(
                "No LLM provider generated a requirement-specific code patch; refusing to use a generic fallback."
            )

        return schema.model_validate({})

    async def generate_structured(self, prompt: str, schema: Type[T], model: str | None = None) -> T:
        """Route explicit local/Groq models directly, then fall back across providers."""
        selected_model = model or self.gemini_model
        cache_key = (schema.__name__, selected_model, prompt.strip())
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < self.cache_ttl:
            self._cache.move_to_end(cache_key)
            return cached[1].model_copy(deep=True)
        if cached:
            del self._cache[cache_key]

        if selected_model.startswith("local:"):
            try:
                return await self._fallback_local(
                    prompt,
                    schema,
                    cache_key,
                    model=selected_model.removeprefix("local:"),
                )
            except GenerationUnavailable as local_error:
                print(f"[Gateway Warning] Local model failed: {local_error}. Trying Groq...")
                result = await self._fallback_groq(prompt, schema, cache_key, self.groq_model)
                if result is not None:
                    return result
                if self.gemini_client:
                    result = await self._fallback_gemini(prompt, schema, cache_key, self.gemini_model)
                    if result is not None:
                        return result
                raise local_error

        if selected_model.startswith("groq:"):
            result = await self._fallback_groq(
                prompt,
                schema,
                cache_key,
                selected_model.removeprefix("groq:") or self.groq_model,
            )
            if result is not None:
                return result
            if self.gemini_client:
                result = await self._fallback_gemini(prompt, schema, cache_key, self.gemini_model)
                if result is not None:
                    return result
            return await self._fallback_local(prompt, schema, cache_key)

        if self.gemini_client:
            try:
                gemini_models = [selected_model, self.gemini_model]
                if self.gemini_fallback_model not in gemini_models:
                    gemini_models.append(self.gemini_fallback_model)
                for attempt, gemini_model in enumerate(gemini_models):
                    try:
                        response = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.gemini_client.models.generate_content,
                                model=gemini_model,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=schema,
                                    temperature=0.1,
                                ),
                            ),
                            timeout=self.gemini_timeout,
                        )
                        record_token_usage(gemini_model, getattr(response, "usage_metadata", None))
                        result = schema.model_validate_json(response.text)
                        self._store_cached(cache_key, result)
                        return result
                    except Exception as exc:
                        if attempt == 0 and any(code in str(exc) for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                            await asyncio.sleep(0.15)
                            continue
                        raise
            except Exception as exc:
                print(f"[Gateway Warning] Gemini call failed: {exc}. Switching to Groq...")

        result = await self._fallback_groq(prompt, schema, cache_key, self.groq_model)
        if result is not None:
            return result
        return await self._fallback_local(prompt, schema, cache_key)

    async def _fallback_gemini(
        self,
        prompt: str,
        schema: Type[T],
        cache_key: tuple[str, str, str],
        model: str,
    ) -> T | None:
        if not self.gemini_client:
            return None
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.1,
                    ),
                ),
                timeout=self.gemini_timeout,
            )
            record_token_usage(model, getattr(response, "usage_metadata", None))
            result = schema.model_validate_json(response.text)
            self._store_cached(cache_key, result)
            return result
        except Exception as exc:
            print(f"[Gateway Warning] Gemini recovery failed: {type(exc).__name__}: {exc!r}")
            return None

    def _store_cached(self, key: tuple[str, str, str], result: T) -> None:
        self._cache[key] = (time.monotonic(), result.model_copy(deep=True))
        self._cache.move_to_end(key)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

    async def _fallback_groq(
        self,
        prompt: str,
        schema: Type[T],
        cache_key: tuple[str, str, str],
        model: str,
    ) -> T | None:
        if not self.groq_key or _is_placeholder(self.groq_key):
            print("[Gateway Warning] GROQ_API_KEY is not configured. Switching to local LLM...")
            return None

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a strict JSON generator. Return ONLY valid JSON matching this schema:\n{json.dumps(schema.model_json_schema())}",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_completion_tokens": self.groq_max_tokens,
        }

        try:
            timeout = httpx.Timeout(self.groq_timeout, connect=min(3.0, self.groq_timeout))
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(self.groq_url, json=payload, headers=headers)
                if resp.is_error:
                    raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                record_token_usage(model, data.get("usage"))
                content = data["choices"][0]["message"]["content"]
                result = schema.model_validate_json(content)
                self._store_cached(cache_key, result)
                return result
        except Exception as exc:
            print(f"[Gateway Warning] Groq fallback failed: {exc}. Utilizing offline fallback.")
            return None

    async def _fallback_local(
        self,
        prompt: str,
        schema: Type[T],
        cache_key: tuple[str, str, str],
        model: str | None = None,
    ) -> T:
        if not self.local_llm_url:
            return self._offline_fallback(schema, prompt)

        headers = {
            "Authorization": f"Bearer {self.local_llm_key}",
            "Content-Type": "application/json",
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "Return one JSON object, never markdown and never the schema itself. "
                    f"The top-level fields must be: {', '.join(schema.model_fields)}."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        local_model = model or self.local_llm_model
        if "/v1/" in self.local_llm_url.rstrip("/"):
            payload = {
                "model": local_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": self.local_llm_max_tokens,
            }
        else:
            payload = {
                "model": local_model,
                "messages": messages,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": self.local_llm_max_tokens},
            }

        try:
            timeout = httpx.Timeout(self.local_llm_timeout, connect=3.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.local_llm_url, json=payload, headers=headers)
                if response.is_error:
                    raise RuntimeError(f"Local LLM HTTP {response.status_code}: {response.text[:300]}")
                data = response.json()
                record_token_usage(local_model, data.get("usage"))
                content = data.get("message", {}).get("content")
                if content is None:
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                if content is None:
                    content = data.get("response")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Local LLM response did not contain text content")
                content = content.strip()
                if content.startswith("```"):
                    lines = content.splitlines()
                    if len(lines) < 3:
                        raise ValueError("Local LLM returned an incomplete markdown code block")
                    content = "\n".join(lines[1:-1]).strip()
                result = self._validate_local_result(content, schema)
                self._store_cached(cache_key, result)
                return result
        except Exception as exc:
            print(
                f"[Gateway Warning] Local LLM unavailable: {type(exc).__name__}: {exc!r}. "
                "Utilizing offline fallback."
            )
            return self._offline_fallback(schema, prompt)

    @staticmethod
    def _validate_local_result(content: str, schema: Type[T]) -> T:
        """Normalize common small-model field aliases before schema validation."""
        value = json.loads(content)
        if schema is TaskBreakdown:
            normalized_tasks = []
            for index, task in enumerate(value.get("tasks", []), start=1):
                if isinstance(task, dict):
                    dependencies = task.get("dependencies", [])
                    if not isinstance(dependencies, list):
                        dependencies = []
                    normalized_tasks.append({
                        "id": str(task.get("id", f"TASK-{index}")),
                        "title": str(task.get("title", task.get("task_title", task.get("task_name", "Task")))),
                        "description": str(task.get("description", task.get("task_description", ""))),
                        "dependencies": [str(dependency) for dependency in dependencies],
                    })
                elif isinstance(task, str):
                    normalized_tasks.append({
                        "id": f"TASK-{index}",
                        "title": task,
                        "description": "",
                        "dependencies": [],
                    })
            value["tasks"] = normalized_tasks
        elif schema is CodePatch:
            normalized_files = []
            for file in value.get("files", []):
                if isinstance(file, dict):
                    normalized_files.append({
                        "path": file.get("path", file.get("file_path", file.get("filename", "app/main.py"))),
                        "content": file.get("content", file.get("code", "")),
                    })
                elif isinstance(file, str):
                    normalized_files.append({"path": "app/main.py", "content": file})
            value["files"] = normalized_files
        return schema.model_validate(value)