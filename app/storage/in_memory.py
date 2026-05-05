from __future__ import annotations

from dataclasses import dataclass, field

from app.storage.bootstrap import (
    FieldSpec,
    IndexSpec,
    StorageLayout,
    StorageLayoutConflict,
    TableSpec,
    ViewSpec,
)


@dataclass(slots=True)
class InMemoryStorageBackend:
    """In-memory catalog used to verify bootstrap behavior locally."""

    tables: dict[str, TableSpec] = field(default_factory=dict)
    fields: dict[str, FieldSpec] = field(default_factory=dict)
    views: dict[str, ViewSpec] = field(default_factory=dict)
    indexes: dict[str, IndexSpec] = field(default_factory=dict)

    def ensure_table(self, spec: TableSpec) -> bool:
        existing = self.tables.get(spec.name)
        if existing is not None:
            if existing != spec:
                msg = (
                    f"Table {spec.name!r} exists with incompatible layout: "
                    f"expected {spec!r}, got {existing!r}."
                )
                raise StorageLayoutConflict(msg)
            return False

        self.tables[spec.name] = spec
        return True

    def ensure_field(self, spec: FieldSpec) -> bool:
        existing = self.fields.get(spec.identity)
        if existing is not None:
            if existing != spec:
                msg = (
                    f"Field {spec.identity!r} exists with incompatible layout: "
                    f"expected {spec!r}, got {existing!r}."
                )
                raise StorageLayoutConflict(msg)
            return False

        self.fields[spec.identity] = spec
        return True

    def ensure_view(self, spec: ViewSpec) -> bool:
        existing = self.views.get(spec.name)
        if existing is not None:
            if existing != spec:
                msg = (
                    f"View {spec.name!r} exists with incompatible layout: "
                    f"expected {spec!r}, got {existing!r}."
                )
                raise StorageLayoutConflict(msg)
            return False

        self.views[spec.name] = spec
        return True

    def ensure_index(self, spec: IndexSpec) -> bool:
        existing = self.indexes.get(spec.identity)
        if existing is not None:
            if existing != spec:
                msg = (
                    f"Index {spec.identity!r} exists with incompatible layout: "
                    f"expected {spec!r}, got {existing!r}."
                )
                raise StorageLayoutConflict(msg)
            return False

        self.indexes[spec.identity] = spec
        return True

    def matches(self, layout: StorageLayout) -> bool:
        expected_tables = {spec.name: spec for spec in layout.tables}
        expected_fields = {spec.identity: spec for spec in layout.fields}
        expected_views = {spec.name: spec for spec in layout.views}
        expected_indexes = {spec.identity: spec for spec in layout.indexes}
        return (
            expected_tables.items() <= self.tables.items()
            and expected_fields.items() <= self.fields.items()
            and expected_views.items() <= self.views.items()
            and expected_indexes.items() <= self.indexes.items()
        )


__all__ = ["InMemoryStorageBackend"]
