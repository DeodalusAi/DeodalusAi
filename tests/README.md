# Tests

This directory contains the unit and integration-style tests for the DaedalusOS runtime. Pytest discovers it through `pytest.ini`.

Run the suite from the repository root:

```bash
python -m pytest -q
```

## Coverage by file

- `test_gateway.py`: structured generation, caching, fallback, and provider behavior.
- `test_local_llm.py`: local model routing and Ollama-compatible responses.
- `test_researcher.py`: retrieval, filtering, caching, and offline research behavior.
- `test_memory.py`: SQLite persistence and memory expiry.
- `test_sandbox.py`: patch writing, nested paths, pytest execution, failures, and timeouts.
- `test_github_config.py` and `test_github_ops.py`: repository validation and PR delivery behavior.

Generated projects are tested by the verifier in `sandbox/workspace`; those generated tests are separate from this repository's own test suite.