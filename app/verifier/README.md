# Verification and Delivery

The verifier side turns a generated `CodePatch` into evidence that the patch works, then optionally delivers it to GitHub.

## Components

- `sandbox.py` resets `sandbox/workspace`, writes the generated files, and runs `pytest -v --tb=short` in a subprocess with a timeout.
- `reviewer.py` reduces noisy pytest output to an actionable failure summary for the healer.
- `healer.py` asks the model for a corrected patch and enforces a hard cap of three healing attempts.
- `github_ops.py` creates a branch, writes or updates patch files, and opens a pull request through PyGithub.

## Safety boundaries

- Patch paths must remain inside the sandbox workspace.
- Test execution has a timeout and does not inherit the repository `PYTHONPATH`.
- The graph also applies `max_iterations` (clamped to 1 through 10) to stop repeated failures.
- GitHub delivery requires `GITHUB_TOKEN` and an `owner/repository` target.

The final workflow event is `COMPLETE` only when tests pass and a PR URL exists. Passing tests without successful GitHub delivery is reported as an error so delivery status is never hidden.