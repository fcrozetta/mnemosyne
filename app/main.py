from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI

from app.dependencies import get_notes_service
from app.service.notes import NotesService


def create_app() -> FastAPI:
    app = FastAPI(title="Mnemosyne", version="0.1.0-alpha")

    @app.get("/healthz")
    def healthz(service: Annotated[NotesService, Depends(get_notes_service)]) -> dict:
        return {
            "ok": True,
            "storage_initialized": service.storage_initialized(),
        }

    return app


app = create_app()
