# Claim 0037: API Stack and Layout Directives

## Statement

Future API work uses Python with `uv`, FastAPI for HTTP, `fastapi-mcp` for MCP,
and `app/main.py` as the entrypoint.

## Scope

- Module layout follows `router`, `handler`, `service`, `repository`.
- Type hints are expected throughout the codebase.
- Comments stay lean and meaningful.
- Docstrings are minimal but useful for LSP/autocomplete.

## Acceptance Checks

- API entrypoint is `app/main.py`.
- Project layout follows the defined module split.
- Code style favors typed, lean, readable Python.
