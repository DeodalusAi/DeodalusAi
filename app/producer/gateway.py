import json
import os
from typing import Type, TypeVar
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from app.schemas import CodePatch, FilePatch, TaskBreakdown, TaskItem

load_dotenv()

T = TypeVar("T", bound=BaseModel)

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
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.gemini_client = (
            genai.Client(api_key=self.gemini_key)
            if self.gemini_key and not _is_placeholder(self.gemini_key)
            else None
        )

    def _offline_fallback(self, schema: Type[T]) -> T:
        """Guarantees a valid Pydantic response even when offline/out of credits."""
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

        if schema is CodePatch:
            return CodePatch(
                summary="Fallback code generated in offline mode.",
                files=[
                    FilePatch(
                        path="app/main.py",
                        content="from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'status': 'healthy'}\n",
                    ),
                    FilePatch(
                        path="tests/test_main.py",
                        content="from fastapi.testclient import TestClient\nfrom app.main import app\n\nclient = TestClient(app)\n\ndef test_root():\n    res = client.get('/')\n    assert res.status_code == 200\n",
                    ),
                ],
            )

        return schema.model_validate({})

    async def generate_structured(self, prompt: str, schema: Type[T], model: str | None = None) -> T:
        """Primary: Gemini -> Secondary: Groq -> Tertiary: Offline Mock."""
        if self.gemini_client:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model or self.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.1,
                    ),
                )
                return schema.model_validate_json(response.text)
            except Exception as exc:
                print(f"[Gateway Warning] Gemini call failed: {exc}. Switching to Groq...")

        return await self._fallback_groq(prompt, schema)

    async def _fallback_groq(self, prompt: str, schema: Type[T]) -> T:
        if not self.groq_key or _is_placeholder(self.groq_key):
            print("[Gateway Warning] GROQ_API_KEY is not configured. Utilizing offline fallback.")
            return self._offline_fallback(schema)

        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a strict JSON generator. Return ONLY valid JSON matching this schema:\n{json.dumps(schema.model_json_schema())}",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(self.groq_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return schema.model_validate_json(content)
        except Exception as exc:
            print(f"[Gateway Warning] Groq fallback failed: {exc}. Utilizing offline fallback.")
            return self._offline_fallback(schema)