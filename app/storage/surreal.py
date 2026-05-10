from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.storage.bootstrap import (
    FieldSpec,
    IndexSpec,
    StorageLayout,
    StorageLayoutConflict,
    TableKind,
    TableSpec,
    ViewSpec,
)


class SurrealRequestError(RuntimeError):
    """Raised when SurrealDB rejects a bootstrap request."""


@dataclass(frozen=True, slots=True)
class SurrealStorageBackend:
    base_url: str
    namespace: str
    database: str
    username: str = "root"
    password: str = "root"
    timeout_seconds: float = 5.0
    token: str | None = None

    def wait_until_ready(self, timeout_seconds: float = 30.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error = "server was not ready"

        while time.monotonic() < deadline:
            try:
                status, _ = self._send(
                    "GET",
                    "/version",
                    authenticate=False,
                    include_namespace_database=False,
                )
                if status == 200:
                    return
                last_error = f"HTTP {status}"
            except (SurrealRequestError, OSError, URLError) as exc:
                last_error = str(exc)

            time.sleep(0.5)

        msg = f"Timed out waiting for SurrealDB at {self.base_url}: {last_error}"
        raise TimeoutError(msg)

    def sign_in(self) -> SurrealStorageBackend:
        status, payload = self._send(
            "POST",
            "/signin",
            body=_to_json(
                {
                    "ns": self.namespace,
                    "db": self.database,
                    "user": self.username,
                    "pass": self.password,
                }
            ).encode(),
            content_type="application/json",
            authenticate=False,
            include_namespace_database=False,
        )
        if status != 200:
            msg = f"SurrealDB signin returned HTTP {status}: {payload!r}"
            raise SurrealRequestError(msg)
        if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
            msg = f"SurrealDB signin returned unexpected payload: {payload!r}"
            raise SurrealRequestError(msg)
        return replace(self, token=payload["token"])

    def ensure_namespace_database(self) -> None:
        self.query(
            f"DEFINE NAMESPACE IF NOT EXISTS {self.namespace};\n"
            f"DEFINE DATABASE IF NOT EXISTS {self.database};"
        )

    def ensure_database_user(
        self,
        username: str,
        password: str,
        *,
        roles: tuple[str, ...] = ("EDITOR",),
    ) -> bool:
        users = self._database_info().get("users", {})
        created = username not in users
        self.query(_define_database_user_sql(username, password, roles))
        return created

    def ensure_table(self, spec: TableSpec) -> bool:
        tables = self._database_info().get("tables", {})
        definition = tables.get(spec.name)
        if definition is not None:
            self._validate_table(spec, definition)
            return False

        self.query(f"DEFINE TABLE IF NOT EXISTS {spec.name} {_table_clause(spec)};")
        return True

    def ensure_field(self, spec: FieldSpec) -> bool:
        fields = self._table_info(spec.table).get("fields", {})
        definition = fields.get(spec.name)
        if definition is not None:
            self._validate_field(spec, definition)
            return False

        self.query(
            f"DEFINE FIELD IF NOT EXISTS {spec.name} "
            f"ON TABLE {spec.table} TYPE {spec.type_name};"
        )
        return True

    def ensure_view(self, spec: ViewSpec) -> bool:
        tables = self._database_info().get("tables", {})
        definition = tables.get(spec.name)
        if definition is not None:
            self._validate_view(spec, definition)
            return False

        self.query(f"DEFINE TABLE IF NOT EXISTS {spec.name} AS {spec.query};")
        return True

    def ensure_index(self, spec: IndexSpec) -> bool:
        indexes = self._table_info(spec.table).get("indexes", {})
        definition = indexes.get(spec.identity)
        if definition is not None:
            self._validate_index(spec, definition)
            return False

        fields = ", ".join(spec.fields)
        unique = " UNIQUE" if spec.unique else ""
        self.query(
            f"DEFINE INDEX IF NOT EXISTS {spec.identity} "
            f"ON TABLE {spec.table} FIELDS {fields}{unique};"
        )
        return True

    def upsert_record(self, table: str, key: str, data: dict[str, Any]) -> bool:
        record_id = _record_id(table, key)
        created = not self.record_exists(record_id)
        self.query(f"UPSERT {record_id} CONTENT {_to_surql(data)} RETURN NONE;")
        return created

    def upsert_relation(
        self,
        table: str,
        key: str,
        in_record: str,
        out_record: str,
        data: dict[str, Any],
        *,
        replace_existing_in: bool = False,
    ) -> bool:
        relation_id = _record_id(table, key)
        created = not self.record_exists(relation_id)

        if created:
            if replace_existing_in:
                self.query(
                    f"DELETE {table} WHERE in = {in_record} "
                    f"AND id != {relation_id} RETURN NONE;"
                )
            self.query(
                f"RELATE {in_record}->{relation_id}->{out_record} "
                f"CONTENT {_to_surql(data)} RETURN NONE;"
            )
        else:
            self.query(f"UPDATE {relation_id} MERGE {_to_surql(data)} RETURN NONE;")

        return created

    def matches_layout(self, layout: StorageLayout) -> bool:
        try:
            database_info = self._database_info()
            if not isinstance(database_info.get("tables"), dict):
                return False

            table_definitions = database_info["tables"]
            table_infos: dict[str, dict[str, Any]] = {}

            for table in layout.tables:
                definition = table_definitions.get(table.name)
                if definition is None:
                    return False
                self._validate_table(table, definition)
                table_infos[table.name] = self._table_info(table.name)

            for view in layout.views:
                definition = table_definitions.get(view.name)
                if definition is None:
                    return False
                self._validate_view(view, definition)

            for field in layout.fields:
                definition = (
                    table_infos.get(field.table, {})
                    .get("fields", {})
                    .get(field.name)
                )
                if definition is None:
                    return False
                self._validate_field(field, definition)

            for index in layout.indexes:
                definition = table_infos.get(index.table, {}).get("indexes", {}).get(
                    index.identity
                )
                if definition is None:
                    return False
                self._validate_index(index, definition)
        except (StorageLayoutConflict, SurrealRequestError):
            return False

        return True

    def record_exists(self, record_id: str) -> bool:
        result = self.query(f"SELECT VALUE id FROM ONLY {record_id};")
        return result not in (None, [])

    def query(self, sql: str) -> Any:
        status, payload = self._send(
            "POST",
            "/sql",
            body=sql.encode(),
            content_type="text/plain",
        )
        if status != 200:
            msg = f"SurrealDB SQL returned HTTP {status}: {payload!r}"
            raise SurrealRequestError(msg)
        if not isinstance(payload, list):
            msg = f"SurrealDB SQL returned unexpected payload: {payload!r}"
            raise SurrealRequestError(msg)

        result: Any = None
        for statement in payload:
            if statement.get("status") != "OK":
                msg = f"SurrealDB SQL failed: {statement!r}"
                raise SurrealRequestError(msg)
            result = statement.get("result")
        return result

    def _database_info(self) -> dict[str, Any]:
        result = self.query("INFO FOR DB;")
        if not isinstance(result, dict):
            msg = f"SurrealDB database info has unexpected shape: {result!r}"
            raise SurrealRequestError(msg)
        return result

    def _table_info(self, table: str) -> dict[str, Any]:
        result = self.query(f"INFO FOR TABLE {table};")
        if not isinstance(result, dict):
            msg = f"SurrealDB table info has unexpected shape: {result!r}"
            raise SurrealRequestError(msg)
        return result

    def _validate_table(self, spec: TableSpec, definition: Any) -> None:
        definition_text = _definition_text(definition)
        if spec.schemafull and "SCHEMAFULL" not in definition_text:
            msg = (
                f"Table {spec.name!r} exists without required SCHEMAFULL clause: "
                f"{definition_text!r}."
            )
            raise StorageLayoutConflict(msg)

        expected_type = f"TYPE {_surreal_table_type(spec.kind)}"
        if expected_type not in definition_text:
            msg = (
                f"Table {spec.name!r} exists with incompatible layout: "
                f"expected {expected_type}, got {definition_text!r}."
            )
            raise StorageLayoutConflict(msg)

        if spec.kind == "relation":
            for endpoint in (spec.from_table, spec.to_table):
                if endpoint is None or endpoint not in definition_text:
                    msg = (
                        f"Relation table {spec.name!r} exists with incompatible "
                        f"endpoints: expected {spec.from_table!r} -> "
                        f"{spec.to_table!r}, got {definition_text!r}."
                    )
                    raise StorageLayoutConflict(msg)
            if "ENFORCED" not in definition_text:
                msg = (
                    f"Relation table {spec.name!r} exists without required "
                    f"ENFORCED clause: {definition_text!r}."
                )
                raise StorageLayoutConflict(msg)

    def _validate_field(self, spec: FieldSpec, definition: Any) -> None:
        definition_text = _definition_text(definition)
        expected_type = f"TYPE {spec.type_name}"
        if not _field_type_matches(spec.type_name, definition_text):
            msg = (
                f"Field {spec.identity!r} exists with incompatible type: "
                f"expected {expected_type}, got {definition_text!r}."
            )
            raise StorageLayoutConflict(msg)

    def _validate_view(self, spec: ViewSpec, definition: Any) -> None:
        definition_text = _normalize_definition(_definition_text(definition))
        expected_query = _normalize_definition(f"AS {spec.query}")
        if " AS SELECT " not in definition_text:
            msg = (
                f"View {spec.name!r} exists as a non-view table: "
                f"{definition_text!r}."
            )
            raise StorageLayoutConflict(msg)
        if expected_query not in definition_text:
            msg = (
                f"View {spec.name!r} exists with incompatible query body: "
                f"expected {expected_query!r}, got {definition_text!r}."
            )
            raise StorageLayoutConflict(msg)

    def _validate_index(self, spec: IndexSpec, definition: Any) -> None:
        definition_text = _definition_text(definition)
        expected_fields = f"FIELDS {', '.join(spec.fields)}"
        if expected_fields not in definition_text:
            msg = (
                f"Index {spec.identity!r} exists with incompatible fields: "
                f"expected {expected_fields}, got {definition_text!r}."
            )
            raise StorageLayoutConflict(msg)
        if spec.unique and "UNIQUE" not in definition_text:
            msg = (
                f"Index {spec.identity!r} exists without required UNIQUE clause: "
                f"{definition_text!r}."
            )
            raise StorageLayoutConflict(msg)

    def _send(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        authenticate: bool = True,
        include_namespace_database: bool = True,
    ) -> tuple[int, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = {
            "accept": "application/json",
        }
        if authenticate:
            headers["authorization"] = self._authorization_header()
        if include_namespace_database:
            headers["surreal-ns"] = self.namespace
            headers["surreal-db"] = self.database

        if content_type is not None:
            headers["content-type"] = content_type

        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.getcode(), _decode_payload(response.read())
        except HTTPError as exc:
            return exc.code, _decode_payload(exc.read())
        except URLError as exc:
            msg = f"Could not connect to SurrealDB at {url}: {exc.reason}"
            raise SurrealRequestError(msg) from exc

    def _authorization_header(self) -> str:
        if self.token is not None:
            return f"Bearer {self.token}"
        token = f"{self.username}:{self.password}".encode()
        encoded = base64.b64encode(token).decode("ascii")
        return f"Basic {encoded}"


def _surreal_table_type(kind: TableKind) -> str:
    return "RELATION" if kind == "relation" else "NORMAL"


def _define_database_user_sql(
    username: str,
    password: str,
    roles: tuple[str, ...],
) -> str:
    role_clause = ", ".join(_surreal_role(role) for role in roles)
    return (
        f"DEFINE USER OVERWRITE {_surreal_identifier(username)} "
        f"ON DATABASE PASSWORD {_to_surql(password)} ROLES {role_clause};"
    )


def _surreal_identifier(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) is None:
        msg = f"Invalid SurrealDB identifier: {value!r}."
        raise ValueError(msg)
    return value


def _surreal_role(value: str) -> str:
    role = value.upper()
    if role not in {"OWNER", "EDITOR", "VIEWER"}:
        msg = f"Invalid SurrealDB role: {value!r}."
        raise ValueError(msg)
    return role


def _table_clause(spec: TableSpec) -> str:
    schema = "SCHEMAFULL" if spec.schemafull else "SCHEMALESS"
    table_type = _surreal_table_type(spec.kind)
    if spec.kind == "normal":
        return f"{schema} TYPE {table_type}"

    if spec.from_table is None or spec.to_table is None:
        msg = f"Relation table {spec.name!r} requires from_table and to_table."
        raise ValueError(msg)

    return (
        f"{schema} TYPE {table_type} "
        f"FROM {spec.from_table} TO {spec.to_table} ENFORCED"
    )


def _record_id(table: str, key: str) -> str:
    return f"{table}:{key}"


def _to_surql(value: Any) -> str:
    if isinstance(value, datetime):
        return f"d'{value.astimezone(UTC).isoformat().replace('+00:00', 'Z')}'"
    if isinstance(value, dict):
        fields = (
            f"{json.dumps(key, separators=(',', ':'))}:{_to_surql(item)}"
            for key, item in value.items()
        )
        return "{" + ",".join(fields) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_to_surql(item) for item in value) + "]"
    return json.dumps(value, separators=(",", ":"))


def _to_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _definition_text(definition: Any) -> str:
    if isinstance(definition, dict) and isinstance(definition.get("sql"), str):
        return definition["sql"]
    return str(definition)


def _normalize_definition(definition: str) -> str:
    return " ".join(definition.rstrip(";").split())


def _field_type_matches(expected: str, definition_text: str) -> bool:
    actual = _extract_field_type(definition_text)
    if actual is None:
        return False
    return _normalize_field_type(actual) == _normalize_field_type(expected)


def _extract_field_type(definition_text: str) -> str | None:
    normalized = _normalize_definition(definition_text)
    match = re.search(r"\bTYPE\s+(.+?)(?:\s+PERMISSIONS\b|$)", normalized)
    if match is None:
        return None
    return match.group(1)


def _normalize_field_type(type_name: str) -> str:
    normalized = _normalize_definition(type_name)
    optional_inner = _optional_inner_type(normalized)
    if optional_inner is not None:
        return f"none|{_normalize_field_type(optional_inner)}"

    parts = [part.strip() for part in normalized.split("|")]
    if len(parts) > 1 and "none" in parts:
        non_none_parts = [part for part in parts if part != "none"]
        if len(non_none_parts) == 1:
            return f"none|{_normalize_field_type(non_none_parts[0])}"

    return normalized.replace(" ", "")


def _optional_inner_type(type_name: str) -> str | None:
    if not type_name.startswith("option<") or not type_name.endswith(">"):
        return None
    return type_name.removeprefix("option<")[:-1].strip()


def _decode_payload(raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


__all__ = [
    "SurrealRequestError",
    "SurrealStorageBackend",
]
