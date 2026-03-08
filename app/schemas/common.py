from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    """Base schema settings shared by API request and response models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


EntityKind: TypeAlias = Literal[
    "person",
    "meeting",
    "state",
    "follow_up",
    "item",
    "location",
    "note",
]


class EntityRef(SchemaModel):
    """Canonical reference to an existing entity."""

    collection: str
    key: str


__all__ = ["EntityKind", "EntityRef", "SchemaModel"]
