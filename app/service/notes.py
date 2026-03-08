from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.notes import (
    NoteRecord,
    NoteWritePayload,
    PendingAboutRecord,
    ResolvedAboutRecord,
)
from app.repository.notes import NotesRepository, RepositoryVersionConflictError
from app.schemas.errors import ErrorDetail
from app.schemas.notes import (
    CreateNoteRequest,
    NoteSearchResultView,
    NoteView,
    PatchNoteRequest,
    PendingAboutView,
    PutNoteRequest,
    ResolvedAboutInput,
    ResolvedAboutView,
    UnresolvedAboutInput,
)


class ServiceError(Exception):
    """Base service-layer error."""

    error: str = "service_error"
    status_code: int = 500

    def __init__(
        self, message: str, *, details: list[ErrorDetail] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class NoteNotFoundError(ServiceError):
    """Raised when a note cannot be found."""

    error = "note_not_found"
    status_code = 404


class NoteVersionConflictError(ServiceError):
    """Raised when an optimistic concurrency check fails."""

    error = "version_conflict"
    status_code = 409


class NotePatchError(ServiceError):
    """Raised when a note patch request is semantically invalid."""

    error = "invalid_note_patch"
    status_code = 400


@dataclass(slots=True)
class NotesService:
    """Application service for note behavior and view mapping."""

    repository: NotesRepository

    def create_note(self, payload: CreateNoteRequest) -> NoteView:
        record = self.repository.create_note(
            NoteWritePayload(
                content=payload.content,
                observed_at=payload.observed_at or datetime.now(UTC),
                resolved_about=self._resolved_about_records(payload.about),
                pending_about=self._pending_about_records(payload.about),
                source_channel=payload.source_channel,
                event_kind="manual_note",
            )
        )
        return self._to_view(record)

    def get_note(self, note_id: str) -> NoteView:
        note = self.repository.get_note(note_id)
        if note is None:
            raise self._not_found(note_id)
        return self._to_view(note)

    def search_notes(self, query: str, limit: int = 5) -> list[NoteSearchResultView]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []

        return [
            NoteSearchResultView(
                note_id=item.note_id,
                version=item.version,
                content_preview=item.latest_content,
                observed_at=item.observed_at,
                score=round(item.score, 4),
            )
            for item in self.repository.search_notes(normalized_query, limit=limit)
        ]

    def put_note(self, note_id: str, payload: PutNoteRequest) -> NoteView:
        current = self.get_note(note_id)

        try:
            record = self.repository.create_revision(
                note_id,
                NoteWritePayload(
                    content=payload.content,
                    observed_at=payload.observed_at or current.observed_at,
                    resolved_about=self._resolved_about_records(payload.about),
                    pending_about=self._pending_about_records(payload.about),
                    event_kind="manual_edit",
                ),
                expected_version=payload.version,
            )
        except RepositoryVersionConflictError as exc:
            self._raise_version_conflict(
                note_id, exc.current_version, exc.expected_version
            )
        return self._to_view(record)

    def patch_note(self, note_id: str, payload: PatchNoteRequest) -> NoteView:
        current = self._get_record(note_id)

        merged_resolved = self._dedupe_resolved_about(
            current.resolved_about + self._resolved_about_records(payload.add_about)
        )
        merged_pending = self._dedupe_pending_about(
            current.latest_revision.pending_about
            + self._pending_about_records(payload.add_about)
        )

        try:
            record = self.repository.create_revision(
                note_id,
                NoteWritePayload(
                    content=self._apply_addendum(
                        current.latest_revision.content, payload.addendum
                    ),
                    observed_at=(
                        payload.observed_at or current.latest_revision.observed_at
                    ),
                    resolved_about=merged_resolved,
                    pending_about=merged_pending,
                    event_kind="manual_patch",
                ),
                expected_version=payload.version,
            )
        except RepositoryVersionConflictError as exc:
            self._raise_version_conflict(
                note_id, exc.current_version, exc.expected_version
            )
        return self._to_view(record)

    def _raise_version_conflict(
        self, note_id: str, current_version: int, requested_version: int
    ) -> None:
        raise NoteVersionConflictError(
            f"Note {note_id} is at version {current_version}, not {requested_version}.",
            details=[
                ErrorDetail(
                    field="version",
                    message="Version does not match latest note version.",
                    code="version_conflict",
                    context={
                        "note_id": note_id,
                        "current_version": current_version,
                        "requested_version": requested_version,
                    },
                )
            ],
        )

    def _apply_addendum(self, current_content: str, addendum: str | None) -> str:
        if addendum is None:
            return current_content
        return f"{current_content}\n\nAddendum:\n{addendum}"

    def _resolved_about_records(
        self, about: list[ResolvedAboutInput | UnresolvedAboutInput]
    ) -> list[ResolvedAboutRecord]:
        resolved = [
            ResolvedAboutRecord(
                kind=target.kind,
                collection=target.ref.collection,
                key=target.ref.key,
            )
            for target in about
            if isinstance(target, ResolvedAboutInput)
        ]
        return self._dedupe_resolved_about(resolved)

    def _pending_about_records(
        self, about: list[ResolvedAboutInput | UnresolvedAboutInput]
    ) -> list[PendingAboutRecord]:
        pending = [
            PendingAboutRecord(kind=target.kind, label=target.label)
            for target in about
            if isinstance(target, UnresolvedAboutInput)
        ]
        return self._dedupe_pending_about(pending)

    def _dedupe_resolved_about(
        self, about: list[ResolvedAboutRecord]
    ) -> list[ResolvedAboutRecord]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[ResolvedAboutRecord] = []

        for target in about:
            identity = (target.kind, target.collection, target.key)
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(target)

        return deduped

    def _dedupe_pending_about(
        self, about: list[PendingAboutRecord]
    ) -> list[PendingAboutRecord]:
        seen: set[tuple[str, str]] = set()
        deduped: list[PendingAboutRecord] = []

        for target in about:
            identity = (target.kind, self._normalize_label(target.label))
            if identity in seen:
                continue
            seen.add(identity)
            deduped.append(PendingAboutRecord(kind=target.kind, label=target.label))

        return deduped

    def _normalize_label(self, label: str) -> str:
        return " ".join(label.split()).lower()

    def _not_found(self, note_id: str) -> NoteNotFoundError:
        return NoteNotFoundError(
            f"Note {note_id} was not found.",
            details=[
                ErrorDetail(
                    field="note_id",
                    message="No note exists for the provided note_id.",
                    code="note_not_found",
                    context={"note_id": note_id},
                )
            ],
        )

    def _get_record(self, note_id: str) -> NoteRecord:
        note = self.repository.get_note(note_id)
        if note is None:
            raise self._not_found(note_id)
        return note

    def _to_view(self, record: NoteRecord) -> NoteView:
        return NoteView(
            note_id=record.note_id,
            version=record.version,
            content=record.latest_revision.content,
            observed_at=record.latest_revision.observed_at,
            created_at=record.latest_revision.created_at,
            resolved_about=[
                ResolvedAboutView(
                    kind=target.kind,
                    collection=target.collection,
                    key=target.key,
                )
                for target in record.resolved_about
            ],
            pending_about=[
                PendingAboutView(kind=target.kind, label=target.label)
                for target in record.latest_revision.pending_about
            ],
        )


__all__ = [
    "NotesService",
    "NoteNotFoundError",
    "NotePatchError",
    "NoteVersionConflictError",
    "ServiceError",
]
