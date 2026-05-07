from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Response, status

from app.dependencies import get_notes_service
from app.service.notes import NotesService


def create_app() -> FastAPI:
    app = FastAPI(title="Mnemosyne", version="0.1.0-alpha")

    @app.get("/healthz")
    def healthz(
        response: Response,
        service: Annotated[NotesService, Depends(get_notes_service)],
    ) -> dict:
        initialized = service.storage_initialized()
        if not initialized:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ok": initialized,
            "storage_initialized": initialized,
        }

    return app


app = create_app()
