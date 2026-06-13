from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "db/schema.arcadesql"


class ArcadeRequestError(RuntimeError):
    """Raised when ArcadeDB returns an unexpected HTTP response."""


@dataclass(frozen=True, slots=True)
class ArcadeStorageBackend:
    base_url: str
    database: str = "mnemosyne"
    username: str = "root"
    password: str = "mnemosyne-root"
    timeout_seconds: float = 5.0

    def ready(self) -> bool:
        try:
            self._send("GET", "/api/v1/ready")
        except ArcadeRequestError:
            return False
        return True

    def database_exists(self) -> bool:
        exists = self._send("GET", f"/api/v1/exists/{self.database}")
        return isinstance(exists, dict) and exists.get("result") is True

    def ensure_database(self) -> bool:
        if self.database_exists():
            return False
        self._send(
            "POST",
            "/api/v1/server",
            body={"command": f"create database {self.database}"},
        )
        return True

    def apply_schema(self, schema: str) -> None:
        for statement in _schema_statements(schema):
            self.command(statement, language="sqlscript")

    def apply_default_schema(self) -> None:
        self.apply_schema(DEFAULT_SCHEMA_PATH.read_text())

    def command(
        self,
        command: str,
        *,
        language: str = "sql",
        params: dict[str, Any] | None = None,
    ) -> object:
        body: dict[str, Any] = {
            "language": language,
            "command": command,
        }
        if params is not None:
            body["params"] = params
        return self._send("POST", f"/api/v1/command/{self.database}", body=body)

    def query(
        self,
        query: str,
        *,
        language: str = "sql",
        params: dict[str, Any] | None = None,
    ) -> object:
        body: dict[str, Any] = {
            "language": language,
            "command": query,
        }
        if params is not None:
            body["params"] = params
        return self._send("POST", f"/api/v1/query/{self.database}", body=body)

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
    ) -> object:
        encoded_body = None
        headers = {
            "Accept": "application/json",
            "Authorization": self._authorization_header(),
        }
        if body is not None:
            encoded_body = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url.rstrip('/')}{path}",
            data=encoded_body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read()
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            msg = f"ArcadeDB HTTP {exc.code} for {method} {path}: {detail}"
            raise ArcadeRequestError(msg) from exc
        except URLError as exc:
            msg = f"Could not connect to ArcadeDB at {self.base_url}: {exc.reason}"
            raise ArcadeRequestError(msg) from exc

        if not payload:
            return {}
        try:
            return json.loads(payload.decode())
        except json.JSONDecodeError as exc:
            msg = f"ArcadeDB returned invalid JSON for {method} {path}."
            raise ArcadeRequestError(msg) from exc

    def _authorization_header(self) -> str:
        token = f"{self.username}:{self.password}".encode()
        return f"Basic {base64.b64encode(token).decode()}"


def _schema_statements(schema: str) -> tuple[str, ...]:
    statements: list[str] = []
    current: list[str] = []
    for char in schema:
        current.append(char)
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return tuple(statements)


__all__ = [
    "ArcadeRequestError",
    "ArcadeStorageBackend",
    "DEFAULT_SCHEMA_PATH",
]
