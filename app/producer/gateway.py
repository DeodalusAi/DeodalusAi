import os
import json
from typing import Type, TypeVar
from pydantic import BaseModel
from google import genai
from google.genai import types
import httpx
from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T", bound=BaseModel)

class LLMGateway:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None

    async def generate_structured(self, prompt: str, schema: Type[T], model: str = "gemini-2.0-flash") -> T:
        """
        Attempts structured output generation via Gemini first.
        Automatically falls back to Groq if rate-limited, timed out, or unavailable.
        """
        if self.gemini_client:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.1
                    ),
                )
                return schema.model_validate_json(response.text)
            except Exception as e:
                print(f"[Gateway Warning] Gemini primary call failed: {e}. Switching to Groq fallback...")

        return await self._fallback_groq(prompt, schema)

    async def _fallback_groq(self, prompt: str, schema: Type[T]) -> T:
        if not self.groq_key:
            raise RuntimeError("GROQ_API_KEY is not set in environment or .env file.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a strict JSON generator. Return ONLY a valid JSON object matching this schema:\n{json.dumps(schema.model_json_schema())}"
                },
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return schema.model_validate_json(content)

# Standalone verification script for Person 1
if __name__ == "__main__":
    import asyncio
    from app.schemas import CodePatch

    async def main():
        gateway = LLMGateway()
        print("=== [Person 1] Testing Gateway with Gemini & Groq Fallback ===")
        test_prompt = "Generate a simple add function in Python (app/calc.py) and a pytest suite (tests/test_calc.py)."
        result = await gateway.generate_structured(test_prompt, CodePatch)
        print("\n✅ Gateway Verification Successful!")
        print(f"Summary: {result.summary}")
        for file in result.files:
            print(f"  - {file.path}")

    asyncio.run(main())