from __future__ import annotations

import os
import uuid
from typing import List, Optional
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.producer.gateway import LLMGateway

load_dotenv()


def _is_placeholder(val: Optional[str]) -> bool:
    if not val:
        return True
    return val.strip().lower() in {
        "your_qdrant_api_key",
        "https://your-cluster.qdrant.tech",
        "https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io:6333",
    }


class ResearcherAgent:
    def __init__(self, collection_name: str = "daedalus_docs", gateway: Optional[LLMGateway] = None):
        self.collection_name = collection_name
        self.gateway = gateway or LLMGateway()
        
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        # Initialize Qdrant Client (Cloud if credentials exist, otherwise In-Memory for local dev)
        if self.qdrant_url and not _is_placeholder(self.qdrant_url):
            try:
                self.client = QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key if not _is_placeholder(self.qdrant_api_key) else None,
                    timeout=10.0
                )
            except Exception as e:
                print(f"[Researcher Warning] Cloud Qdrant connection failed: {e}. Using in-memory client.")
                self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(":memory:")

        self._ensure_collection()

    def _ensure_collection(self):
        """Creates the collection if it does not already exist."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=768,  # Standard size for text-embedding-004 / lightweight embeddings
                        distance=qmodels.Distance.COSINE
                    )
                )
                self._seed_default_docs()
        except Exception as e:
            print(f"[Researcher Warning] Error initializing collection: {e}")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generates vector embeddings. Uses Gemini if available, 
        or creates a deterministic normalized mock vector for offline resilience.
        """
        if self.gateway.gemini_client:
            try:
                result = self.gateway.gemini_client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                return result.embedding.values
            except Exception:
                pass
        
        # Deterministic 768-dim mock vector fallback for local testing
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        raw = [(b / 255.0) for b in h]
        repeated = (raw * ((768 // len(raw)) + 1))[:768]
        norm = sum(x * x for x in repeated) ** 0.5
        return [x / norm for x in repeated]

    def _seed_default_docs(self):
        """Pre-populates best-practice architecture documents into Qdrant."""
        seed_docs = [
            {
                "title": "FastAPI Standard Architectural Guidelines",
                "content": "Use APIRouter for route modularity. Implement clean dependency injection via Depends(). Place Pydantic models in app/schemas.py or app/models.py. Use Starlette TestClient for writing pytest suites."
            },
            {
                "title": "Clean Rate Limiter Design",
                "content": "Token bucket algorithms must update tokens based on (current_time - last_update_time) * fill_rate. Return HTTP 429 Too Many Requests with a 'Retry-After' header when bucket is empty."
            },
            {
                "title": "Pytest Verification Conventions",
                "content": "Test functions must start with test_*. Assert status codes, response payloads, and exception triggers. Never mock without verifying true function execution."
            }
        ]

        points = []
        for doc in seed_docs:
            vector = self._get_embedding(doc["content"])
            points.append(
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=doc
                )
            )
        
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        except Exception as e:
            print(f"[Researcher Warning] Failed to seed default docs: {e}")

    def search_context(self, query: str, limit: int = 2) -> str:
        """
        Queries Qdrant vector database for relevant architectural guidelines
        and formats them into a single string for the Developer Agent.
        """
        try:
            query_vector = self._get_embedding(query)
            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit
            )

            if not search_result or not search_result.points:
                return "Use standard Python clean-code architecture with modular functions and pytest suites."

            context_blocks = []
            for hit in search_result.points:
                payload = hit.payload or {}
                title = payload.get("title", "Guideline")
                content = payload.get("content", "")
                context_blocks.append(f"### {title}\n{content}")

            return "\n\n".join(context_blocks)

        except Exception as e:
            print(f"[Researcher Warning] Qdrant search encountered an issue: {e}")
            return "Follow standard Python modular design patterns and pytest unit testing conventions."


# --- Standalone Verification Test for Person 1 ---
if __name__ == "__main__":
    print("=== [Person 1] Testing Researcher Agent with Qdrant ===")
    researcher = ResearcherAgent()
    
    test_query = "How to build a token bucket rate limiter with FastAPI middleware?"
    print(f"Query: '{test_query}'\n")
    
    context = researcher.search_context(test_query)
    print("✅ Retrieved Architectural Context:\n")
    print(context)