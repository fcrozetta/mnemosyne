from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models.notes import (
    AboutEdge,
    BelongsToEdge,
    EventDocument,
    LatestRevisionEdge,
    NoteDocument,
    NoteRecord,
    NoteRevisionDocument,
    NoteSearchCandidateRecord,
    NoteWritePayload,
    OriginatesFromEdge,
    SupersedesEdge,
)
from app.repository.notes import NotesRepository, RepositoryVersionConflictError


@dataclass(slots=True)
class InMemoryNotesRepository(NotesRepository):
    """Temporary repository that mimics note persistence without Arango."""

    _note_counter: int = 0
    _revision_counter: int = 0
    _event_counter: int = 0
    _edge_counter: int = 0
    _notes: dict[str, NoteDocument] = field(default_factory=dict)
    _revisions_by_note_id: dict[str, list[NoteRevisionDocument]] = field(
        default_factory=dict
    )
    _events_by_revision_key: dict[str, EventDocument] = field(default_factory=dict)
    _about_by_revision_key: dict[str, list[AboutEdge]] = field(default_factory=dict)
    _belongs_to_by_revision_key: dict[str, BelongsToEdge] = field(default_factory=dict)
    _latest_revision_by_note_id: dict[str, LatestRevisionEdge] = field(
        default_factory=dict
    )
    _supersedes_by_revision_key: dict[str, SupersedesEdge] = field(default_factory=dict)
    _originates_from_by_revision_key: dict[str, OriginatesFromEdge] = field(
        default_factory=dict
    )
    def create_note(self, payload: NoteWritePayload) -> NoteRecord:
        self._note_counter += 1
        note_id = f"note_{self._note_counter:03d}"
        now = datetime.now(UTC)

        note = NoteDocument(
            _key=note_id,
            note_id=note_id,
            created_at=now,
            created_by=payload.created_by,
            updated_at=now,
            observed_at=payload.observed_at,
        )

        self._notes[note_id] = note
        self._revisions_by_note_id[note_id] = []
        return self.create_revision(note_id, payload)

    def get_note(self, note_id: str) -> NoteRecord | None:
        note = self._notes.get(note_id)
        revisions = self._revisions_by_note_id.get(note_id)
        if note is None or not revisions:
            return None

        latest_revision = revisions[-1]
        about_edges = self._about_by_revision_key.get(latest_revision.key, [])

        return NoteRecord(
            note=note,
            latest_revision=latest_revision,
            resolved_about=[
                self._resolved_about_from_edge(edge) for edge in about_edges
            ],
        )

    def create_revision(
        self,
        note_id: str,
        payload: NoteWritePayload,
        expected_version: int | None = None,
    ) -> NoteRecord:
        note = self._notes.get(note_id)
        revisions = self._revisions_by_note_id.get(note_id)
        if note is None or revisions is None:
            raise KeyError(note_id)

        current_version = len(revisions)
        if expected_version is not None and current_version != expected_version:
            raise RepositoryVersionConflictError(expected_version, current_version)

        self._revision_counter += 1
        revision_key = f"nr_{self._revision_counter:03d}"
        revision_number = len(revisions) + 1
        now = datetime.now(UTC)

        revision = NoteRevisionDocument(
            _key=revision_key,
            note_id=note_id,
            revision=revision_number,
            content=payload.content,
            observed_at=payload.observed_at,
            pending_about=payload.pending_about,
            created_at=now,
            created_by=payload.created_by,
        )
        revisions.append(revision)

        self._belongs_to_by_revision_key[revision.key] = BelongsToEdge(
            _key=self._next_edge_key(),
            _from=f"note_revision/{revision.key}",
            _to=f"note/{note.key}",
            created_at=now,
            created_by=payload.created_by,
        )

        self._latest_revision_by_note_id[note_id] = LatestRevisionEdge(
            _key=self._next_edge_key(),
            _from=f"note/{note.key}",
            _to=f"note_revision/{revision.key}",
            created_at=now,
            created_by=payload.created_by,
        )

        if len(revisions) > 1:
            previous = revisions[-2]
            self._supersedes_by_revision_key[revision.key] = SupersedesEdge(
                _key=self._next_edge_key(),
                _from=f"note_revision/{revision.key}",
                _to=f"note_revision/{previous.key}",
                created_at=now,
                created_by=payload.created_by,
            )

        event = self._create_event(payload, now)
        self._events_by_revision_key[revision.key] = event
        self._originates_from_by_revision_key[revision.key] = OriginatesFromEdge(
            _key=self._next_edge_key(),
            _from=f"note_revision/{revision.key}",
            _to=f"event/{event.key}",
            created_at=now,
            created_by=payload.created_by,
        )

        self._about_by_revision_key[revision.key] = [
            AboutEdge(
                _key=self._next_edge_key(),
                _from=f"note_revision/{revision.key}",
                _to=f"{target.collection}/{target.key}",
                kind=target.kind,
                created_at=now,
                created_by=payload.created_by,
            )
            for target in payload.resolved_about
        ]

        self._notes[note_id] = note.model_copy(
            update={
                "current_content": revision.content,
                "pending_about_labels": [
                    target.label for target in payload.pending_about
                ],
                "resolved_about_labels": [
                    self._resolved_label(target.collection, target.key)
                    for target in payload.resolved_about
                ],
                "aliases": self._aliases_for_content(revision.content),
                "updated_at": revision.created_at,
                "observed_at": revision.observed_at,
            }
        )

        return self.get_note(note_id)  # type: ignore[return-value]

    def search_notes(
        self, query: str, limit: int = 5
    ) -> list[NoteSearchCandidateRecord]:
        query = self._normalize_text(query)
        if not query:
            return []

        candidates: list[NoteSearchCandidateRecord] = []
        for note in self._notes.values():
            score = self._score_search_document(note, query)
            if score <= 0:
                continue
            candidates.append(
                NoteSearchCandidateRecord(
                    note_id=note.note_id,
                    version=len(self._revisions_by_note_id[note.note_id]),
                    latest_content=note.current_content,
                    score=score,
                    updated_at=note.updated_at or note.created_at,
                    observed_at=note.observed_at or note.created_at,
                )
            )

        candidates.sort(key=lambda item: (item.score, item.updated_at), reverse=True)
        return candidates[:limit]

    def _create_event(self, payload: NoteWritePayload, now: datetime) -> EventDocument:
        self._event_counter += 1
        return EventDocument(
            _key=f"ev_{self._event_counter:03d}",
            event_kind=payload.event_kind,
            source_system="manual_notes",
            source_channel=payload.source_channel,
            created_at=now,
            created_by=payload.created_by,
        )

    def _next_edge_key(self) -> str:
        self._edge_counter += 1
        return f"edge_{self._edge_counter:04d}"

    def _resolved_about_from_edge(self, edge: AboutEdge):
        collection, key = edge.to_id.split("/", maxsplit=1)
        from app.models.notes import ResolvedAboutRecord

        return ResolvedAboutRecord(kind=edge.kind, collection=collection, key=key)

    def _score_search_document(self, note: NoteDocument, query: str) -> float:
        score = 0.0
        haystacks = [
            (note.current_content, 3.0),
            (" ".join(note.pending_about_labels), 2.0),
            (" ".join(note.resolved_about_labels), 2.0),
            (" ".join(note.aliases), 1.5),
        ]

        for text, weight in haystacks:
            normalized = self._normalize_text(text)
            if not normalized:
                continue
            if query in normalized:
                score += weight
            overlap = len(set(query.split()) & set(normalized.split()))
            score += overlap * (weight / 10)

        return score

    def _aliases_for_content(self, content: str) -> list[str]:
        lowered = self._normalize_text(content)
        aliases: list[str] = []
        if "shirt" in lowered:
            aliases.append("shirt note")
        if "ink" in lowered:
            aliases.append("ink note")
        if "follow up" in lowered:
            aliases.append("follow up note")
        return aliases

    def _resolved_label(self, collection: str, key: str) -> str:
        return f"{collection} {key}".replace("_", " ")

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.lower().split())


__all__ = ["InMemoryNotesRepository"]
