import asyncio
import json
import tomllib
from pathlib import Path
from typing import Any

import httpx

from app.mcp_client import MnemosyneApiClient, MnemosyneApiError
from app.mcp_server import build_mcp_server


class StubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def create_document(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_document", kwargs))
        return {"id": "obs_123", "current_revision": "obs_123:v1"}

    def close(self) -> None:
        self.closed = True


def test_mcp_client_create_document_posts_curated_document_payload() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": "obs_123",
                "type": "document",
                "current_revision": "obs_123:v1",
            },
        )

    http_client = httpx.Client(
        base_url="http://mnemosyne.test",
        transport=httpx.MockTransport(handler),
    )
    client = MnemosyneApiClient(
        "http://mnemosyne.test",
        http_client=http_client,
    )

    response = client.create_document(
        content="Fernando owns a Pilot Custom 823.",
        topics=["pens", "possessions"],
        mentions=[{"type": "item", "label": "Pilot Custom 823"}],
        source_label="telegram",
        observed_at="2026-06-29T10:00:00Z",
        domain="shopping",
        sensitivity="personal",
        allowed_purposes=["recall"],
    )

    assert response["id"] == "obs_123"
    assert seen == {
        "method": "POST",
        "path": "/observations",
        "body": {
            "type": "document",
            "content": "Fernando owns a Pilot Custom 823.",
            "topics": ["pens", "possessions"],
            "mentions": [{"type": "item", "label": "Pilot Custom 823"}],
            "observed_at": "2026-06-29T10:00:00Z",
            "domain": "shopping",
            "sensitivity": "personal",
            "allowed_purposes": ["recall"],
            "source": {
                "source_type": "agent",
                "label": "telegram",
            },
        },
    }


def test_mcp_client_entity_tools_wrap_entity_registry() -> None:
    requests: list[tuple[str, str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            requests.append((request.method, str(request.url), None))
            return httpx.Response(200, json=[{"id": "ent_1", "label": "Appelboom"}])
        requests.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(201, json={"id": "ent_2", "label": "Appelboom"})

    http_client = httpx.Client(
        base_url="http://mnemosyne.test",
        transport=httpx.MockTransport(handler),
    )
    client = MnemosyneApiClient(
        "http://mnemosyne.test",
        http_client=http_client,
    )

    found = client.find_entities(
        entity_type="store",
        query="Appelboom",
        scope="vendors/pens",
        limit=5,
    )
    created = client.create_entity(
        entity_type="store",
        label="Appelboom",
        scope="vendors/pens",
        sensitivity="public",
        allowed_purposes=["recall"],
        profile={"store_kind": "retailer", "website": "https://example.com"},
    )

    assert found == [{"id": "ent_1", "label": "Appelboom"}]
    assert created == {"id": "ent_2", "label": "Appelboom"}
    assert requests[0] == (
        "GET",
        "http://mnemosyne.test/entities?type=store&q=Appelboom&scope=vendors%2Fpens&limit=5",
        None,
    )
    assert requests[1] == (
        "POST",
        "/entities",
        {
            "type": "store",
            "label": "Appelboom",
            "scope": "vendors/pens",
            "sensitivity": "public",
            "allowed_purposes": ["recall"],
            "store": {"store_kind": "retailer", "website": "https://example.com"},
        },
    )


def test_mcp_client_returns_existing_entity_without_profileless_upsert() -> None:
    requests: list[tuple[str, str, Any]] = []

    existing = {
        "id": "ent_1",
        "type": "person",
        "label": "Fernando Crozetta",
        "normalized_label": "fernando crozetta",
        "scope": "personal",
        "person": {
            "display_name": "Fernando Crozetta",
            "contact_methods": [
                {
                    "kind": "email",
                    "value": "fernando@example.test",
                    "sensitivity": "restricted",
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url), None))
        if request.method == "POST":
            return httpx.Response(500, json={"detail": "profile was overwritten"})
        return httpx.Response(200, json=[existing])

    http_client = httpx.Client(
        base_url="http://mnemosyne.test",
        transport=httpx.MockTransport(handler),
    )
    client = MnemosyneApiClient(
        "http://mnemosyne.test",
        http_client=http_client,
    )

    entity = client.create_entity(
        entity_type="person",
        label=" Fernando   Crozetta ",
    )

    assert entity == existing
    assert requests == [
        (
            "GET",
            "http://mnemosyne.test/entities?type=person&q=Fernando+Crozetta&scope=personal&limit=10",
            None,
        )
    ]


def test_mcp_client_preserves_base_url_path_prefix() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.method == "GET" and request.url.path.endswith("/entities"):
            return httpx.Response(200, json=[])
        if request.method == "GET":
            return httpx.Response(200, json={"id": "ent_1"})
        return httpx.Response(201, json={"id": "obs_1"})

    http_client = httpx.Client(
        base_url="https://mnemosyne.test/api/v1/",
        transport=httpx.MockTransport(handler),
    )
    client = MnemosyneApiClient(
        "https://mnemosyne.test/api/v1/",
        http_client=http_client,
    )

    client.create_document(content="source document")
    client.find_entities(query="pilot")
    client.create_entity(entity_type="item", label="Pilot Custom 823")
    client.get_entity(entity_id="ent_1")

    assert urls == [
        "https://mnemosyne.test/api/v1/observations",
        "https://mnemosyne.test/api/v1/entities?q=pilot&limit=25",
        "https://mnemosyne.test/api/v1/entities?type=item&q=Pilot+Custom+823&scope=personal&limit=10",
        "https://mnemosyne.test/api/v1/entities",
        "https://mnemosyne.test/api/v1/entities/ent_1",
    ]


def test_mcp_client_raises_clear_api_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "invalid"})

    http_client = httpx.Client(
        base_url="http://mnemosyne.test",
        transport=httpx.MockTransport(handler),
    )
    client = MnemosyneApiClient(
        "http://mnemosyne.test",
        http_client=http_client,
    )

    try:
        client.get_entity(entity_id="missing")
    except MnemosyneApiError as exc:
        assert exc.status_code == 422
        assert "invalid" in str(exc)
    else:
        raise AssertionError("expected MnemosyneApiError")


def test_mcp_server_exposes_curated_memory_tools() -> None:
    stub = StubClient()
    server = build_mcp_server(lambda: stub)

    async def run() -> None:
        tools = await server.list_tools()
        assert [tool.name for tool in tools] == [
            "create_document",
            "find_entities",
            "create_entity",
            "get_entity",
        ]
        _content, structured = await server.call_tool(
            "create_document",
            {"content": "Fernando owns a Pilot Custom 823."},
        )
        assert structured == {"id": "obs_123", "current_revision": "obs_123:v1"}

    asyncio.run(run())
    assert stub.calls == [
        (
            "create_document",
            {
                "content": "Fernando owns a Pilot Custom 823.",
                "topics": None,
                "mentions": None,
                "source_type": "agent",
                "source_label": "mnemosyne-mcp",
                "source_ref": None,
                "writer": None,
                "session_id": None,
                "observed_channel": None,
                "observed_at": None,
                "domain": "general",
                "sensitivity": "personal",
                "subject": None,
                "allowed_purposes": None,
            },
        )
    ]
    assert stub.closed is True


def test_package_declares_mcp_console_script_and_runtime_dependencies() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert pyproject["project"]["scripts"]["mnemosyne-mcp"] == (
        "app.mcp_server:main"
    )
    dependencies = pyproject["project"]["dependencies"]
    assert "mcp>=1.12.0,<2" in dependencies
    assert "httpx>=0.27.0" in dependencies
