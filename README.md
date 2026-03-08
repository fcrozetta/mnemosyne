# mnemosyne

Project that aims to be a place where humans and AI can share their brains.

## Python Runtime

Mnemosyne uses `uv` for dependency management and packaging.

### Install

```bash
uv sync --dev
```

This creates `.venv/` and installs both dependencies and the local
`mnemosyne` package defined in `pyproject.toml`.

### Why `[tool.uv] package = true` exists

`[tool.uv] package = true` tells `uv` to install this repository as a package,
not just resolve third-party dependencies.

That matters here because:

- the `app` package is importable through the installed project
- local runtime and tests execute against packaged project metadata
- `uv sync` builds and installs `mnemosyne` from the current repo

Without it, `uv` can still manage dependencies, but the repo itself is not
treated as an installed package by default.

### Run

```bash
uv run fastapi dev app/main.py --host 127.0.0.1 --port 8000
```

`fastapi dev` is the default local development entrypoint. `uvicorn` remains a
valid lower-level runtime, but it is not the documented primary dev command.

### Local database

Start and seed ArangoDB:

```bash
make db
```

The default local settings are documented in `.env.example`.
