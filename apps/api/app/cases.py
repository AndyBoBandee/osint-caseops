from datetime import UTC, datetime
import json
import re
import sqlite3
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_settings
from app.db.sqlite import initialize_database


CaseStatus = Literal["active", "archived", "closed"]
Confidence = Literal["high", "medium", "low", "unknown"]
EntityType = Literal["domain", "url", "email", "ip_address", "organization"]

RequiredText = Annotated[str, Field(min_length=1, max_length=500)]
LongText = Annotated[str, Field(max_length=4000)]
TagList = Annotated[list[str], Field(max_length=20)]

DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

router = APIRouter()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    initialize_database()
    connection = sqlite3.connect(get_settings().database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_required_text(value: str) -> str:
    cleaned = normalize_text(value)
    if not cleaned:
        raise ValueError("This field is required.")
    return cleaned


def normalize_long_text(value: str) -> str:
    return value.strip()


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        cleaned = normalize_text(tag).lower()
        if not cleaned:
            continue
        if len(cleaned) > 40:
            raise ValueError("Tags must be 40 characters or fewer.")
        if cleaned not in seen:
            normalized.append(cleaned)
            seen.add(cleaned)

    return normalized


def decode_tags(value: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        return []

    return [tag for tag in parsed if isinstance(tag, str)]


def row_to_case(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["scope_acknowledged"] = bool(payload["scope_acknowledged"])
    payload["tags"] = decode_tags(payload.pop("tags_json"))
    return payload


def row_to_entity(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["tags"] = decode_tags(payload.pop("tags_json"))
    return payload


def normalize_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")

    if "://" in domain or "/" in domain or "?" in domain or "#" in domain:
        raise ValueError("Domain entities must not include a scheme, path, query, or fragment.")
    if not (1 < len(domain) <= 253):
        raise ValueError("Domain must be between 2 and 253 characters.")

    labels = domain.split(".")
    if len(labels) < 2 or any(not DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        raise ValueError("Domain must contain valid DNS labels, such as example.com.")

    return domain


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL entities must be absolute http or https URLs.")
    if parsed.username or parsed.password:
        raise ValueError("URL entities must not include embedded credentials.")

    host = parsed.hostname
    if host is None:
        raise ValueError("URL entities must include a valid host.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL entities must include a valid port when a port is provided.") from exc

    try:
        normalized_host = normalize_ip_address(host)
        if ":" in normalized_host:
            normalized_host = f"[{normalized_host}]"
    except ValueError:
        normalized_host = normalize_domain(host)

    netloc = f"{normalized_host}:{port}" if port is not None else normalized_host
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Email entities must be valid email addresses.")
    return email


def normalize_ip_address(value: str) -> str:
    from ipaddress import ip_address

    try:
        return str(ip_address(value.strip()))
    except ValueError as exc:
        raise ValueError("IP address entities must be valid IPv4 or IPv6 addresses.") from exc


def normalize_entity_value(entity_type: EntityType, value: str) -> str:
    if entity_type == "domain":
        return normalize_domain(value)
    if entity_type == "url":
        return normalize_url(value)
    if entity_type == "email":
        return normalize_email(value)
    if entity_type == "ip_address":
        return normalize_ip_address(value)

    organization = normalize_text(value)
    if len(organization) < 2:
        raise ValueError("Organization entities must be at least 2 characters.")
    return organization


class CaseBase(BaseModel):
    title: RequiredText
    objective: LongText = Field(min_length=1)
    scope_category: RequiredText
    scope_notes: LongText = ""
    case_type: RequiredText
    status: CaseStatus = "active"
    tags: TagList = Field(default_factory=list)
    analyst_notes: LongText = ""

    @field_validator("title", "objective", "scope_category", "case_type")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("scope_notes", "analyst_notes")
    @classmethod
    def clean_long_text(cls, value: str) -> str:
        return normalize_long_text(value)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)


class CaseCreate(CaseBase):
    scope_acknowledged: bool

    @field_validator("scope_acknowledged")
    @classmethod
    def require_scope_acknowledgment(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Scope acknowledgment is required before creating a case.")
        return value


class CaseUpdate(BaseModel):
    title: RequiredText | None = None
    objective: LongText | None = None
    scope_category: RequiredText | None = None
    scope_notes: LongText | None = None
    case_type: RequiredText | None = None
    status: CaseStatus | None = None
    tags: TagList | None = None
    analyst_notes: LongText | None = None

    @field_validator("title", "objective", "scope_category", "case_type")
    @classmethod
    def clean_optional_required_text(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else value

    @field_validator("scope_notes", "analyst_notes")
    @classmethod
    def clean_optional_long_text(cls, value: str | None) -> str | None:
        return normalize_long_text(value) if value is not None else value

    @field_validator("tags")
    @classmethod
    def clean_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value) if value is not None else value


class CaseRecord(CaseBase):
    id: str
    scope_acknowledged: bool
    scope_acknowledged_at: str
    created_at: str
    updated_at: str


class CaseSummary(CaseRecord):
    entity_count: int


class EntityBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_type: EntityType = Field(alias="type")
    value: RequiredText
    display_name: str = Field(default="", max_length=200)
    description: LongText = ""
    confidence: Confidence = "unknown"
    tags: TagList = Field(default_factory=list)
    notes: LongText = ""

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        return normalize_text(value) if value.strip() else ""

    @field_validator("description", "notes")
    @classmethod
    def clean_entity_long_text(cls, value: str) -> str:
        return normalize_long_text(value)

    @field_validator("tags")
    @classmethod
    def clean_entity_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)

    @model_validator(mode="after")
    def clean_entity_value(self) -> "EntityBase":
        self.value = normalize_entity_value(self.entity_type, self.value)
        if not self.display_name:
            self.display_name = self.value
        return self


class EntityCreate(EntityBase):
    pass


class EntityUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_type: EntityType | None = Field(default=None, alias="type")
    value: RequiredText | None = None
    display_name: str | None = Field(default=None, max_length=200)
    description: LongText | None = None
    confidence: Confidence | None = None
    tags: TagList | None = None
    notes: LongText | None = None

    @field_validator("display_name")
    @classmethod
    def clean_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_text(value) if value.strip() else ""

    @field_validator("description", "notes")
    @classmethod
    def clean_optional_entity_long_text(cls, value: str | None) -> str | None:
        return normalize_long_text(value) if value is not None else value

    @field_validator("tags")
    @classmethod
    def clean_optional_entity_tags(cls, value: list[str] | None) -> list[str] | None:
        return normalize_tags(value) if value is not None else value


class EntityRecord(EntityBase):
    id: str
    case_id: str
    created_at: str
    updated_at: str


def get_case_or_404(case_id: str, connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            cases.*,
            (
                SELECT COUNT(*)
                FROM entities
                WHERE entities.case_id = cases.id
            ) AS entity_count
        FROM cases
        WHERE id = ?
        """,
        (case_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    return row_to_case(row)


def get_entity_or_404(entity_id: str, connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    return row_to_entity(row)


def execute_unique(connection: sqlite3.Connection, sql: str, values: tuple[Any, ...]) -> None:
    try:
        connection.execute(sql, values)
    except sqlite3.IntegrityError as exc:
        message = str(exc)
        if "UNIQUE constraint failed: entities.case_id, entities.type, entities.value" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This entity already exists in the case.",
            ) from exc
        raise


@router.get("/cases", response_model=list[CaseSummary])
def list_cases() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                cases.*,
                (
                    SELECT COUNT(*)
                    FROM entities
                    WHERE entities.case_id = cases.id
                ) AS entity_count
            FROM cases
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()

    return [row_to_case(row) for row in rows]


@router.post("/cases", response_model=CaseSummary, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate) -> dict[str, Any]:
    case_id = str(uuid4())
    now = utc_now()

    with connect() as connection:
        connection.execute(
            """
            INSERT INTO cases (
                id,
                title,
                objective,
                scope_category,
                scope_notes,
                case_type,
                status,
                scope_acknowledged,
                scope_acknowledged_at,
                tags_json,
                analyst_notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                payload.title,
                payload.objective,
                payload.scope_category,
                payload.scope_notes,
                payload.case_type,
                payload.status,
                now,
                json.dumps(payload.tags),
                payload.analyst_notes,
                now,
                now,
            ),
        )
        return get_case_or_404(case_id, connection)


@router.get("/cases/{case_id}", response_model=CaseSummary)
def get_case(case_id: str) -> dict[str, Any]:
    with connect() as connection:
        return get_case_or_404(case_id, connection)


@router.patch("/cases/{case_id}", response_model=CaseSummary)
def update_case(case_id: str, payload: CaseUpdate) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        with connect() as connection:
            return get_case_or_404(case_id, connection)

    column_values: dict[str, Any] = {}
    for key, value in updates.items():
        column_values["tags_json" if key == "tags" else key] = (
            json.dumps(value) if key == "tags" else value
        )
    column_values["updated_at"] = utc_now()

    assignments = ", ".join(f"{column} = ?" for column in column_values)
    values = tuple(column_values.values()) + (case_id,)

    with connect() as connection:
        get_case_or_404(case_id, connection)
        connection.execute(f"UPDATE cases SET {assignments} WHERE id = ?", values)
        return get_case_or_404(case_id, connection)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(case_id: str) -> None:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        connection.execute("DELETE FROM cases WHERE id = ?", (case_id,))


@router.get("/cases/{case_id}/entities", response_model=list[EntityRecord])
def list_case_entities(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = connection.execute(
            """
            SELECT *
            FROM entities
            WHERE case_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (case_id,),
        ).fetchall()

    return [row_to_entity(row) for row in rows]


@router.post(
    "/cases/{case_id}/entities",
    response_model=EntityRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_entity(case_id: str, payload: EntityCreate) -> dict[str, Any]:
    entity_id = str(uuid4())
    now = utc_now()

    with connect() as connection:
        get_case_or_404(case_id, connection)
        execute_unique(
            connection,
            """
            INSERT INTO entities (
                id,
                case_id,
                type,
                value,
                display_name,
                description,
                confidence,
                tags_json,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                case_id,
                payload.entity_type,
                payload.value,
                payload.display_name,
                payload.description,
                payload.confidence,
                json.dumps(payload.tags),
                payload.notes,
                now,
                now,
            ),
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
        return get_entity_or_404(entity_id, connection)


@router.get("/entities/{entity_id}", response_model=EntityRecord)
def get_entity(entity_id: str) -> dict[str, Any]:
    with connect() as connection:
        return get_entity_or_404(entity_id, connection)


@router.patch("/entities/{entity_id}", response_model=EntityRecord)
def update_entity(entity_id: str, payload: EntityUpdate) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)

    with connect() as connection:
        current = get_entity_or_404(entity_id, connection)
        if not updates:
            return current

        merged = {
            "type": updates.get("entity_type", current["type"]),
            "value": updates.get("value", current["value"]),
            "display_name": updates.get("display_name", current["display_name"]),
            "description": updates.get("description", current["description"]),
            "confidence": updates.get("confidence", current["confidence"]),
            "tags": updates.get("tags", current["tags"]),
            "notes": updates.get("notes", current["notes"]),
        }
        normalized = EntityBase.model_validate(merged)
        now = utc_now()
        execute_unique(
            connection,
            """
            UPDATE entities
            SET
                type = ?,
                value = ?,
                display_name = ?,
                description = ?,
                confidence = ?,
                tags_json = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                normalized.entity_type,
                normalized.value,
                normalized.display_name,
                normalized.description,
                normalized.confidence,
                json.dumps(normalized.tags),
                normalized.notes,
                now,
                entity_id,
            ),
        )
        connection.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (now, current["case_id"]),
        )
        return get_entity_or_404(entity_id, connection)


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: str) -> None:
    now = utc_now()

    with connect() as connection:
        current = get_entity_or_404(entity_id, connection)
        connection.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
        connection.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (now, current["case_id"]),
        )
