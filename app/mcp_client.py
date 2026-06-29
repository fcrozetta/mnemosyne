import os
from collections.abc import Mapping
from typing import Any

import httpx

DEFAULT_API_URL = "http://127.0.0.1:8180"


class MnemosyneApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MnemosyneApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            headers=dict(headers or {}),
            timeout=timeout,
        )

    @classmethod
    def from_env(cls) -> "MnemosyneApiClient":
        return cls(
            os.getenv("MNEMOSYNE_API_URL", DEFAULT_API_URL),
            headers=_access_headers_from_env(),
            timeout=float(os.getenv("MNEMOSYNE_MCP_TIMEOUT_SECONDS", "30")),
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def create_document(
        self,
        *,
        content: str,
        topics: list[str] | None = None,
        mentions: list[dict[str, Any]] | None = None,
        source_type: str = "agent",
        source_label: str = "mnemosyne-mcp",
        source_ref: str | None = None,
        writer: str | None = None,
        session_id: str | None = None,
        observed_channel: str | None = None,
        observed_at: str | None = None,
        domain: str = "general",
        sensitivity: str = "personal",
        subject: str | None = None,
        allowed_purposes: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = _without_none(
            {
                "type": "document",
                "content": content,
                "topics": topics or [],
                "mentions": mentions or [],
                "observed_at": observed_at,
                "domain": domain,
                "sensitivity": sensitivity,
                "subject": subject,
                "allowed_purposes": allowed_purposes or [],
                "source": _without_none(
                    {
                        "source_type": source_type,
                        "label": source_label,
                        "source_ref": source_ref,
                        "writer": writer,
                        "session_id": session_id,
                        "observed_channel": observed_channel,
                    }
                ),
            }
        )
        return self._request("POST", "observations", json=payload)

    def find_entities(
        self,
        *,
        entity_type: str | None = None,
        query: str | None = None,
        scope: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        params = _without_none(
            {
                "type": entity_type,
                "q": query,
                "scope": scope,
                "limit": limit,
            }
        )
        response = self._request("GET", "entities", params=params)
        if not isinstance(response, list):
            raise MnemosyneApiError("Expected /entities to return a list.")
        return response

    def create_entity(
        self,
        *,
        entity_type: str,
        label: str,
        scope: str = "personal",
        sensitivity: str = "personal",
        allowed_purposes: list[str] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if profile is None:
            existing = self._find_exact_entity(
                entity_type=entity_type,
                label=label,
                scope=scope,
            )
            if existing is not None:
                return existing

        payload = _without_none(
            {
                "type": entity_type,
                "label": label,
                "scope": scope,
                "sensitivity": sensitivity,
                "allowed_purposes": allowed_purposes or [],
            }
        )
        if profile:
            payload[entity_type] = profile
        return self._request("POST", "entities", json=payload)

    def get_entity(self, *, entity_id: str) -> dict[str, Any]:
        return self._request("GET", f"entities/{entity_id}")

    def _find_exact_entity(
        self,
        *,
        entity_type: str,
        label: str,
        scope: str,
    ) -> dict[str, Any] | None:
        normalized_label = _normalize_label(label)
        query_label = " ".join(label.split())
        for entity in self.find_entities(
            entity_type=entity_type,
            query=query_label,
            scope=scope,
            limit=10,
        ):
            if (
                entity.get("type") == entity_type
                and entity.get("scope") == scope
                and entity.get("normalized_label") == normalized_label
            ):
                return entity
        return None

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if path.startswith("/"):
            path = path.lstrip("/")
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise MnemosyneApiError(f"Mnemosyne API request failed: {exc}") from exc
        if response.status_code >= 400:
            raise MnemosyneApiError(
                _error_message(response),
                status_code=response.status_code,
            )
        if not response.content:
            return None
        return response.json()


def _access_headers_from_env() -> dict[str, str]:
    headers = {
        "X-Mnemosyne-Client-App": os.getenv(
            "MNEMOSYNE_MCP_CLIENT_APP", "mnemosyne-mcp"
        ),
        "X-Mnemosyne-Service-Identity": os.getenv(
            "MNEMOSYNE_MCP_SERVICE_IDENTITY", "mnemosyne-mcp"
        ),
        "X-Mnemosyne-Purpose": os.getenv("MNEMOSYNE_MCP_PURPOSE", "recall"),
        "X-Mnemosyne-Scopes": os.getenv(
            "MNEMOSYNE_MCP_SCOPES", "mnemosyne.query mnemosyne.write"
        ),
        "X-Mnemosyne-Roles": os.getenv("MNEMOSYNE_MCP_ROLES", "owner"),
        "X-Mnemosyne-Projection": os.getenv(
            "MNEMOSYNE_MCP_PROJECTION", "observation_summary"
        ),
    }
    actor_user = os.getenv("MNEMOSYNE_MCP_ACTOR_USER")
    if actor_user:
        headers["X-Mnemosyne-Actor-User"] = actor_user
    return headers


def _without_none(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).lower()


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return f"Mnemosyne API returned {response.status_code}: {body}"


__all__ = ["DEFAULT_API_URL", "MnemosyneApiClient", "MnemosyneApiError"]
