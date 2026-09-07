# Sandbox

The sandbox holds runtime artifacts for the verifier:

- `workspace/` is reset before each generated patch is tested. It contains only the files written by the current `CodePatch`.
- `memory.sqlite3` is the default persistent MAG store for recently retrieved research context.

These files are local working data, not source code. Configure alternate locations with `MAG_MEMORY_PATH` or by passing a workspace path to `SandboxRunner` in tests.