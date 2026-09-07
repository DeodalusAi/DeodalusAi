from __future__ import annotations

import inspect
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from prometheus_client import Counter, Histogram


NODE_EXECUTION_TIME = Histogram(
    "daedalus_node_duration_seconds",
    "Time spent in each LangGraph node",
    ["node_name"],
)
HEALING_CYCLES = Counter(
    "daedalus_healing_cycles_total",
    "Total self-healing correction attempts",
)
TEST_RESULTS = Counter(
    "daedalus_test_runs_total",
    "Pytest outcomes in sandbox",
    ["status"],
)
LLM_TOKEN_USAGE = Counter(
    "daedalus_llm_token_usage_total",
    "Tokens reported by LLM providers",
    ["model", "token_type"],
)
HTTP_REQUESTS = Counter(
    "daedalus_http_requests_total",
    "HTTP requests handled by the DaedalusOS API",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "daedalus_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)

F = TypeVar("F", bound=Callable[..., Any])


def observe_node(node_name: str) -> Callable[[F], F]:
    """Measure sync or async LangGraph node execution without changing its result."""
    def decorator(function: F) -> F:
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                try:
                    return await function(*args, **kwargs)
                finally:
                    NODE_EXECUTION_TIME.labels(node_name).observe(time.perf_counter() - started)

            return async_wrapper  # type: ignore[return-value]

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                NODE_EXECUTION_TIME.labels(node_name).observe(time.perf_counter() - started)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def record_test_result(passed: bool) -> None:
    TEST_RESULTS.labels(status="passed" if passed else "failed").inc()


def record_token_usage(model: str, usage: Any) -> None:
    if not usage:
        return
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif not isinstance(usage, dict):
        usage = {
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "completion_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }
    for key, token_type in (
        ("prompt_tokens", "prompt"),
        ("completion_tokens", "completion"),
        ("total_tokens", "total"),
    ):
        value = usage.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            LLM_TOKEN_USAGE.labels(model=model, token_type=token_type).inc(value)