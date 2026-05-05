from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_initialized_storage() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "storage_initialized": True}
