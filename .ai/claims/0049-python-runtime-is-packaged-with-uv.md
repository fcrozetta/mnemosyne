# Claim 0049: Python Runtime Is Packaged with uv

## Statement

Mnemosyne's Python runtime is packaged with `uv` using a repo-level
`pyproject.toml` and checked-in dependency lockfile.

## Scope

- Project metadata and dependencies live in `pyproject.toml`.
- Runtime dependencies include FastAPI, Pydantic, Pydantic Settings,
  `python-arango`, and the FastAPI standard extra used for the `fastapi`
  development CLI.
- Development dependencies include pytest, Ruff, and HTTPX.
- `uv.lock` is checked in for reproducible local installs.
- `[tool.uv] package = true` is used so `uv sync` installs the local
  `mnemosyne` project as a package rather than only installing third-party
  dependencies.

## Acceptance Checks

- `pyproject.toml` exists at repo root.
- `uv.lock` exists at repo root.
- `uv sync --dev` can create a working local environment for the API runtime.
- README documents the `uv` workflow and explains why
  `[tool.uv] package = true` is set.
- README documents `uv run fastapi dev app/main.py` as the primary local
  development entrypoint.
