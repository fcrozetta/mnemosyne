from __future__ import annotations

import binascii
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.notes import (
    AboutKind,
    CreateNoteInput,
    InvalidNotePatchError,
    Note,
    NoteContext,
    NoteNotFoundError,
    NoteRevision,
    NoteSearchResult,
    PatchNoteInput,
    PendingAboutRef,
    Provenance,
    ResolvedAboutRef,
    VersionConflictError,
    append_addendum,
    content_preview,
    merge_about_refs,
    next_note_id,
    normalize_label,
    related_overlap,
    score_content_match,
    split_about_refs,
    utc_now,
)
from app.repository.notes import NotesRepository
from app.storage.bootstrap import (
    ALPHA_STORAGE_LAYOUT,
    StorageBootstrapper,
    StorageBootstrapResult,
    StorageLayout,
    StorageLayoutConflict,
)
from app.storage.surreal import (
    SurrealRequestError,
    SurrealStorageBackend,
    _record_id,
    _to_surql,
)


@dataclass(slots=True)
class SurrealNotesRepository(NotesRepository):
    """Repository skeleton backed by SurrealDB bootstrap and layout checks."""

    runtime: SurrealStorageBackend
    bootstrap: SurrealStorageBackend | None = None
    layout: StorageLayout = ALPHA_STORAGE_LAYOUT

    def initialize_storage(self) -> StorageBootstrapResult:
        backend = self.bootstrap if self.bootstrap is not None else self.runtime
        backend.wait_until_ready(timeout_seconds=backend.timeout_seconds)
        backend.ensure_namespace_database()
        result = StorageBootstrapper(backend, self.layout).initialize()
        if self.bootstrap is not None:
            self.bootstrap.ensure_database_user(
                self.runtime.username,
                self.runtime.password,
            )
        return result

    def storage_initialized(self) -> bool:
        try:
            self.runtime.wait_until_ready(timeout_seconds=self.runtime.timeout_seconds)
            return self.runtime.sign_in().matches_layout(self.layout)
        except (StorageLayoutConflict, SurrealRequestError, TimeoutError):
            return False

    def create_note(self, note: CreateNoteInput) -> Note:
        backend = self.runtime.sign_in()
        observed_at = note.observed_at or utc_now()
        created_at = observed_at
        revision_created_at = utc_now()
        merged_about = merge_about_refs((), note.about)
        resolved_about, pending_about = split_about_refs(merged_about)

        for _attempt in range(8):
            note_id = next_note_id(self._list_existing_note_ids(backend))
            try:
                backend.query(
                    self._create_note_transaction_sql(
                        note_id=note_id,
                        content=note.content,
                        observed_at=observed_at,
                        created_at=created_at,
                        revision_created_at=revision_created_at,
                        resolved_about=resolved_about,
                        pending_about=pending_about,
                        provenance=note.provenance,
                    )
                )
            except SurrealRequestError as exc:
                retryable_note_conflict = _is_retryable_create_conflict(exc, note_id)
                if retryable_note_conflict or _is_retryable_about_ref_conflict(exc):
                    continue
                raise
            return self._get_note(backend, note_id)

        msg = "Failed to allocate a unique note id after repeated conflicts."
        raise SurrealRequestError(msg)

    def get_note(self, note_id: str) -> Note:
        return self._get_note(self.runtime.sign_in(), note_id)

    def search_notes(self, query: str, limit: int = 5) -> tuple[NoteSearchResult, ...]:
        backend = self.runtime.sign_in()
        rows = backend.query("SELECT * FROM notes;")
        if not isinstance(rows, list):
            return ()

        matches: list[NoteSearchResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            content = _string_field(row, "content")
            score = score_content_match(content, query)
            if score <= 0:
                continue
            matches.append(
                NoteSearchResult(
                    note_id=_string_field(row, "note_id"),
                    version=_int_field(row, "version"),
                    content_preview=content_preview(content),
                    observed_at=_datetime_field(row, "observed_at"),
                    score=score,
                )
            )

        matches.sort(
            key=lambda item: (
                item.score,
                item.observed_at.timestamp(),
                item.note_id,
            ),
            reverse=True,
        )
        return tuple(matches[:limit])

    def patch_note(self, note_id: str, patch: PatchNoteInput) -> Note:
        backend = self.runtime.sign_in()
        current_note = self._get_note(backend, note_id)
        latest = current_note.latest_revision
        assert latest is not None

        if patch.version != latest.version:
            raise VersionConflictError(
                note_id=note_id,
                current_version=latest.version,
                requested_version=patch.version,
            )

        if (
            patch.addendum is None
            and not patch.add_about
            and patch.observed_at is None
        ):
            raise InvalidNotePatchError(
                "Patch request must include at least one change."
            )

        merged_about = merge_about_refs(
            (*latest.resolved_about, *latest.pending_about),
            patch.add_about,
        )
        resolved_about, pending_about = split_about_refs(merged_about)
        observed_at = patch.observed_at or latest.observed_at
        revision_created_at = utc_now()
        next_version = latest.version + 1
        content = (
            append_addendum(latest.content, patch.addendum)
            if patch.addendum is not None
            else latest.content
        )

        last_error: SurrealRequestError | None = None
        for _attempt in range(3):
            try:
                backend.query(
                    self._patch_note_transaction_sql(
                        note_id=note_id,
                        expected_version=patch.version,
                        next_version=next_version,
                        content=content,
                        observed_at=observed_at,
                        revision_created_at=revision_created_at,
                        resolved_about=resolved_about,
                        pending_about=pending_about,
                    )
                )
            except SurrealRequestError as exc:
                current_version = _parse_version_conflict(exc, note_id)
                if current_version is not None:
                    raise VersionConflictError(
                        note_id=note_id,
                        current_version=current_version,
                        requested_version=patch.version,
                    ) from exc
                if _is_retryable_patch_conflict(exc, note_id, next_version):
                    raise VersionConflictError(
                        note_id=note_id,
                        current_version=self._load_current_version(backend, note_id),
                        requested_version=patch.version,
                    ) from exc
                if _is_note_not_found(exc, note_id):
                    raise NoteNotFoundError(note_id) from exc
                if _is_retryable_about_ref_conflict(exc):
                    last_error = exc
                    continue
                raise
            break
        else:
            assert last_error is not None
            raise last_error

        return self._get_note(backend, note_id)

    def get_note_context(self, note_id: str, limit: int = 5) -> NoteContext:
        backend = self.runtime.sign_in()
        anchor = self._get_note(backend, note_id)
        related: list[NoteSearchResult] = []

        for candidate_id in self._list_note_ids_from_view(backend):
            if candidate_id == note_id:
                continue
            candidate = self._get_note(backend, candidate_id)
            overlap = related_overlap(anchor, candidate)
            latest = candidate.latest_revision
            if overlap <= 0 or latest is None:
                continue
            related.append(
                NoteSearchResult(
                    note_id=candidate.note_id,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    score=float(overlap),
                )
            )

        related.sort(
            key=lambda item: (
                item.score,
                item.observed_at.timestamp(),
                item.note_id,
            ),
            reverse=True,
        )
        return NoteContext(note=anchor, related_notes=tuple(related[:limit]))

    def _get_note(self, backend: SurrealStorageBackend, note_id: str) -> Note:
        rows = backend.query(
            "SELECT * FROM notes "
            f"WHERE note_id = {_to_surql(note_id)} LIMIT 1;"
        )
        if not isinstance(rows, list) or not rows:
            raise NoteNotFoundError(note_id)

        note_row = rows[0]
        if not isinstance(note_row, dict):
            raise NoteNotFoundError(note_id)

        revision_rows = backend.query(
            "SELECT * FROM note_revisions "
            f"WHERE note_id = {_to_surql(note_id)} ORDER BY version ASC;"
        )
        revisions = self._build_revisions(
            backend,
            note_id=note_id,
            rows=revision_rows if isinstance(revision_rows, list) else [],
        )
        if not revisions:
            raise NoteNotFoundError(note_id)

        return Note(
            note_id=note_id,
            created_at=_datetime_field(note_row, "created_at"),
            revisions=tuple(revisions),
        )

    def _build_revisions(
        self,
        backend: SurrealStorageBackend,
        note_id: str,
        rows: list[Any],
    ) -> list[NoteRevision]:
        related_about = self._load_about(backend, note_id)
        revisions: list[NoteRevision] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            version = _int_field(row, "version")
            provenance = self._load_provenance(backend, note_id, version)
            resolved_about: tuple[ResolvedAboutRef, ...] = ()
            pending_about: tuple[PendingAboutRef, ...] = ()
            if version == _max_version(rows):
                resolved_about, pending_about = related_about

            revisions.append(
                NoteRevision(
                    version=version,
                    content=_string_field(row, "content"),
                    observed_at=_datetime_field(row, "observed_at"),
                    created_at=_datetime_field(row, "created_at"),
                    resolved_about=resolved_about,
                    pending_about=pending_about,
                    provenance=provenance,
                )
            )

        return revisions

    def _load_about(
        self,
        backend: SurrealStorageBackend,
        note_id: str,
    ) -> tuple[tuple[ResolvedAboutRef, ...], tuple[PendingAboutRef, ...]]:
        root_record = _record_id("note_roots", note_id)
        rows = backend.query(
            "SELECT * FROM note_about "
            f"WHERE in = {root_record} FETCH out;"
        )
        resolved: list[ResolvedAboutRef] = []
        pending: list[PendingAboutRef] = []

        if not isinstance(rows, list):
            return (), ()

        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = row.get("out")
            if not isinstance(payload, dict):
                continue
            kind = payload.get("kind")
            if not isinstance(kind, str):
                continue
            if payload.get("resolved") is True:
                resolved.append(
                    ResolvedAboutRef(
                        kind=AboutKind(kind),
                        collection=_string_field(payload, "collection"),
                        key=_string_field(payload, "key"),
                    )
                )
            else:
                label = row.get("label")
                if not isinstance(label, str):
                    label = _string_field(payload, "label")
                pending.append(
                    PendingAboutRef(
                        kind=AboutKind(kind),
                        label=label,
                    )
                )

        return tuple(resolved), tuple(pending)

    def _load_provenance(
        self,
        backend: SurrealStorageBackend,
        note_id: str,
        version: int,
    ) -> Provenance | None:
        revision_record = _record_id("note_revisions", f"{note_id}_v{version}")
        rows = backend.query(
            "SELECT out FROM revision_has_provenance "
            f"WHERE in = {revision_record} LIMIT 1 FETCH out;"
        )
        if not isinstance(rows, list) or not rows:
            return None

        row = rows[0]
        if not isinstance(row, dict):
            return None
        payload = row.get("out")
        if not isinstance(payload, dict):
            return None

        return Provenance(
            writer=_optional_string_field(payload, "writer"),
            session_id=_optional_string_field(payload, "session_id"),
            source_type=_optional_string_field(payload, "source_type"),
            source_ref=_optional_string_field(payload, "source_ref"),
        )

    def _list_existing_note_ids(
        self,
        backend: SurrealStorageBackend,
    ) -> tuple[str, ...]:
        rows = backend.query("SELECT VALUE note_id FROM note_roots;")
        if not isinstance(rows, list):
            return ()
        return tuple(note_id for note_id in rows if isinstance(note_id, str))

    def _load_current_version(
        self,
        backend: SurrealStorageBackend,
        note_id: str,
    ) -> int:
        root_record = _record_id("note_roots", note_id)
        rows = backend.query(
            f"SELECT VALUE current_version FROM ONLY {root_record};"
        )
        if isinstance(rows, int):
            return rows
        if isinstance(rows, list) and rows and isinstance(rows[0], int):
            return rows[0]
        raise NoteNotFoundError(note_id)

    def _create_note_transaction_sql(
        self,
        *,
        note_id: str,
        content: str,
        observed_at: datetime,
        created_at: datetime,
        revision_created_at: datetime,
        resolved_about: tuple[ResolvedAboutRef, ...],
        pending_about: tuple[PendingAboutRef, ...],
        provenance: Provenance | None,
    ) -> str:
        root_record = _record_id("note_roots", note_id)
        revision_record = _record_id("note_revisions", f"{note_id}_v1")
        root_content = {
            "note_id": note_id,
            "current_version": 1,
            "created_at": created_at,
            "updated_at": revision_created_at,
        }
        revision_content = {
            "note_id": note_id,
            "version": 1,
            "content": content,
            "observed_at": observed_at,
            "created_at": revision_created_at,
        }
        statements = [
            "BEGIN TRANSACTION;",
            (
                f"IF record::exists({root_record}) {{ "
                f"THROW {_to_surql(f'{_CREATE_CONFLICT_PREFIX}{note_id}')}; "
                "};"
            ),
            (
                f"CREATE ONLY {root_record} CONTENT "
                f"{_to_surql(root_content)} "
                "RETURN NONE;"
            ),
            (
                f"CREATE ONLY {revision_record} CONTENT "
                f"{_to_surql(revision_content)} "
                "RETURN NONE;"
            ),
            _relation_upsert_sql(
                table="note_has_revision",
                key=f"{note_id}_has_{note_id}_v1",
                in_record=root_record,
                out_record=revision_record,
            ),
            _relation_upsert_sql(
                table="note_current_revision",
                key=f"{note_id}_current_{note_id}_v1",
                in_record=root_record,
                out_record=revision_record,
            ),
            *self._about_relation_sql(
                note_id=note_id,
                root_record=root_record,
                resolved_about=resolved_about,
                pending_about=pending_about,
            ),
            *self._provenance_sql(
                note_id=note_id,
                version=1,
                revision_record=revision_record,
                provenance=provenance,
            ),
            "COMMIT TRANSACTION;",
        ]
        return "\n".join(statements)

    def _patch_note_transaction_sql(
        self,
        *,
        note_id: str,
        expected_version: int,
        next_version: int,
        content: str,
        observed_at: datetime,
        revision_created_at: datetime,
        resolved_about: tuple[ResolvedAboutRef, ...],
        pending_about: tuple[PendingAboutRef, ...],
    ) -> str:
        root_record = _record_id("note_roots", note_id)
        revision_record = _record_id("note_revisions", f"{note_id}_v{next_version}")
        current_edge_key = f"{note_id}_current_{note_id}_v{next_version}"
        current_edge_record = _record_id("note_current_revision", current_edge_key)
        revision_content = {
            "note_id": note_id,
            "version": next_version,
            "content": content,
            "observed_at": observed_at,
            "created_at": revision_created_at,
        }
        conflict_prefix = _to_surql(f"{_VERSION_CONFLICT_PREFIX}{note_id}:")
        previous_revision = _record_id(
            "note_revisions",
            f"{note_id}_v{expected_version}",
        )
        statements = [
            "BEGIN TRANSACTION;",
            (
                f"IF !record::exists({root_record}) {{ "
                f"THROW {_to_surql(f'{_NOTE_NOT_FOUND_PREFIX}{note_id}')}; "
                "};"
            ),
            (
                "LET $updated_root = ("
                f"UPDATE ONLY {root_record} "
                "SET "
                f"current_version = {next_version}, "
                f"updated_at = {_to_surql(revision_created_at)} "
                f"WHERE current_version = {expected_version} "
                "RETURN AFTER"
                ");"
            ),
            (
                "IF !$updated_root { "
                "LET $current_version = "
                f"SELECT VALUE current_version FROM ONLY {root_record}; "
                f"THROW {conflict_prefix} + <string>$current_version; "
                "};"
            ),
            (
                f"CREATE ONLY {revision_record} CONTENT "
                f"{_to_surql(revision_content)} "
                "RETURN NONE;"
            ),
            _relation_upsert_sql(
                table="note_has_revision",
                key=f"{note_id}_has_{note_id}_v{next_version}",
                in_record=root_record,
                out_record=revision_record,
            ),
            (
                f"DELETE note_current_revision WHERE in = {root_record} "
                f"AND id != {current_edge_record} RETURN NONE;"
            ),
            _relation_upsert_sql(
                table="note_current_revision",
                key=current_edge_key,
                in_record=root_record,
                out_record=revision_record,
            ),
            _relation_upsert_sql(
                table="revision_previous",
                key=f"{note_id}_v{next_version}_previous_{note_id}_v{expected_version}",
                in_record=revision_record,
                out_record=previous_revision,
            ),
            *self._about_relation_sql(
                note_id=note_id,
                root_record=root_record,
                resolved_about=resolved_about,
                pending_about=pending_about,
            ),
            "COMMIT TRANSACTION;",
        ]
        return "\n".join(statements)

    def _about_relation_sql(
        self,
        *,
        note_id: str,
        root_record: str,
        resolved_about: tuple[ResolvedAboutRef, ...],
        pending_about: tuple[PendingAboutRef, ...],
    ) -> list[str]:
        statements: list[str] = []

        about_index = 0

        for about_ref in resolved_about:
            about_key = _resolved_about_key(about_ref)
            about_content = {
                "kind": about_ref.kind,
                "identity": _resolved_about_identity(about_ref),
                "collection": about_ref.collection,
                "key": about_ref.key,
                "label": None,
                "resolved": True,
            }
            about_record_var = f"$about_record_{about_index}"
            statements.extend(
                _about_ref_upsert_sql(
                    about_record_var,
                    about_content,
                    match_collection_key=True,
                )
            )
            statements.append(
                _relation_upsert_sql(
                    table="note_about",
                    key=f"{note_id}_about_{about_key}",
                    in_record=root_record,
                    out_record=about_record_var,
                    match_existing_relation=True,
                )
            )
            about_index += 1

        for about_ref in pending_about:
            about_key = _pending_about_key(about_ref)
            about_content = {
                "kind": about_ref.kind,
                "identity": normalize_label(about_ref.label),
                "collection": None,
                "key": None,
                "label": about_ref.label,
                "resolved": False,
            }
            about_record_var = f"$about_record_{about_index}"
            statements.extend(
                _about_ref_upsert_sql(
                    about_record_var,
                    about_content,
                    preserve_existing_label=True,
                )
            )
            statements.append(
                _relation_upsert_sql(
                    table="note_about",
                    key=f"{note_id}_about_{about_key}",
                    in_record=root_record,
                    out_record=about_record_var,
                    extra_content={"label": about_ref.label},
                    match_existing_relation=True,
                )
            )
            about_index += 1

        return statements

    def _provenance_sql(
        self,
        *,
        note_id: str,
        version: int,
        revision_record: str,
        provenance: Provenance | None,
    ) -> list[str]:
        if provenance is None:
            return []
        if not any(
            (
                provenance.writer,
                provenance.session_id,
                provenance.source_type,
                provenance.source_ref,
            )
        ):
            return []

        provenance_key = f"provenance_{note_id}_v{version}"
        provenance_record = _record_id("provenance_records", provenance_key)
        provenance_content = _compact_record_data(
            {
                "writer": provenance.writer,
                "session_id": provenance.session_id,
                "source_type": provenance.source_type,
                "source_ref": provenance.source_ref,
            }
        )
        return [
            f"UPSERT {provenance_record} CONTENT "
            f"{_to_surql(provenance_content)} "
            "RETURN NONE;",
            _relation_upsert_sql(
                table="revision_has_provenance",
                key=f"{note_id}_v{version}_has_provenance",
                in_record=revision_record,
                out_record=provenance_record,
            ),
        ]

    def _list_note_ids_from_view(
        self,
        backend: SurrealStorageBackend,
    ) -> tuple[str, ...]:
        rows = backend.query("SELECT VALUE note_id FROM notes;")
        if not isinstance(rows, list):
            return ()
        return tuple(note_id for note_id in rows if isinstance(note_id, str))


def _string_field(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        msg = f"Expected string field {field!r}, got {value!r}."
        raise SurrealRequestError(msg)
    return value


def _optional_string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"Expected optional string field {field!r}, got {value!r}."
        raise SurrealRequestError(msg)
    return value


def _int_field(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int):
        msg = f"Expected int field {field!r}, got {value!r}."
        raise SurrealRequestError(msg)
    return value


def _datetime_field(payload: dict[str, Any], field: str) -> datetime:
    value = payload.get(field)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    msg = f"Expected datetime field {field!r}, got {value!r}."
    raise SurrealRequestError(msg)


def _resolved_about_key(about_ref: ResolvedAboutRef) -> str:
    return (
        f"about_{about_ref.kind}_"
        f"{_encode_key_component(about_ref.collection)}_"
        f"{_encode_key_component(about_ref.key)}"
    )


def _pending_about_key(about_ref: PendingAboutRef) -> str:
    normalized = normalize_label(about_ref.label)
    return f"about_{about_ref.kind}_{_encode_key_component(normalized)}"


def _resolved_about_identity(about_ref: ResolvedAboutRef) -> str:
    return (
        "resolved:"
        f"{_encode_key_component(about_ref.collection)}:"
        f"{_encode_key_component(about_ref.key)}"
    )


def _encode_key_component(value: str) -> str:
    return binascii.hexlify(value.encode("utf-8")).decode("ascii")


_CREATE_CONFLICT_PREFIX = "mnemosyne.create_conflict:"
_NOTE_NOT_FOUND_PREFIX = "mnemosyne.note_not_found:"
_VERSION_CONFLICT_PREFIX = "mnemosyne.version_conflict:"


def _relation_upsert_sql(
    *,
    table: str,
    key: str,
    in_record: str,
    out_record: str,
    extra_content: dict[str, Any] | None = None,
    match_existing_relation: bool = False,
) -> str:
    relation_record = _record_id(table, key)
    update_content = {"edge_key": key}
    if extra_content is not None:
        update_content.update(extra_content)
    existing_relation_lookup = ""
    target_record = relation_record
    if match_existing_relation:
        existing_relation_lookup = (
            "LET $existing_relation = array::first("
            f"SELECT VALUE id FROM {table} "
            f"WHERE in = {in_record} AND out = {out_record} LIMIT 1"
            ");\n"
        )
        target_record = "$existing_relation"
    return existing_relation_lookup + (
        f"IF record::exists({relation_record}) {{ "
        f"UPDATE ONLY {relation_record} MERGE {_to_surql(update_content)} "
        "RETURN NONE; "
        "} ELSE IF "
        f"{'$existing_relation' if match_existing_relation else 'false'}"
        " {\n"
        f"UPDATE ONLY {target_record} MERGE {_to_surql(update_content)} RETURN NONE; "
        "} ELSE { "
        f"INSERT RELATION INTO {table} "
        f"{_relation_insert_content_sql(key, in_record, out_record, extra_content)} "
        "RETURN NONE; "
        "};"
    )


def _about_ref_upsert_sql(
    record_var: str,
    data: dict[str, Any],
    *,
    preserve_existing_label: bool = False,
    match_collection_key: bool = False,
) -> list[str]:
    kind = _to_surql(data["kind"])
    identity = _to_surql(data["identity"])
    record_id = _record_id(
        "about_refs",
        _about_ref_record_key(data),
    )
    create_data = _compact_record_data(data)
    update_data = create_data
    if preserve_existing_label:
        update_data = {
            key: value for key, value in create_data.items() if key != "label"
        }
    identity_match = f"identity = {identity}"
    if match_collection_key:
        collection = _to_surql(data["collection"])
        key = _to_surql(data["key"])
        identity_match = (
            f"({identity_match} OR (collection = {collection} AND key = {key}))"
        )
    existing_var = f"{record_var}_existing"
    return [
        (
            f"LET {existing_var} = array::first(SELECT VALUE id FROM about_refs "
            f"WHERE kind = {kind} AND {identity_match} LIMIT 1);"
        ),
        (
            f"IF {existing_var} {{ "
            f"UPDATE ONLY {existing_var} "
            f"MERGE {_to_surql(update_data)} RETURN NONE; "
            "} ELSE { "
            f"CREATE ONLY {record_id} "
            f"CONTENT {_to_surql(create_data)} RETURN NONE; "
            "};"
        ),
        (
            f"LET {record_var} = IF {existing_var} "
            f"{{ {existing_var} }} ELSE {{ {record_id} }};"
        ),
    ]


def _compact_record_data(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def _relation_insert_content_sql(
    key: str,
    in_record: str,
    out_record: str,
    extra_content: dict[str, Any] | None,
) -> str:
    fields = [
        f"id: {_to_surql(key)}",
        f"in: {in_record}",
        f"out: {out_record}",
        f"edge_key: {_to_surql(key)}",
    ]
    if extra_content is not None:
        for name, value in extra_content.items():
            fields.append(f"{name}: {_to_surql(value)}")
    return "{ " + ", ".join(fields) + " }"


def _about_ref_record_key(data: dict[str, Any]) -> str:
    collection = data.get("collection")
    key = data.get("key")
    label = data.get("label")

    if isinstance(collection, str) and isinstance(key, str):
        return _resolved_about_key(
            ResolvedAboutRef(
                kind=AboutKind(str(data["kind"])),
                collection=collection,
                key=key,
            )
        )

    if isinstance(label, str):
        return _pending_about_key(
            PendingAboutRef(
                kind=AboutKind(str(data["kind"])),
                label=label,
            )
        )

    msg = f"Unsupported about ref payload: {data!r}"
    raise ValueError(msg)


def _is_retryable_create_conflict(exc: SurrealRequestError, note_id: str) -> bool:
    message = str(exc)
    if f"{_CREATE_CONFLICT_PREFIX}{note_id}" in message:
        return True
    duplicate_markers = ("already", "exists", "contains")
    return (
        any(marker in message.lower() for marker in duplicate_markers)
        and (
            f"note_roots:{note_id}" in message
            or f"note_revisions:{note_id}_v1" in message
            or "note_roots_note_id_unique" in message
        )
    )


def _is_retryable_patch_conflict(
    exc: SurrealRequestError,
    note_id: str,
    next_version: int,
) -> bool:
    message = str(exc).lower()
    if not any(marker in message for marker in ("already", "exists", "contains")):
        return False
    return (
        f"note_revisions:{note_id}_v{next_version}".lower() in message
        or "note_revisions_note_id_version_unique" in message
        or f"note_current_revision:{note_id}_current_{note_id}_v{next_version}".lower()
        in message
        or "note_current_revision_in_unique" in message
    )


def _is_retryable_about_ref_conflict(exc: SurrealRequestError) -> bool:
    message = str(exc).lower()
    if not any(
        marker in message
        for marker in ("already", "exists", "contains", "duplicate")
    ):
        return False
    return "about_refs:" in message or "about_refs_kind_identity" in message


def _parse_version_conflict(
    exc: SurrealRequestError,
    note_id: str,
) -> int | None:
    match = re.search(
        re.escape(f"{_VERSION_CONFLICT_PREFIX}{note_id}:") + r"(\d+)",
        str(exc),
    )
    if match is None:
        return None
    return int(match.group(1))


def _is_note_not_found(exc: SurrealRequestError, note_id: str) -> bool:
    return f"{_NOTE_NOT_FOUND_PREFIX}{note_id}" in str(exc)


def _max_version(rows: list[Any]) -> int:
    versions = [
        row.get("version")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("version"), int)
    ]
    return max(versions, default=0)


__all__ = ["SurrealNotesRepository"]
