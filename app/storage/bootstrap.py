from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageBootstrapResult:
    created_tables: tuple[str, ...] = ()
    existing_tables: tuple[str, ...] = ()
    created_fields: tuple[str, ...] = ()
    existing_fields: tuple[str, ...] = ()
    created_views: tuple[str, ...] = ()
    existing_views: tuple[str, ...] = ()
    created_indexes: tuple[str, ...] = ()
    existing_indexes: tuple[str, ...] = ()

    @property
    def initialized(self) -> bool:
        return True


__all__ = ["StorageBootstrapResult"]
