from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelBase(BaseModel):
    """Base configuration for internal models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class ArangoDocument(ModelBase):
    """Base shape for Arango document records."""

    key: str = Field(alias="_key")
    created_at: datetime
    created_by: str


class ArangoEdge(ArangoDocument):
    """Base shape for Arango edge records."""

    from_id: str = Field(alias="_from")
    to_id: str = Field(alias="_to")


__all__ = ["ArangoDocument", "ArangoEdge", "ModelBase"]
