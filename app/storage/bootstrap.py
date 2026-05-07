from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

TableKind = Literal["normal", "relation"]


@dataclass(frozen=True, slots=True)
class TableSpec:
    name: str
    kind: TableKind
    schemafull: bool = True
    from_table: str | None = None
    to_table: str | None = None


@dataclass(frozen=True, slots=True)
class FieldSpec:
    table: str
    name: str
    type_name: str

    @property
    def identity(self) -> str:
        return f"{self.table}.{self.name}"


@dataclass(frozen=True, slots=True)
class ViewSpec:
    name: str
    query: str


@dataclass(frozen=True, slots=True)
class IndexSpec:
    table: str
    fields: tuple[str, ...]
    unique: bool = False
    name: str | None = None

    @property
    def identity(self) -> str:
        if self.name is not None:
            return self.name
        fields = "_".join(self.fields)
        return f"{self.table}_{fields}"


class StorageLayoutConflict(RuntimeError):
    """Raised when existing storage does not match the expected layout."""


@dataclass(frozen=True, slots=True)
class StorageLayout:
    tables: tuple[TableSpec, ...]
    fields: tuple[FieldSpec, ...] = ()
    views: tuple[ViewSpec, ...] = ()
    indexes: tuple[IndexSpec, ...] = ()

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(table.name for table in self.tables)


ALPHA_STORAGE_LAYOUT = StorageLayout(
    tables=(
        TableSpec("note_roots", "normal"),
        TableSpec("note_revisions", "normal"),
        TableSpec("about_refs", "normal"),
        TableSpec("provenance_records", "normal"),
        TableSpec(
            "note_has_revision",
            "relation",
            from_table="note_roots",
            to_table="note_revisions",
        ),
        TableSpec(
            "note_current_revision",
            "relation",
            from_table="note_roots",
            to_table="note_revisions",
        ),
        TableSpec(
            "revision_previous",
            "relation",
            from_table="note_revisions",
            to_table="note_revisions",
        ),
        TableSpec(
            "revision_has_provenance",
            "relation",
            from_table="note_revisions",
            to_table="provenance_records",
        ),
        TableSpec(
            "note_about",
            "relation",
            from_table="note_roots",
            to_table="about_refs",
        ),
    ),
    fields=(
        FieldSpec("note_roots", "note_id", "string"),
        FieldSpec("note_roots", "current_version", "int"),
        FieldSpec("note_roots", "created_at", "datetime"),
        FieldSpec("note_roots", "updated_at", "datetime"),
        FieldSpec("note_revisions", "note_id", "string"),
        FieldSpec("note_revisions", "version", "int"),
        FieldSpec("note_revisions", "content", "string"),
        FieldSpec("note_revisions", "observed_at", "datetime"),
        FieldSpec("note_revisions", "created_at", "datetime"),
        FieldSpec("about_refs", "kind", "string"),
        FieldSpec("about_refs", "identity", "string"),
        FieldSpec("about_refs", "collection", "option<string>"),
        FieldSpec("about_refs", "key", "option<string>"),
        FieldSpec("about_refs", "label", "option<string>"),
        FieldSpec("about_refs", "resolved", "bool"),
        FieldSpec("provenance_records", "writer", "option<string>"),
        FieldSpec("provenance_records", "session_id", "option<string>"),
        FieldSpec("provenance_records", "source_type", "option<string>"),
        FieldSpec("provenance_records", "source_ref", "option<string>"),
        FieldSpec("note_has_revision", "edge_key", "string"),
        FieldSpec("note_current_revision", "edge_key", "string"),
        FieldSpec("revision_previous", "edge_key", "string"),
        FieldSpec("revision_has_provenance", "edge_key", "string"),
        FieldSpec("note_about", "edge_key", "string"),
    ),
    views=(
        ViewSpec(
            name="notes",
            query=(
                "SELECT "
                "type::record('notes', in.note_id) AS id, "
                "in.note_id AS note_id, "
                "out.version AS version, "
                "out.content AS content, "
                "out.observed_at AS observed_at, "
                "in.created_at AS created_at, "
                "out.created_at AS revision_created_at "
                "FROM note_current_revision"
            ),
        ),
    ),
    indexes=(
        IndexSpec(
            table="note_roots",
            fields=("note_id",),
            unique=True,
            name="note_roots_note_id_unique",
        ),
        IndexSpec(
            table="note_revisions",
            fields=("note_id", "version"),
            unique=True,
            name="note_revisions_note_id_version_unique",
        ),
        IndexSpec(
            table="about_refs",
            fields=("kind", "identity"),
            unique=True,
            name="about_refs_kind_identity",
        ),
        IndexSpec(
            table="note_current_revision",
            fields=("in",),
            unique=True,
            name="note_current_revision_in_unique",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class StorageBootstrapResult:
    created_tables: tuple[str, ...]
    existing_tables: tuple[str, ...]
    created_fields: tuple[str, ...]
    existing_fields: tuple[str, ...]
    created_views: tuple[str, ...]
    existing_views: tuple[str, ...]
    created_indexes: tuple[str, ...]
    existing_indexes: tuple[str, ...]

    @property
    def initialized(self) -> bool:
        return True


class StorageBackend(Protocol):
    def ensure_table(self, spec: TableSpec) -> bool: ...

    def ensure_field(self, spec: FieldSpec) -> bool: ...

    def ensure_view(self, spec: ViewSpec) -> bool: ...

    def ensure_index(self, spec: IndexSpec) -> bool: ...


@dataclass(frozen=True, slots=True)
class StorageBootstrapper:
    backend: StorageBackend
    layout: StorageLayout = ALPHA_STORAGE_LAYOUT

    def initialize(self) -> StorageBootstrapResult:
        created_tables: list[str] = []
        existing_tables: list[str] = []
        created_fields: list[str] = []
        existing_fields: list[str] = []
        created_views: list[str] = []
        existing_views: list[str] = []
        created_indexes: list[str] = []
        existing_indexes: list[str] = []

        for table in self.layout.tables:
            target = created_tables
            if not self.backend.ensure_table(table):
                target = existing_tables
            target.append(table.name)

        for field in self.layout.fields:
            target = created_fields
            if not self.backend.ensure_field(field):
                target = existing_fields
            target.append(field.identity)

        for view in self.layout.views:
            target = created_views
            if not self.backend.ensure_view(view):
                target = existing_views
            target.append(view.name)

        for index in self.layout.indexes:
            target = created_indexes
            if not self.backend.ensure_index(index):
                target = existing_indexes
            target.append(index.identity)

        return StorageBootstrapResult(
            created_tables=tuple(created_tables),
            existing_tables=tuple(existing_tables),
            created_fields=tuple(created_fields),
            existing_fields=tuple(existing_fields),
            created_views=tuple(created_views),
            existing_views=tuple(existing_views),
            created_indexes=tuple(created_indexes),
            existing_indexes=tuple(existing_indexes),
        )


__all__ = [
    "ALPHA_STORAGE_LAYOUT",
    "FieldSpec",
    "IndexSpec",
    "StorageBackend",
    "StorageBootstrapResult",
    "StorageBootstrapper",
    "StorageLayout",
    "StorageLayoutConflict",
    "TableKind",
    "TableSpec",
    "ViewSpec",
]
