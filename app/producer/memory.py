from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path


class AgentMemory:
    """Small persistent MAG store for reusable task context and outcomes."""

    def __init__(self, path: str | None = None, ttl_seconds: float | None = None):
        configured_path = path or os.getenv("MAG_MEMORY_PATH", "sandbox/memory.sqlite3")
        self.path = Path(configured_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds or float(os.getenv("MAG_MEMORY_TTL_SECONDS", "86400"))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_memory (
                    memory_key TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    context TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    accessed_at REAL NOT NULL
                )"""
            )

    @staticmethod
    def _key(query: str) -> str:
        normalized = " ".join(query.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def recall(self, query: str) -> str | None:
        memory_key = self._key(query)
        cutoff = time.time() - self.ttl_seconds
        with self._connect() as connection:
            row = connection.execute(
                "SELECT context FROM agent_memory WHERE memory_key = ? AND created_at >= ?",
                (memory_key, cutoff),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE agent_memory SET accessed_at = ? WHERE memory_key = ?",
                (time.time(), memory_key),
            )
            return row[0]

    def remember(self, query: str, context: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO agent_memory(memory_key, query, context, created_at, accessed_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(memory_key) DO UPDATE SET
                     context = excluded.context,
                     created_at = excluded.created_at,
                     accessed_at = excluded.accessed_at""",
                (self._key(query), query.strip(), context.strip(), now, now),
            )
