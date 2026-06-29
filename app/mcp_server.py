from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_client import MnemosyneApiClient

ClientFactory = Callable[[], Any]


def build_mcp_server(
    client_factory: ClientFactory = MnemosyneApiClient.from_env,
) -> FastMCP:
    server = FastMCP(
        "mnemosyne-memory",
        instructions=(
            "Use these tools only for curated, provenance-backed Mnemosyne "
            "memory operations. They intentionally expose memory intents rather "
            "than mirroring the raw HTTP API."
        ),
    )

    @server.tool(
        description=(
            "Create a provenance document in Mnemosyne. Use this before writing "
            "curated graph facts so future facts can reference the source."
        )
    )
    def create_document(
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
        return _call_client(
            client_factory,
            "create_document",
            content=content,
            topics=topics,
            mentions=mentions,
            source_type=source_type,
            source_label=source_label,
            source_ref=source_ref,
            writer=writer,
            session_id=session_id,
            observed_channel=observed_channel,
            observed_at=observed_at,
            domain=domain,
            sensitivity=sensitivity,
            subject=subject,
            allowed_purposes=allowed_purposes,
        )

    @server.tool(
        description=(
            "Find existing curated entities before creating new ones. Use this "
            "to avoid duplicate people, places, stores, and items."
        )
    )
    def find_entities(
        query: str | None = None,
        entity_type: str | None = None,
        scope: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        return _call_client(
            client_factory,
            "find_entities",
            entity_type=entity_type,
            query=query,
            scope=scope,
            limit=limit,
        )

    @server.tool(
        description=(
            "Create or update one curated entity node. Search with find_entities "
            "first when the caller is not sure the entity is new. The optional "
            "profile object is placed under the entity type key, e.g. person, "
            "location, store, or item."
        )
    )
    def create_entity(
        entity_type: str,
        label: str,
        scope: str = "personal",
        sensitivity: str = "personal",
        allowed_purposes: list[str] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _call_client(
            client_factory,
            "create_entity",
            entity_type=entity_type,
            label=label,
            scope=scope,
            sensitivity=sensitivity,
            allowed_purposes=allowed_purposes,
            profile=profile,
        )

    @server.tool(
        description="Fetch one curated Mnemosyne entity by id."
    )
    def get_entity(entity_id: str) -> dict[str, Any]:
        return _call_client(client_factory, "get_entity", entity_id=entity_id)

    return server


def _call_client(
    client_factory: ClientFactory,
    method_name: str,
    **kwargs: Any,
) -> Any:
    client = client_factory()
    try:
        method = getattr(client, method_name)
        return method(**kwargs)
    finally:
        close = getattr(client, "close", None)
        if close is not None:
            close()


def main() -> None:
    build_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()


__all__ = ["build_mcp_server", "main"]
