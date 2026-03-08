from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from arango.exceptions import TransactionAbortError

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
    ResolvedAboutRecord,
    SupersedesEdge,
)
from app.repository.notes import NotesRepository, RepositoryVersionConflictError


class ArangoNotesRepository(NotesRepository):
    """Arango-backed notes repository."""

    def __init__(self, db) -> None:
        self.db = db

    def create_note(self, payload: NoteWritePayload) -> NoteRecord:
        now = datetime.now(UTC)
        note_id = f"note_{uuid4().hex}"
        note = NoteDocument(
            _key=note_id,
            note_id=note_id,
            created_at=now,
            created_by=payload.created_by,
        )
        self._note_collection().insert(self._dump(note))
        return self.create_revision(note_id, payload)

    def get_note(self, note_id: str) -> NoteRecord | None:
        note_doc = self._note_collection().get(note_id)
        if note_doc is None:
            return None

        latest_edge = self._latest_revision_collection().get(
            self._latest_revision_edge_key(note_id)
        )
        if latest_edge is None:
            return None

        revision_id = latest_edge["_to"]
        revision_key = revision_id.split("/", maxsplit=1)[1]
        revision_doc = self._note_revision_collection().get(revision_key)
        if revision_doc is None:
            return None

        about_edges = list(
            self.db.aql.execute(
                """
                FOR edge IN about
                  FILTER edge._from == @revision_id
                  RETURN edge
                """,
                bind_vars={"revision_id": revision_id},
            )
        )

        return NoteRecord(
            note=NoteDocument.model_validate(self._strip_arango_metadata(note_doc)),
            latest_revision=NoteRevisionDocument.model_validate(
                self._strip_arango_metadata(revision_doc)
            ),
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
        note_doc = self._note_collection().get(note_id)
        if note_doc is None:
            raise KeyError(note_id)

        tx = self.db.begin_transaction(
            read=["note"],
            write=[
                "note",
                "note_revision",
                "belongs_to",
                "latest_revision",
                "supersedes",
                "event",
                "originates_from",
                "about",
            ],
            allow_implicit=False,
        )

        try:
            current = self._get_note_from_db(tx, note_id)
            current_version = 0 if current is None else current.version
            if expected_version is not None and current_version != expected_version:
                raise RepositoryVersionConflictError(expected_version, current_version)

            revision_number = current_version + 1
            now = datetime.now(UTC)
            revision_key = f"nr_{uuid4().hex}"

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
            tx.collection("note_revision").insert(self._dump(revision))

            tx.collection("belongs_to").insert(
                self._dump(
                    BelongsToEdge(
                        _key=f"belongs_to__{revision.key}",
                        _from=f"note_revision/{revision.key}",
                        _to=f"note/{note_id}",
                        created_at=now,
                        created_by=payload.created_by,
                    )
                )
            )

            tx.collection("latest_revision").insert(
                self._dump(
                    LatestRevisionEdge(
                        _key=self._latest_revision_edge_key(note_id),
                        _from=f"note/{note_id}",
                        _to=f"note_revision/{revision.key}",
                        created_at=now,
                        created_by=payload.created_by,
                    )
                ),
                overwrite=True,
                overwrite_mode="replace",
            )

            if current is not None:
                tx.collection("supersedes").insert(
                    self._dump(
                        SupersedesEdge(
                            _key=f"supersedes__{revision.key}",
                            _from=f"note_revision/{revision.key}",
                            _to=f"note_revision/{current.latest_revision.key}",
                            created_at=now,
                            created_by=payload.created_by,
                        )
                    )
                )

            event = EventDocument(
                _key=f"ev_{uuid4().hex}",
                event_kind=payload.event_kind,
                source_system="manual_notes",
                source_channel=payload.source_channel,
                created_at=now,
                created_by=payload.created_by,
            )
            tx.collection("event").insert(self._dump(event))

            tx.collection("originates_from").insert(
                self._dump(
                    OriginatesFromEdge(
                        _key=f"originates_from__{revision.key}",
                        _from=f"note_revision/{revision.key}",
                        _to=f"event/{event.key}",
                        created_at=now,
                        created_by=payload.created_by,
                    )
                )
            )

            for target in payload.resolved_about:
                edge_key = self._about_edge_key(revision.key, target)
                tx.collection("about").insert(
                    self._dump(
                        AboutEdge(
                            _key=edge_key,
                            _from=f"note_revision/{revision.key}",
                            _to=f"{target.collection}/{target.key}",
                            kind=target.kind,
                            created_at=now,
                            created_by=payload.created_by,
                        )
                    ),
                    overwrite=True,
                    overwrite_mode="replace",
                )

            current_note = NoteDocument.model_validate(
                self._strip_arango_metadata(note_doc)
            )
            updated_note = current_note.model_copy(
                update={
                    "current_content": revision.content,
                    "pending_about_labels": [
                        item.label for item in payload.pending_about
                    ],
                    "resolved_about_labels": [
                        self._label_for_target(target.collection, target.key)
                        for target in payload.resolved_about
                    ],
                    "aliases": self._aliases_for_content(revision.content),
                    "updated_at": revision.created_at,
                    "observed_at": revision.observed_at,
                }
            )
            tx.collection("note").update(
                self._dump(updated_note),
                keep_none=False,
            )

            tx.commit_transaction()
        except Exception:
            try:
                tx.abort_transaction()
            except TransactionAbortError:
                pass
            raise

        record = self.get_note(note_id)
        if record is None:
            raise KeyError(note_id)
        return record

    def search_notes(
        self, query: str, limit: int = 5
    ) -> list[NoteSearchCandidateRecord]:
        query = " ".join(query.lower().split())
        if not query:
            return []

        cursor = self.db.aql.execute(
            """
            FOR doc IN note_current_view
              SEARCH
                BOOST(PHRASE(doc.current_content, @query, 'text_en'), 4.0) OR
                BOOST(
                  TOKENS(@query, 'text_en') AT LEAST (1) == doc.current_content,
                  2.5
                ) OR
                BOOST(
                  TOKENS(@query, 'text_en') AT LEAST (1) == doc.pending_about_labels,
                  2.0
                ) OR
                BOOST(
                  TOKENS(@query, 'text_en') AT LEAST (1) == doc.resolved_about_labels,
                  2.0
                ) OR
                BOOST(TOKENS(@query, 'text_en') AT LEAST (1) == doc.aliases, 1.5)
              LET latest_rev = FIRST(
                FOR edge IN latest_revision
                  FILTER edge._from == CONCAT('note/', doc._key)
                  FOR rev IN note_revision
                    FILTER rev._id == edge._to
                    LIMIT 1
                    RETURN rev
              )
              LET score = BM25(doc)
              SORT score DESC, doc.updated_at DESC
              LIMIT @limit
              RETURN {
                note_id: doc.note_id,
                version: latest_rev.revision,
                latest_content: doc.current_content,
                score,
                updated_at: doc.updated_at,
                observed_at: doc.observed_at
              }
            """,
            bind_vars={"query": query, "limit": limit},
        )

        return [NoteSearchCandidateRecord.model_validate(item) for item in cursor]

    def _get_note_from_db(self, db, note_id: str) -> NoteRecord | None:
        note_doc = db.collection("note").get(note_id)
        if note_doc is None:
            return None

        latest_edge = db.collection("latest_revision").get(
            self._latest_revision_edge_key(note_id)
        )
        if latest_edge is None:
            return None

        revision_id = latest_edge["_to"]
        revision_key = revision_id.split("/", maxsplit=1)[1]
        revision_doc = db.collection("note_revision").get(revision_key)
        if revision_doc is None:
            return None

        about_edges = list(
            db.aql.execute(
                """
                FOR edge IN about
                  FILTER edge._from == @revision_id
                  RETURN edge
                """,
                bind_vars={"revision_id": revision_id},
            )
        )

        return NoteRecord(
            note=NoteDocument.model_validate(self._strip_arango_metadata(note_doc)),
            latest_revision=NoteRevisionDocument.model_validate(
                self._strip_arango_metadata(revision_doc)
            ),
            resolved_about=[
                self._resolved_about_from_edge(edge) for edge in about_edges
            ],
        )

    def _about_edge_key(
        self, revision_key: str, target: ResolvedAboutRecord
    ) -> str:
        return (
            f"about__{revision_key}__{target.kind}__"
            f"{target.collection}__{target.key}"
        )

    def _latest_revision_edge_key(self, note_id: str) -> str:
        return f"latest_revision__{note_id}"

    def _resolved_about_from_edge(self, edge: dict[str, object]) -> ResolvedAboutRecord:
        collection, key = str(edge["_to"]).split("/", maxsplit=1)
        return ResolvedAboutRecord(
            kind=str(edge["kind"]),
            collection=collection,
            key=key,
        )

    def _dump(self, model) -> dict[str, object]:
        return model.model_dump(by_alias=True, mode="json")

    def _strip_arango_metadata(self, document: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in document.items()
            if key not in {"_id", "_rev"}
        }

    def _note_collection(self):
        return self.db.collection("note")

    def _note_revision_collection(self):
        return self.db.collection("note_revision")

    def _event_collection(self):
        return self.db.collection("event")

    def _belongs_to_collection(self):
        return self.db.collection("belongs_to")

    def _latest_revision_collection(self):
        return self.db.collection("latest_revision")

    def _supersedes_collection(self):
        return self.db.collection("supersedes")

    def _originates_from_collection(self):
        return self.db.collection("originates_from")

    def _about_collection(self):
        return self.db.collection("about")

    def _aliases_for_content(self, content: str) -> list[str]:
        lowered = " ".join(content.lower().split())
        aliases: list[str] = []
        if "shirt" in lowered:
            aliases.append("shirt note")
        if "ink" in lowered:
            aliases.append("ink note")
        if "follow up" in lowered:
            aliases.append("follow up note")
        return aliases

    def _label_for_target(self, collection: str, key: str) -> str:
        if collection == "item":
            snapshot = next(
                self.db.aql.execute(
                    """
                    FOR snap IN product_snapshot
                      FILTER CONCAT('item/', @key) IN (
                        FOR edge IN describes
                          FILTER edge._from == CONCAT('product_snapshot/', snap._key)
                          RETURN edge._to
                      )
                      LIMIT 1
                      RETURN snap
                    """,
                    bind_vars={"key": key},
                ),
                None,
            )
            if snapshot is not None:
                attributes = snapshot.get("attributes", {})
                values = [str(value) for value in attributes.values()]
                return " ".join(values)

        doc = self.db.collection(collection).get(key)
        if doc is None:
            return f"{collection} {key}".replace("_", " ")

        for field in ("display_name", "title", "name", "provider", "kind", "note_id"):
            if field in doc and doc[field]:
                return str(doc[field])

        return f"{collection} {key}".replace("_", " ")


__all__ = ["ArangoNotesRepository"]
