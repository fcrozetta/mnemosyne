from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.notes import (
    CreateNoteInput,
    InvalidNotePatchError,
    Note,
    NoteContext,
    NoteNotFoundError,
    NoteRevision,
    NoteSearchResult,
    PatchNoteInput,
    VersionConflictError,
    append_addendum,
    content_preview,
    merge_about_refs,
    next_note_id,
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
)
from app.storage.in_memory import InMemoryStorageBackend


@dataclass(slots=True)
class InMemoryNotesRepository(NotesRepository):
    """Local repository skeleton backed by an in-memory storage catalog."""

    storage: InMemoryStorageBackend = field(default_factory=InMemoryStorageBackend)
    notes: dict[str, Note] = field(default_factory=dict)
    layout: StorageLayout = ALPHA_STORAGE_LAYOUT

    def initialize_storage(self) -> StorageBootstrapResult:
        return StorageBootstrapper(self.storage, self.layout).initialize()

    def storage_initialized(self) -> bool:
        return self.storage.matches(self.layout)

    def create_note(self, note: CreateNoteInput) -> Note:
        self._ensure_initialized()

        observed_at = note.observed_at or utc_now()
        created_at = observed_at
        revision_created_at = utc_now()
        note_id = next_note_id(self.notes)
        resolved_about, pending_about = split_about_refs(
            merge_about_refs((), note.about)
        )
        revision = NoteRevision(
            version=1,
            content=note.content,
            observed_at=observed_at,
            created_at=revision_created_at,
            resolved_about=resolved_about,
            pending_about=pending_about,
            provenance=note.provenance,
        )
        created_note = Note(
            note_id=note_id,
            created_at=created_at,
            revisions=(revision,),
        )
        self.notes[note_id] = created_note
        return created_note

    def get_note(self, note_id: str) -> Note:
        self._ensure_initialized()

        note = self.notes.get(note_id)
        if note is None:
            raise NoteNotFoundError(note_id)
        return note

    def search_notes(self, query: str, limit: int = 5) -> tuple[NoteSearchResult, ...]:
        self._ensure_initialized()

        matches: list[NoteSearchResult] = []
        for note in self.notes.values():
            latest = note.latest_revision
            if latest is None:
                continue
            score = score_content_match(latest.content, query)
            if score <= 0:
                continue
            matches.append(
                NoteSearchResult(
                    note_id=note.note_id,
                    version=latest.version,
                    content_preview=content_preview(latest.content),
                    observed_at=latest.observed_at,
                    score=score,
                )
            )

        matches.sort(
            key=lambda item: (
                item.score,
                _timestamp(item.observed_at),
                item.note_id,
            ),
            reverse=True,
        )
        return tuple(matches[:limit])

    def patch_note(self, note_id: str, patch: PatchNoteInput) -> Note:
        self._ensure_initialized()

        current_note = self.get_note(note_id)
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

        revision_created_at = utc_now()
        observed_at = patch.observed_at or latest.observed_at
        merged_about = merge_about_refs(
            (*latest.resolved_about, *latest.pending_about),
            patch.add_about,
        )
        resolved_about, pending_about = split_about_refs(merged_about)
        new_revision = NoteRevision(
            version=latest.version + 1,
            content=append_addendum(latest.content, patch.addendum)
            if patch.addendum is not None
            else latest.content,
            observed_at=observed_at,
            created_at=revision_created_at,
            resolved_about=resolved_about,
            pending_about=pending_about,
            provenance=None,
        )
        updated_note = Note(
            note_id=current_note.note_id,
            created_at=current_note.created_at,
            revisions=(*current_note.revisions, new_revision),
        )
        self.notes[note_id] = updated_note
        return updated_note

    def get_note_context(self, note_id: str, limit: int = 5) -> NoteContext:
        anchor = self.get_note(note_id)
        related: list[NoteSearchResult] = []

        for candidate in self.notes.values():
            if candidate.note_id == note_id:
                continue

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
                _timestamp(item.observed_at),
                item.note_id,
            ),
            reverse=True,
        )
        return NoteContext(note=anchor, related_notes=tuple(related[:limit]))

    def _ensure_initialized(self) -> None:
        if not self.storage_initialized():
            self.initialize_storage()


def _timestamp(value: datetime) -> float:
    return value.timestamp()


__all__ = ["InMemoryNotesRepository"]
