from collections import Counter, defaultdict
from base64 import b64decode
import csv
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.cases import connect, get_case_or_404, normalize_long_text, normalize_required_text
from app.core.config import get_settings
from app.provider_registry import canonical_provider_id, provider_metadata
from app.taxonomy import CLASSIFICATION_VERSION, TaxonomyClassification, classify_fraud_taxonomy


RunStatus = Literal["success", "partial", "failed"]
ReviewStatus = Literal["pending", "relevant", "not_relevant"]
TrendGroupType = Literal["keyword", "classification", "source", "time_window", "theme"]
SourceQuality = Literal["named_source", "unnamed_source"]
RecencyCue = Literal["fresh", "recent", "older", "unknown"]
ClassificationBasis = Literal["title", "snippet", "fallback"]
FraudStateBasis = Literal["title", "snippet", "publisher", "source_url", "unknown"]
EvidenceArtifactType = Literal["source_url", "html_snapshot", "text_snapshot", "screenshot"]
EvidenceArtifactAvailability = Literal["available", "not_captured"]

NEWS_TIMEOUT_SECONDS = 8
MAX_NEWS_BODY_BYTES = 512_000
MAX_KEYWORDS = 12
MAX_GENERAL_RESULT_AGE_DAYS = 730
ALLOWED_KEYWORD_TERMS = {
    "abuse",
    "brand",
    "crime",
    "criminal",
    "fake",
    "fraud",
    "fraudulent",
    "impersonation",
    "phishing",
    "public",
    "risk",
    "scam",
    "scams",
    "spoof",
    "theft",
    "warning",
}
STOP_WORDS = {
    "about",
    "after",
    "again",
    "against",
    "also",
    "amid",
    "from",
    "into",
    "over",
    "that",
    "the",
    "their",
    "this",
    "with",
    "your",
}

FRAUD_CLASSIFICATION_RULES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "lending fraud",
        [
            ("lending fraud", r"\blending fraud\b"),
            ("loan fraud", r"\bloan fraud\b"),
            ("mortgage fraud", r"\bmortgage fraud\b"),
        ],
    ),
    (
        "investment fraud",
        [
            ("investment fraud", r"\binvestment fraud\b"),
            ("securities fraud", r"\bsecurities fraud\b"),
            ("ponzi", r"\bponzi\b"),
        ],
    ),
    ("insurance fraud", [("insurance fraud", r"\binsurance fraud\b")]),
    (
        "identity theft",
        [
            ("identity theft", r"\bidentity theft\b"),
            ("stolen identity", r"\bstolen identit(?:y|ies)\b"),
        ],
    ),
    (
        "phishing or impersonation",
        [
            ("phishing", r"\bphishing\b"),
            ("impersonation", r"\bimpersonation\b"),
            ("impersonator", r"\bimpersonator\b"),
            ("spoofing", r"\bspoof(?:ing)?\b"),
        ],
    ),
    (
        "healthcare fraud",
        [
            ("healthcare fraud", r"\bhealth ?care fraud\b"),
            ("medicare fraud", r"\bmedicare fraud\b"),
            ("medicaid fraud", r"\bmedicaid fraud\b"),
        ],
    ),
    ("tax fraud", [("tax fraud", r"\btax fraud\b"), ("tax evasion", r"\btax evasion\b")]),
    (
        "wire or payment fraud",
        [
            ("wire fraud", r"\bwire fraud\b"),
            ("payment fraud", r"\bpayment fraud\b"),
            ("ach fraud", r"\bach fraud\b"),
            ("credit card fraud", r"\bcredit card fraud\b"),
        ],
    ),
    (
        "crypto fraud",
        [
            ("crypto fraud", r"\bcrypto(?:currency)? fraud\b"),
            ("bitcoin fraud", r"\bbitcoin fraud\b"),
            ("token fraud", r"\btoken fraud\b"),
        ],
    ),
    (
        "procurement or contract fraud",
        [
            ("procurement fraud", r"\bprocurement fraud\b"),
            ("contract fraud", r"\bcontract fraud\b"),
            ("vendor fraud", r"\bvendor fraud\b"),
        ],
    ),
    (
        "charity fraud",
        [
            ("charity fraud", r"\bcharity fraud\b"),
            ("fundraising fraud", r"\bfundraising fraud\b"),
        ],
    ),
]
GENERAL_FRAUD_LABEL = "general fraud reporting"
UNKNOWN_FRAUD_STATE_LABEL = "Unknown"
US_STATE_TERMS: list[tuple[str, str, list[str]]] = [
    ("AL", "Alabama", ["Alabama"]),
    ("AK", "Alaska", ["Alaska"]),
    ("AZ", "Arizona", ["Arizona"]),
    ("AR", "Arkansas", ["Arkansas"]),
    ("CA", "California", ["California"]),
    ("CO", "Colorado", ["Colorado"]),
    ("CT", "Connecticut", ["Connecticut"]),
    ("DE", "Delaware", ["Delaware"]),
    ("FL", "Florida", ["Florida"]),
    ("GA", "Georgia", ["Georgia"]),
    ("HI", "Hawaii", ["Hawaii"]),
    ("ID", "Idaho", ["Idaho"]),
    ("IL", "Illinois", ["Illinois"]),
    ("IN", "Indiana", ["Indiana"]),
    ("IA", "Iowa", ["Iowa"]),
    ("KS", "Kansas", ["Kansas"]),
    ("KY", "Kentucky", ["Kentucky"]),
    ("LA", "Louisiana", ["Louisiana"]),
    ("ME", "Maine", ["Maine"]),
    ("MD", "Maryland", ["Maryland"]),
    ("MA", "Massachusetts", ["Massachusetts"]),
    ("MI", "Michigan", ["Michigan"]),
    ("MN", "Minnesota", ["Minnesota"]),
    ("MS", "Mississippi", ["Mississippi"]),
    ("MO", "Missouri", ["Missouri"]),
    ("MT", "Montana", ["Montana"]),
    ("NE", "Nebraska", ["Nebraska"]),
    ("NV", "Nevada", ["Nevada"]),
    ("NH", "New Hampshire", ["New Hampshire"]),
    ("NJ", "New Jersey", ["New Jersey"]),
    ("NM", "New Mexico", ["New Mexico"]),
    ("NY", "New York", ["New York"]),
    ("NC", "North Carolina", ["North Carolina"]),
    ("ND", "North Dakota", ["North Dakota"]),
    ("OH", "Ohio", ["Ohio"]),
    ("OK", "Oklahoma", ["Oklahoma"]),
    ("OR", "Oregon", ["Oregon"]),
    ("PA", "Pennsylvania", ["Pennsylvania"]),
    ("RI", "Rhode Island", ["Rhode Island"]),
    ("SC", "South Carolina", ["South Carolina"]),
    ("SD", "South Dakota", ["South Dakota"]),
    ("TN", "Tennessee", ["Tennessee"]),
    ("TX", "Texas", ["Texas"]),
    ("UT", "Utah", ["Utah"]),
    ("VT", "Vermont", ["Vermont"]),
    ("VA", "Virginia", ["Virginia"]),
    ("WA", "Washington", ["Washington"]),
    ("WV", "West Virginia", ["West Virginia"]),
    ("WI", "Wisconsin", ["Wisconsin"]),
    ("WY", "Wyoming", ["Wyoming"]),
    ("DC", "District of Columbia", ["District of Columbia", "Washington DC", "Washington D.C."]),
]

router = APIRouter()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def decode_json_list(value: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def normalize_keyword(value: str) -> str:
    keyword = " ".join(value.strip().lower().split())
    if not keyword:
        raise ValueError("Keywords must not be blank.")
    if len(keyword) > 80:
        raise ValueError("Keywords must be 80 characters or fewer.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9 .&'_-]*", keyword):
        raise ValueError("Keywords may contain letters, numbers, spaces, and basic punctuation.")
    if not any(term in keyword.split() or term in keyword for term in ALLOWED_KEYWORD_TERMS):
        raise ValueError(
            "Keyword scans must use scam, fraud, crime, impersonation, or adjacent public-interest terms."
        )
    return keyword


def normalize_keywords(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        keyword = normalize_keyword(value)
        if keyword not in seen:
            normalized.append(keyword)
            seen.add(keyword)

    if not normalized:
        raise ValueError("At least one keyword is required.")
    if len(normalized) > MAX_KEYWORDS:
        raise ValueError(f"Keyword sets can include at most {MAX_KEYWORDS} keywords.")
    return normalized


def normalize_url_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("News result source URLs must be absolute HTTP or HTTPS URLs.")
    if len(cleaned) > 2000:
        raise ValueError("News result source URLs must be 2000 characters or fewer.")
    return cleaned


class KeywordSetBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    keywords: list[str] = Field(min_length=1, max_length=MAX_KEYWORDS)
    scope_notes: str = Field(default="", max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: list[str]) -> list[str]:
        return normalize_keywords(value)

    @field_validator("scope_notes")
    @classmethod
    def clean_scope_notes(cls, value: str) -> str:
        return normalize_long_text(value)


class KeywordSetCreate(KeywordSetBase):
    pass


class KeywordSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    keywords: list[str] | None = Field(default=None, min_length=1, max_length=MAX_KEYWORDS)
    scope_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else value

    @field_validator("keywords")
    @classmethod
    def clean_optional_keywords(cls, value: list[str] | None) -> list[str] | None:
        return normalize_keywords(value) if value is not None else value

    @field_validator("scope_notes")
    @classmethod
    def clean_optional_scope_notes(cls, value: str | None) -> str | None:
        return normalize_long_text(value) if value is not None else value


class KeywordScanRequest(BaseModel):
    keyword_set_id: str | None = None
    keywords: list[str] | None = Field(default=None, max_length=MAX_KEYWORDS)

    @field_validator("keywords")
    @classmethod
    def clean_scan_keywords(cls, value: list[str] | None) -> list[str] | None:
        return normalize_keywords(value) if value is not None else value


class NewsResultRecord(BaseModel):
    id: str
    case_id: str
    run_id: str
    provider: str = ""
    keyword: str
    source_url: str
    publisher: str
    title: str
    snippet: str
    published_at: str
    retrieved_at: str
    review_status: ReviewStatus
    saved_as_evidence: bool
    evidence_link_id: str | None = None
    evidence_analyst_note: str = ""
    evidence_artifacts: list["EvidenceArtifactRecord"] = Field(default_factory=list)
    available_artifact_count: int = 0
    vault_state: str = "not_saved"
    seen_count: int = 1
    duplicate_count: int = 0
    theme: str
    classification_label: str
    classification_basis: ClassificationBasis
    classification_terms: list[str]
    fraud_state_code: str
    fraud_state_label: str
    fraud_state_basis: FraudStateBasis
    fraud_state_terms: list[str]
    source_type: str = "news_index"
    source_confidence: str = "medium"
    fraud_category: str = "unknown"
    fraud_subcategory: str = ""
    payment_rail: str = "unknown"
    victim_segment: str = "unknown"
    state: str = ""
    city: str = ""
    loss_amount: float | None = None
    entities_named: list[str] = Field(default_factory=list)
    keywords_detected: list[str] = Field(default_factory=list)
    event_date: str = ""
    published_date: str = ""
    classification_version: str = CLASSIFICATION_VERSION
    classification_confidence: str = "low"
    source_quality: SourceQuality
    recency_cue: RecencyCue
    prioritization_cue: str
    created_at: str


class NewsIngestionRunRecord(BaseModel):
    id: str
    case_id: str
    keyword_set_id: str | None = None
    provider: str
    status: RunStatus
    started_at: str
    completed_at: str
    query_keywords: list[str]
    raw_result_count: int = 0
    result_count: int
    filtered_result_count: int = 0
    error_message: str
    created_at: str
    results: list[NewsResultRecord] = Field(default_factory=list)


class KeywordSetRecord(KeywordSetBase):
    id: str
    case_id: str
    created_at: str
    updated_at: str


class NewsResultUpdate(BaseModel):
    review_status: ReviewStatus


class EvidenceLinkCreate(BaseModel):
    analyst_note: str = Field(default="", max_length=2000)
    html_snapshot: str = Field(default="", max_length=250000)
    text_snapshot: str = Field(default="", max_length=50000)
    screenshot_data_url: str = Field(default="", max_length=1000000)
    capture_screenshot: bool = False

    @field_validator("analyst_note")
    @classmethod
    def clean_analyst_note(cls, value: str) -> str:
        return normalize_long_text(value)

    @field_validator("html_snapshot", "text_snapshot", "screenshot_data_url")
    @classmethod
    def clean_optional_artifact_text(cls, value: str) -> str:
        return value.strip()


class EvidenceLinkUpdate(EvidenceLinkCreate):
    pass


class EvidenceLinkRecord(BaseModel):
    id: str
    case_id: str
    news_result_id: str
    source_url: str
    publisher: str
    title: str
    snippet: str
    published_at: str
    retrieved_at: str
    query_keyword: str
    analyst_note: str
    created_at: str
    artifacts: list["EvidenceArtifactRecord"] = Field(default_factory=list)


class EvidenceArtifactRecord(BaseModel):
    id: str
    case_id: str
    evidence_link_id: str
    news_result_id: str
    artifact_type: EvidenceArtifactType
    display_name: str
    storage_path: str
    media_type: str
    byte_size: int
    content_hash: str
    source_url: str
    captured_at: str
    retention_policy: str
    availability: EvidenceArtifactAvailability
    capture_note: str
    created_at: str


class TrendGroup(BaseModel):
    group_type: TrendGroupType
    label: str
    result_count: int
    sample_titles: list[str]
    source_attribution: list[str]
    priority_cue: str
    confidence_language: str


class TrendSummary(BaseModel):
    case_id: str
    generated_at: str
    groups: list[TrendGroup]


class ProviderResult(BaseModel):
    keyword: str
    source_url: str
    publisher: str = ""
    title: str = ""
    snippet: str = ""
    published_at: str = ""
    retrieved_at: str
    source_type: str = ""
    source_confidence: str = ""
    fraud_category: str = ""
    fraud_subcategory: str = ""
    payment_rail: str = ""
    victim_segment: str = ""
    state: str = ""
    city: str = ""
    loss_amount: float | None = None
    entities_named: list[str] = Field(default_factory=list)
    keywords_detected: list[str] = Field(default_factory=list)
    event_date: str = ""
    published_date: str = ""
    classification_version: str = ""
    classification_confidence: str = ""

    @field_validator("source_url")
    @classmethod
    def clean_source_url(cls, value: str) -> str:
        return normalize_url_text(value)

    @field_validator("publisher", "title", "snippet", "published_at")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


def request_headers() -> dict[str, str]:
    return {
        "User-Agent": "OSINT-CaseOps/0.1 public-news-monitoring",
        "Accept": "application/json",
    }


def row_to_keyword_set(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["keywords"] = decode_json_list(payload.pop("keywords_json"))
    return payload


def row_to_news_result(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["provider"] = payload.get("provider", "")
    payload["saved_as_evidence"] = bool(payload["saved_as_evidence"])
    payload["evidence_analyst_note"] = payload.get("evidence_analyst_note") or ""
    payload["evidence_artifacts"] = payload.get("evidence_artifacts") or []
    payload["available_artifact_count"] = int(payload.get("available_artifact_count") or 0)
    if not payload["saved_as_evidence"]:
        payload["vault_state"] = "not_saved"
    elif payload["available_artifact_count"] > 0:
        payload["vault_state"] = "artifacts_available"
    else:
        payload["vault_state"] = "metadata_only"
    payload["seen_count"] = int(payload.get("seen_count") or 1)
    payload["duplicate_count"] = max(payload["seen_count"] - 1, 0)
    payload["classification_label"] = payload.get("classification_label") or GENERAL_FRAUD_LABEL
    payload["classification_basis"] = payload.get("classification_basis") or "fallback"
    payload["classification_terms"] = decode_json_list(payload.get("classification_terms_json") or "[]")
    payload["fraud_state_code"] = payload.get("fraud_state_code") or ""
    payload["fraud_state_label"] = payload.get("fraud_state_label") or UNKNOWN_FRAUD_STATE_LABEL
    payload["fraud_state_basis"] = payload.get("fraud_state_basis") or "unknown"
    payload["fraud_state_terms"] = decode_json_list(payload.get("fraud_state_terms_json") or "[]")
    payload["source_type"] = payload.get("source_type") or "news_index"
    payload["source_confidence"] = payload.get("source_confidence") or "medium"
    payload["fraud_category"] = payload.get("fraud_category") or "unknown"
    payload["fraud_subcategory"] = payload.get("fraud_subcategory") or ""
    payload["payment_rail"] = payload.get("payment_rail") or "unknown"
    payload["victim_segment"] = payload.get("victim_segment") or "unknown"
    payload["state"] = payload.get("state") or payload["fraud_state_code"] or ""
    payload["city"] = payload.get("city") or ""
    payload["entities_named"] = decode_json_list(payload.get("entities_named_json") or "[]")
    payload["keywords_detected"] = decode_json_list(payload.get("keywords_detected_json") or "[]")
    payload["event_date"] = payload.get("event_date") or ""
    payload["published_date"] = payload.get("published_date") or normalize_date(payload.get("published_at") or "")
    payload["classification_version"] = payload.get("classification_version") or CLASSIFICATION_VERSION
    payload["classification_confidence"] = payload.get("classification_confidence") or "low"
    payload["source_quality"] = source_quality(payload)
    payload["recency_cue"] = recency_cue(payload.get("published_at") or payload.get("retrieved_at", ""))
    payload["prioritization_cue"] = prioritization_cue(payload)
    payload.pop("classification_terms_json", None)
    payload.pop("fraud_state_terms_json", None)
    payload.pop("entities_named_json", None)
    payload.pop("keywords_detected_json", None)
    return payload


def row_to_evidence_artifact(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["byte_size"] = int(payload.get("byte_size") or 0)
    return payload


def list_artifacts_for_evidence(
    connection: sqlite3.Connection,
    evidence_link_id: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM evidence_artifacts
        WHERE evidence_link_id = ?
        ORDER BY
            CASE artifact_type
                WHEN 'source_url' THEN 1
                WHEN 'text_snapshot' THEN 2
                WHEN 'html_snapshot' THEN 3
                WHEN 'screenshot' THEN 4
                ELSE 5
            END,
            created_at ASC
        """,
        (evidence_link_id,),
    ).fetchall()
    return [row_to_evidence_artifact(row) for row in rows]


def attach_artifacts_to_results(
    connection: sqlite3.Connection,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for result in results:
        evidence_link_id = result.get("evidence_link_id")
        artifacts = list_artifacts_for_evidence(connection, evidence_link_id) if evidence_link_id else []
        result["evidence_artifacts"] = artifacts
        result["available_artifact_count"] = sum(1 for artifact in artifacts if artifact["availability"] == "available")
        if not result["saved_as_evidence"]:
            result["vault_state"] = "not_saved"
        elif result["available_artifact_count"] > 0:
            result["vault_state"] = "artifacts_available"
        else:
            result["vault_state"] = "metadata_only"
    return results


def artifact_storage_root() -> Path:
    return get_settings().data_dir / "evidence-vault"


def relative_artifact_path(path: Path) -> str:
    return path.relative_to(get_settings().data_dir).as_posix()


def write_vault_artifact(
    connection: sqlite3.Connection,
    *,
    evidence_link_id: str,
    case_id: str,
    news_result_id: str,
    artifact_type: EvidenceArtifactType,
    display_name: str,
    content: bytes,
    media_type: str,
    extension: str,
    source_url: str,
    captured_at: str,
    capture_note: str,
) -> dict[str, Any]:
    artifact_id = str(uuid4())
    artifact_dir = artifact_storage_root() / case_id / evidence_link_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    file_path = artifact_dir / f"{artifact_type}-{artifact_id}{extension}"
    file_path.write_bytes(content)
    content_hash = sha256(content).hexdigest()
    connection.execute(
        """
        INSERT INTO evidence_artifacts (
            id,
            case_id,
            evidence_link_id,
            news_result_id,
            artifact_type,
            display_name,
            storage_path,
            media_type,
            byte_size,
            content_hash,
            source_url,
            captured_at,
            retention_policy,
            availability,
            capture_note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)
        """,
        (
            artifact_id,
            case_id,
            evidence_link_id,
            news_result_id,
            artifact_type,
            display_name,
            relative_artifact_path(file_path),
            media_type,
            len(content),
            content_hash,
            source_url,
            captured_at,
            "Retain with the local case data until analyst deletion or case cleanup.",
            capture_note,
            captured_at,
        ),
    )
    row = connection.execute("SELECT * FROM evidence_artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if row is None:
        raise RuntimeError("Evidence artifact was not stored.")
    return row_to_evidence_artifact(row)


def store_reference_artifact(
    connection: sqlite3.Connection,
    *,
    evidence_link_id: str,
    case_id: str,
    news_result_id: str,
    source_url: str,
    captured_at: str,
) -> dict[str, Any]:
    artifact_id = str(uuid4())
    content_hash = sha256(source_url.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO evidence_artifacts (
            id,
            case_id,
            evidence_link_id,
            news_result_id,
            artifact_type,
            display_name,
            storage_path,
            media_type,
            byte_size,
            content_hash,
            source_url,
            captured_at,
            retention_policy,
            availability,
            capture_note,
            created_at
        )
        VALUES (?, ?, ?, ?, 'source_url', 'Source URL reference', '', 'text/uri-list', ?, ?, ?, ?, ?, 'available', ?, ?)
        """,
        (
            artifact_id,
            case_id,
            evidence_link_id,
            news_result_id,
            len(source_url.encode("utf-8")),
            content_hash,
            source_url,
            captured_at,
            "Retain with the local case data until analyst deletion or case cleanup.",
            "Source-link metadata preserved separately from local content artifacts.",
            captured_at,
        ),
    )
    row = connection.execute("SELECT * FROM evidence_artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if row is None:
        raise RuntimeError("Evidence source reference was not stored.")
    return row_to_evidence_artifact(row)


def store_missing_screenshot_artifact(
    connection: sqlite3.Connection,
    *,
    evidence_link_id: str,
    case_id: str,
    news_result_id: str,
    source_url: str,
    captured_at: str,
) -> dict[str, Any]:
    artifact_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO evidence_artifacts (
            id,
            case_id,
            evidence_link_id,
            news_result_id,
            artifact_type,
            display_name,
            storage_path,
            media_type,
            byte_size,
            content_hash,
            source_url,
            captured_at,
            retention_policy,
            availability,
            capture_note,
            created_at
        )
        VALUES (?, ?, ?, ?, 'screenshot', 'Screenshot capture', '', 'image/png', 0, '', ?, ?, ?, 'not_captured', ?, ?)
        """,
        (
            artifact_id,
            case_id,
            evidence_link_id,
            news_result_id,
            source_url,
            captured_at,
            "Capture when a local screenshot is supplied; no remote automation is implied.",
            "No screenshot file was supplied with this evidence save.",
            captured_at,
        ),
    )
    row = connection.execute("SELECT * FROM evidence_artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if row is None:
        raise RuntimeError("Evidence screenshot metadata was not stored.")
    return row_to_evidence_artifact(row)


def decode_screenshot_data_url(value: str) -> tuple[bytes, str]:
    if not value:
        return b"", ""
    prefix, _, payload = value.partition(",")
    if not payload or ";base64" not in prefix:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="screenshot_data_url must be a base64 data URL.",
        )
    media_type = prefix.removeprefix("data:").split(";", 1)[0] or "image/png"
    if media_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Screenshot artifacts must be PNG, JPEG, or WebP data URLs.",
        )
    return b64decode(payload, validate=True), media_type


def create_evidence_artifacts(
    connection: sqlite3.Connection,
    *,
    evidence_link_id: str,
    result: dict[str, Any],
    payload: EvidenceLinkCreate,
    captured_at: str,
) -> list[dict[str, Any]]:
    artifacts = [
        store_reference_artifact(
            connection,
            evidence_link_id=evidence_link_id,
            case_id=result["case_id"],
            news_result_id=result["id"],
            source_url=result["source_url"],
            captured_at=captured_at,
        )
    ]
    snapshot_text = payload.text_snapshot or "\n".join(
        part
        for part in [
            f"Title: {result['title'] or result['source_url']}",
            f"Source URL: {result['source_url']}",
            f"Publisher: {result['publisher'] or 'Unknown source'}",
            f"Published at: {result['published_at'] or 'unknown'}",
            f"Retrieved at: {result['retrieved_at']}",
            "",
            result["snippet"] or "No provider snippet was stored.",
        ]
        if part is not None
    )
    artifacts.append(
        write_vault_artifact(
            connection,
            evidence_link_id=evidence_link_id,
            case_id=result["case_id"],
            news_result_id=result["id"],
            artifact_type="text_snapshot",
            display_name="Provider text snapshot",
            content=snapshot_text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            extension=".txt",
            source_url=result["source_url"],
            captured_at=captured_at,
            capture_note="Saved from provider-returned source metadata and analyst-supplied text.",
        )
    )
    if payload.html_snapshot:
        artifacts.append(
            write_vault_artifact(
                connection,
                evidence_link_id=evidence_link_id,
                case_id=result["case_id"],
                news_result_id=result["id"],
                artifact_type="html_snapshot",
                display_name="HTML snapshot",
                content=payload.html_snapshot.encode("utf-8"),
                media_type="text/html; charset=utf-8",
                extension=".html",
                source_url=result["source_url"],
                captured_at=captured_at,
                capture_note="Saved from analyst-supplied source HTML.",
            )
        )
    if payload.screenshot_data_url:
        content, media_type = decode_screenshot_data_url(payload.screenshot_data_url)
        extension = { "image/jpeg": ".jpg", "image/webp": ".webp" }.get(media_type, ".png")
        artifacts.append(
            write_vault_artifact(
                connection,
                evidence_link_id=evidence_link_id,
                case_id=result["case_id"],
                news_result_id=result["id"],
                artifact_type="screenshot",
                display_name="Screenshot capture",
                content=content,
                media_type=media_type,
                extension=extension,
                source_url=result["source_url"],
                captured_at=captured_at,
                capture_note="Saved from analyst-supplied screenshot data.",
            )
        )
    elif payload.capture_screenshot:
        artifacts.append(
            store_missing_screenshot_artifact(
                connection,
                evidence_link_id=evidence_link_id,
                case_id=result["case_id"],
                news_result_id=result["id"],
                source_url=result["source_url"],
                captured_at=captured_at,
            )
        )
    return artifacts


def parse_source_datetime(value: str) -> datetime | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            if len(cleaned) >= 8 and re.fullmatch(r"\d{8}", cleaned[:8]):
                parsed = datetime.strptime(cleaned[:8], "%Y%m%d").replace(tzinfo=UTC)
            else:
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_date(value: str) -> str:
    parsed = parse_source_datetime(value)
    if parsed is None:
        return ""
    return parsed.date().isoformat()


def source_quality(row: dict[str, Any]) -> SourceQuality:
    return "named_source" if str(row.get("publisher") or "").strip() else "unnamed_source"


def recency_cue(value: str) -> RecencyCue:
    parsed = parse_source_datetime(value)
    if parsed is None:
        return "unknown"
    age_days = (datetime.now(UTC) - parsed).days
    if age_days <= 2:
        return "fresh"
    if age_days <= 14:
        return "recent"
    return "older"


def prioritization_cue(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if row["classification_label"] != GENERAL_FRAUD_LABEL:
        parts.append(f"reported category: {row['classification_label']}")
    if row["recency_cue"] in {"fresh", "recent"}:
        parts.append(f"{row['recency_cue']} public result")
    else:
        parts.append("older or undated public result")
    if row["source_quality"] == "named_source":
        parts.append("named source")
    else:
        parts.append("source attribution needs review")
    if row["duplicate_count"] > 0:
        parts.append(f"seen {row['seen_count']} times")
    return "; ".join(parts)


def row_to_news_run(row: sqlite3.Row, results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = dict(row)
    payload["query_keywords"] = decode_json_list(payload.pop("query_keywords_json"))
    payload["results"] = results or []
    for result in payload["results"]:
        if not result.get("provider"):
            result["provider"] = payload["provider"]
    return payload


def get_keyword_set_or_404(keyword_set_id: str, connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM news_keyword_sets WHERE id = ?",
        (keyword_set_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword set not found.")
    return row_to_keyword_set(row)


def get_news_result_or_404(result_id: str, connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM news_results WHERE id = ?", (result_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News result not found.")
    return row_to_news_result(row)


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or request_headers(), method="GET")
    try:
        with urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:
            return json.loads(response.read(MAX_NEWS_BODY_BYTES).decode("utf-8", errors="replace"))
    except HTTPError as exc:
        raise RuntimeError(f"News provider returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"News provider request failed: {exc}") from exc


def build_provider_query(keyword: str, provider: str) -> str:
    cleaned_keyword = normalize_keyword(keyword)
    if provider.lower() == "brave" and cleaned_keyword == "fraud":
        return "fraud (report OR warning OR investigation OR charged OR lawsuit OR enforcement)"
    return cleaned_keyword


def clean_snippet(value: str, limit: int = 500) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", value))
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def epoch_to_iso(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    if cleaned.isdigit():
        return datetime.fromtimestamp(int(cleaned), UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return cleaned


def search_gdelt(keyword: str, max_results: int) -> list[ProviderResult]:
    query = build_provider_query(keyword, "gdelt")
    params = urlencode(
        {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": max(1, min(max_results, 50)),
            "sort": "DateDesc",
        }
    )
    payload = fetch_json(f"https://api.gdeltproject.org/api/v2/doc/doc?{params}")
    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        return []

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        source_url = str(article.get("url") or "").strip()
        if not source_url:
            continue
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=source_url,
                    publisher=str(article.get("sourceCommonName") or article.get("domain") or ""),
                    title=str(article.get("title") or ""),
                    snippet=str(article.get("seendate") or ""),
                    published_at=str(article.get("seendate") or ""),
                    retrieved_at=retrieved_at,
                )
            )
        except ValueError:
            continue
    return results


def search_doj_news(keyword: str, max_results: int) -> list[ProviderResult]:
    query = build_provider_query(keyword, "doj_news")
    params = urlencode(
        {
            "parameters[title]": query,
            "fields": "title,url,date,body",
            "pagesize": max(1, min(max_results, 50)),
        }
    )
    payload = fetch_json(f"https://www.justice.gov/api/v1/press_releases.json?{params}")
    items = payload.get("results", [])
    if not isinstance(items, list):
        return []

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source_url = str(item.get("url") or "").strip()
        if source_url.startswith("/"):
            source_url = f"https://www.justice.gov{source_url}"
        if not source_url:
            continue
        title = unescape(str(item.get("title") or ""))
        raw_date = str(item.get("date") or "")
        snippet = clean_snippet(str(item.get("body") or "Official DOJ press release metadata."))
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=source_url,
                    publisher="U.S. Department of Justice",
                    title=title,
                    snippet=snippet,
                    published_at=epoch_to_iso(raw_date),
                    retrieved_at=retrieved_at,
                    source_type="official_enforcement",
                    source_confidence="high",
                )
            )
        except ValueError:
            continue
    return results


def search_cfpb_complaints(keyword: str, max_results: int) -> list[ProviderResult]:
    params = urlencode(
        {
            "search_term": build_provider_query(keyword, "cfpb_complaints"),
            "size": max(1, min(max_results, 50)),
            "format": "json",
        }
    )
    payload = fetch_json(
        f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?{params}"
    )
    hits = payload.get("hits", {})
    items = hits.get("hits", []) if isinstance(hits, dict) else payload.get("results", [])
    if not isinstance(items, list):
        return []

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for item in items:
        source = item.get("_source", item) if isinstance(item, dict) else {}
        if not isinstance(source, dict):
            continue
        complaint_id = str(source.get("complaint_id") or source.get("Complaint ID") or "").strip()
        product = str(source.get("product") or source.get("Product") or "").strip()
        issue = str(source.get("issue") or source.get("Issue") or "").strip()
        state = str(source.get("state") or source.get("State") or "").strip()
        received = str(source.get("date_received") or source.get("Date received") or "").strip()
        title = " - ".join(part for part in [product, issue] if part) or "CFPB complaint trend record"
        if not complaint_id:
            complaint_id = sha256(f"{title}:{state}:{received}".encode("utf-8")).hexdigest()[:16]
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=f"https://www.consumerfinance.gov/data-research/consumer-complaints/search/detail/{complaint_id}",
                    publisher="Consumer Financial Protection Bureau",
                    title=title,
                    snippet=clean_snippet(
                        "Public complaint metadata only. Consumer narrative and private details are not stored."
                    ),
                    published_at=received,
                    retrieved_at=retrieved_at,
                    source_type="official_complaint_data",
                    source_confidence="high",
                    state=state,
                    event_date=normalize_date(received),
                )
            )
        except ValueError:
            continue
    return results


def search_fincen_advisories(keyword: str, max_results: int) -> list[ProviderResult]:
    request = Request(
        "https://www.fincen.gov/resources/suspicious-activity-report-sar-advisory-key-terms",
        headers={"User-Agent": request_headers()["User-Agent"], "Accept": "text/html,*/*;q=0.8"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_NEWS_BODY_BYTES).decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"News provider returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"News provider request failed: {exc}") from exc

    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())
    segments = re.findall(r"(FinCEN (?:Alert|Advisory|Notice)[^.]{0,220}?(?:\d{2}/\d{2}/\d{4}|\d{4}))", text)
    if not segments:
        segments = [text[:240]]
    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for index, segment in enumerate(segments[: max(1, min(max_results, 25))], start=1):
        if keyword.lower() not in segment.lower() and "fraud" not in segment.lower():
            continue
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url="https://www.fincen.gov/resources/suspicious-activity-report-sar-advisory-key-terms",
                    publisher="Financial Crimes Enforcement Network",
                    title=segment[:160],
                    snippet=clean_snippet(segment),
                    published_at="",
                    retrieved_at=retrieved_at,
                    source_type="official_advisory",
                    source_confidence="high",
                    entities_named=[f"fincen-advisory-{index}"],
                )
            )
        except ValueError:
            continue
    return results


def search_ftc_consumer_sentinel_import(keyword: str, max_results: int) -> list[ProviderResult]:
    source_path = get_settings().ftc_consumer_sentinel_path
    if not source_path:
        raise RuntimeError(
            "Set OSINT_CASEOPS_FTC_CONSUMER_SENTINEL_PATH to a local Consumer Sentinel CSV export before using this import provider."
        )
    path = Path(source_path).expanduser()
    if not path.exists() or not path.is_file():
        raise RuntimeError("Configured FTC Consumer Sentinel import path does not exist.")

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if len(results) >= max(1, min(max_results, 100)):
                break
            title = str(
                row.get("Category")
                or row.get("Report Category")
                or row.get("Fraud Type")
                or row.get("category")
                or "FTC Consumer Sentinel annual record"
            )
            state = str(row.get("State") or row.get("state") or "").strip()
            reports = str(row.get("Reports") or row.get("# of Reports") or row.get("reports") or "").strip()
            if keyword.lower() not in f"{title} {state}".lower() and "fraud" not in title.lower():
                continue
            digest = sha256(json.dumps(row, sort_keys=True).encode("utf-8")).hexdigest()[:16]
            try:
                results.append(
                    ProviderResult(
                        keyword=keyword,
                        source_url=f"https://www.ftc.gov/reports/consumer-sentinel-network-data-book#import-{digest}",
                        publisher="Federal Trade Commission",
                        title=title,
                        snippet=clean_snippet(
                            f"Annual Consumer Sentinel aggregate import. Reports: {reports or 'not provided'}."
                        ),
                        published_at=str(row.get("Year") or row.get("year") or ""),
                        retrieved_at=retrieved_at,
                        source_type="official_annual_data_import",
                        source_confidence="high",
                        state=state,
                    )
                )
            except ValueError:
                continue
    return results


def search_google_news_rss(keyword: str, max_results: int) -> list[ProviderResult]:
    query = build_provider_query(keyword, "google_news_rss")
    params = urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
    request = Request(
        f"https://news.google.com/rss/search?{params}",
        headers={
            "User-Agent": request_headers()["User-Agent"],
            "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=NEWS_TIMEOUT_SECONDS) as response:
            root = ElementTree.fromstring(response.read(MAX_NEWS_BODY_BYTES))
    except HTTPError as exc:
        raise RuntimeError(f"News provider returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, ElementTree.ParseError) as exc:
        raise RuntimeError(f"News provider request failed: {exc}") from exc

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for item in root.findall("./channel/item")[: max(1, min(max_results, 50))]:
        source = item.find("source")
        source_url = (item.findtext("link") or "").strip()
        if not source_url:
            continue
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=source_url,
                    publisher=(source.text or "").strip() if source is not None else "",
                    title=item.findtext("title") or "",
                    snippet=item.findtext("description") or "",
                    published_at=item.findtext("pubDate") or "",
                    retrieved_at=retrieved_at,
                )
            )
        except ValueError:
            continue
    return results


def search_hn_algolia(keyword: str, max_results: int) -> list[ProviderResult]:
    query = build_provider_query(keyword, "hn_algolia")
    params = urlencode(
        {
            "query": query,
            "tags": "story",
            "hitsPerPage": max(1, min(max_results, 50)),
        }
    )
    payload = fetch_json(f"https://hn.algolia.com/api/v1/search?{params}")
    hits = payload.get("hits", [])
    if not isinstance(hits, list):
        return []

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        object_id = str(hit.get("objectID") or "").strip()
        source_url = str(hit.get("url") or "").strip()
        if not source_url and object_id:
            source_url = f"https://news.ycombinator.com/item?id={object_id}"
        if not source_url:
            continue
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=source_url,
                    publisher="Hacker News",
                    title=str(hit.get("title") or hit.get("story_title") or ""),
                    snippet=str(hit.get("story_text") or hit.get("comment_text") or ""),
                    published_at=str(hit.get("created_at") or ""),
                    retrieved_at=retrieved_at,
                )
            )
        except ValueError:
            continue
    return results


def search_brave(keyword: str, max_results: int) -> list[ProviderResult]:
    settings = get_settings()
    if not settings.brave_search_api_key:
        raise RuntimeError("BRAVE_SEARCH_API_KEY is required when OSINT_CASEOPS_NEWS_PROVIDER=brave.")

    query = build_provider_query(keyword, "brave")
    params = urlencode({"q": query, "count": max(1, min(max_results, 20)), "freshness": "pm"})
    payload = fetch_json(
        f"https://api.search.brave.com/res/v1/news/search?{params}",
        headers={
            **request_headers(),
            "Accept": "application/json",
            "X-Subscription-Token": settings.brave_search_api_key,
        },
    )
    items = payload.get("results", [])
    if not isinstance(items, list):
        return []

    retrieved_at = utc_now()
    results: list[ProviderResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source_url = str(item.get("url") or "").strip()
        if not source_url:
            continue
        meta_url = item.get("meta_url") if isinstance(item.get("meta_url"), dict) else {}
        try:
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=source_url,
                    publisher=str(meta_url.get("hostname") or item.get("source") or ""),
                    title=str(item.get("title") or ""),
                    snippet=str(item.get("description") or ""),
                    published_at=str(item.get("age") or item.get("page_age") or ""),
                    retrieved_at=retrieved_at,
                )
            )
        except ValueError:
            continue
    return results


def search_fixture_news(keyword: str, max_results: int) -> list[ProviderResult]:
    if not get_settings().enable_fixture_provider:
        raise RuntimeError("Set OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1 before using fixture.")

    retrieved_at = utc_now()
    templates = [
        (
            "Public lending fraud reporting fixture",
            "Public reporting describes a recurring lending fraud pattern for analyst review.",
            "https://fixture.example/public-fraud-reporting",
        ),
        (
            "Agency fraud warning fixture",
            "A public agency warning gives source context without private-person profiling.",
            "https://fixture.example/agency-fraud-warning",
        ),
    ]
    return [
        ProviderResult(
            keyword=keyword,
            source_url=url,
            publisher="Fixture Public Source",
            title=title,
            snippet=snippet,
            published_at="2026-05-30T12:00:00Z",
            retrieved_at=retrieved_at,
        )
        for title, snippet, url in templates[: max(1, min(max_results, len(templates)))]
    ]


def search_public_news_with_provider(
    keyword: str,
    provider: str,
    max_results: int | None = None,
) -> list[ProviderResult]:
    settings = get_settings()
    limit = max_results or settings.news_search_max_results
    normalized_provider = provider.lower()

    if normalized_provider == "brave":
        return search_brave(keyword, limit)
    if normalized_provider in {"gdelt", "gdelt_doc"}:
        return search_gdelt(keyword, limit)
    if normalized_provider == "google_news_rss":
        return search_google_news_rss(keyword, limit)
    if normalized_provider == "hn_algolia":
        return search_hn_algolia(keyword, limit)
    if normalized_provider == "fixture":
        return search_fixture_news(keyword, limit)
    if normalized_provider == "doj_news":
        return search_doj_news(keyword, limit)
    if normalized_provider == "cfpb_complaints":
        return search_cfpb_complaints(keyword, limit)
    if normalized_provider == "fincen_advisories":
        return search_fincen_advisories(keyword, limit)
    if normalized_provider == "ftc_consumer_sentinel_import":
        return search_ftc_consumer_sentinel_import(keyword, limit)
    if normalized_provider in {"sec_litigation_releases", "irs_ci_press_releases", "uspis_fraud"}:
        raise RuntimeError(f"{provider} is a documented Tier 2 provider stub and is disabled until implemented.")
    raise RuntimeError(f"Unsupported news provider: {provider}.")


STATIC_URL_EXTENSIONS = {
    ".7z",
    ".avi",
    ".avif",
    ".bmp",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".eot",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".map",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".otf",
    ".pdf",
    ".png",
    ".rar",
    ".svg",
    ".tar",
    ".ttf",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}
STATIC_PATH_SEGMENTS = {
    "_next",
    "asset",
    "assets",
    "cdn-cgi",
    "dist",
    "fonts",
    "images",
    "img",
    "js",
    "scripts",
    "static",
    "styles",
}
ARTICLE_PATH_SEGMENTS = {
    "article",
    "articles",
    "blog",
    "news",
    "press-release",
    "press-releases",
    "report",
    "reports",
    "story",
    "stories",
}
LOW_SIGNAL_HOSTS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
}


def host_matches(host: str, blocked_host: str) -> bool:
    return host == blocked_host or host.endswith(f".{blocked_host}")


def is_official_or_high_confidence(result: ProviderResult) -> bool:
    return result.source_confidence == "high" or result.source_type.startswith("official_")


def stale_general_result_reason(result: ProviderResult) -> str:
    if is_official_or_high_confidence(result):
        return ""
    parsed = parse_source_datetime(result.published_at)
    if parsed is None:
        return ""
    age_days = (datetime.now(UTC) - parsed).days
    if age_days > MAX_GENERAL_RESULT_AGE_DAYS:
        return f"older than {MAX_GENERAL_RESULT_AGE_DAYS} days"
    return ""


def static_result_reason(result: ProviderResult) -> str:
    parsed = urlsplit(result.source_url)
    host = parsed.netloc.lower().removeprefix("www.")
    if any(host_matches(host, blocked_host) for blocked_host in LOW_SIGNAL_HOSTS):
        return "low-signal media or social host"

    stale_reason = stale_general_result_reason(result)
    if stale_reason:
        return stale_reason

    path = unquote(parsed.path).lower()
    filename = path.rsplit("/", 1)[-1]
    if "." in filename:
        extension = f".{filename.rsplit('.', 1)[-1]}"
        if extension in STATIC_URL_EXTENSIONS:
            return f"static asset extension {extension}"

    path_segments = {segment for segment in path.split("/") if segment}
    if path_segments & STATIC_PATH_SEGMENTS:
        return "static asset path"

    title = result.title.strip()
    snippet = result.snippet.strip()
    if title or snippet:
        return ""

    if path_segments & ARTICLE_PATH_SEGMENTS:
        return ""
    return "empty title and snippet"


def filter_static_news_results(results: list[ProviderResult]) -> tuple[list[ProviderResult], list[str]]:
    kept: list[ProviderResult] = []
    filtered_reasons: list[str] = []
    for result in results:
        reason = static_result_reason(result)
        if reason:
            filtered_reasons.append(reason)
            continue
        kept.append(result)
    return kept, filtered_reasons


def search_public_news(keyword: str, max_results: int | None = None) -> list[ProviderResult]:
    return search_public_news_with_provider(
        keyword,
        get_settings().news_search_provider,
        max_results,
    )


def infer_theme(title: str, snippet: str) -> str:
    words = re.findall(r"[a-z0-9]{4,}", f"{title} {snippet}".lower())
    candidates = [word for word in words if word not in STOP_WORDS]
    if not candidates:
        return "general public reporting"
    common = Counter(candidates).most_common(2)
    return " ".join(word for word, _ in common)


def match_classification(text: str) -> tuple[str, list[str]] | None:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return None
    for label, term_patterns in FRAUD_CLASSIFICATION_RULES:
        matched_terms = [
            term
            for term, pattern in term_patterns
            if re.search(pattern, normalized)
        ]
        if matched_terms:
            return label, matched_terms
    return None


def classify_public_result(title: str, snippet: str) -> tuple[str, ClassificationBasis, list[str]]:
    title_match = match_classification(title)
    if title_match:
        label, terms = title_match
        return label, "title", terms

    snippet_match = match_classification(snippet)
    if snippet_match:
        label, terms = snippet_match
        return label, "snippet", terms

    return GENERAL_FRAUD_LABEL, "fallback", []


def state_term_pattern(term: str) -> re.Pattern[str]:
    separators = r"[\s._/-]+"
    parts = [re.escape(part) for part in re.findall(r"[A-Za-z]+", term)]
    return re.compile(rf"(?<![a-z0-9]){separators.join(parts)}(?![a-z0-9])", re.IGNORECASE)


def normalize_state_search_text(value: str) -> str:
    return unquote(value).replace("&nbsp;", " ")


def spans_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def match_reported_states(value: str) -> list[tuple[str, str, str]]:
    text = normalize_state_search_text(value)
    raw_matches: list[tuple[str, str, str, tuple[int, int]]] = []
    for code, label, terms in US_STATE_TERMS:
        for term in terms:
            matched = state_term_pattern(term).search(text)
            if matched:
                raw_matches.append((code, label, term, matched.span()))
                break

    dc_spans = [span for code, _, _, span in raw_matches if code == "DC"]
    matches: list[tuple[str, str, str]] = []
    seen_codes: set[str] = set()
    for code, label, term, span in raw_matches:
        if code == "WA" and any(spans_overlap(span, dc_span) for dc_span in dc_spans):
            continue
        if code not in seen_codes:
            matches.append((code, label, term))
            seen_codes.add(code)
    return matches


def infer_reported_state(
    title: str,
    snippet: str,
    publisher: str,
    source_url: str,
) -> tuple[str, str, FraudStateBasis, list[str]]:
    fields: list[tuple[FraudStateBasis, str]] = [
        ("title", title),
        ("snippet", snippet),
        ("publisher", publisher),
        ("source_url", source_url),
    ]
    for basis, value in fields:
        matches = match_reported_states(value)
        if len(matches) == 1:
            code, label, term = matches[0]
            return code, label, basis, [term]
        if len(matches) > 1:
            return "", UNKNOWN_FRAUD_STATE_LABEL, "unknown", [term for _, _, term in matches]
    return "", UNKNOWN_FRAUD_STATE_LABEL, "unknown", []


def result_taxonomy(result: ProviderResult) -> TaxonomyClassification:
    if result.fraud_category:
        return TaxonomyClassification(
            fraud_category=result.fraud_category,
            fraud_subcategory=result.fraud_subcategory,
            payment_rail=result.payment_rail or "unknown",
            victim_segment=result.victim_segment or "unknown",
            keywords_detected=result.keywords_detected,
            classification_version=result.classification_version or CLASSIFICATION_VERSION,
            classification_confidence=result.classification_confidence or "medium",
        )
    return classify_fraud_taxonomy(result.title, result.snippet, result.publisher, result.source_url)


def provider_defaults_for_run(connection: sqlite3.Connection, run_id: str) -> tuple[str, str]:
    row = connection.execute("SELECT provider FROM news_ingestion_runs WHERE id = ?", (run_id,)).fetchone()
    provider_id = row["provider"] if row else ""
    metadata = provider_metadata(canonical_provider_id(provider_id)) or provider_metadata(provider_id)
    if metadata is None:
        return "news_index", "medium"
    return metadata.source_type, metadata.source_confidence


def store_news_results(
    connection: sqlite3.Connection,
    case_id: str,
    run_id: str,
    results: list[ProviderResult],
) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    default_source_type, default_source_confidence = provider_defaults_for_run(connection, run_id)
    for result in results:
        result_id = str(uuid4())
        created_at = utc_now()
        theme = infer_theme(result.title, result.snippet)
        classification_label, classification_basis, classification_terms = classify_public_result(
            result.title,
            result.snippet,
        )
        fraud_state_code, fraud_state_label, fraud_state_basis, fraud_state_terms = infer_reported_state(
            result.title,
            result.snippet,
            result.publisher,
            result.source_url,
        )
        taxonomy = result_taxonomy(result)
        source_type = result.source_type or default_source_type
        source_confidence = result.source_confidence or default_source_confidence
        state = result.state or fraud_state_code
        published_date = result.published_date or normalize_date(result.published_at)
        event_date = result.event_date or published_date
        connection.execute(
            """
            INSERT INTO news_results (
                id,
                case_id,
                run_id,
                keyword,
                source_url,
                publisher,
                title,
                snippet,
                published_at,
                retrieved_at,
                seen_count,
                last_seen_at,
                theme,
                classification_label,
                classification_basis,
                classification_terms_json,
                fraud_state_code,
                fraud_state_label,
                fraud_state_basis,
                fraud_state_terms_json,
                source_type,
                source_confidence,
                fraud_category,
                fraud_subcategory,
                payment_rail,
                victim_segment,
                state,
                city,
                loss_amount,
                entities_named_json,
                keywords_detected_json,
                event_date,
                published_date,
                classification_version,
                classification_confidence,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, source_url, keyword) DO UPDATE SET
                run_id = excluded.run_id,
                publisher = excluded.publisher,
                title = excluded.title,
                snippet = excluded.snippet,
                published_at = excluded.published_at,
                retrieved_at = excluded.retrieved_at,
                seen_count = news_results.seen_count + 1,
                last_seen_at = excluded.last_seen_at,
                theme = excluded.theme,
                classification_label = excluded.classification_label,
                classification_basis = excluded.classification_basis,
                classification_terms_json = excluded.classification_terms_json,
                fraud_state_code = excluded.fraud_state_code,
                fraud_state_label = excluded.fraud_state_label,
                fraud_state_basis = excluded.fraud_state_basis,
                fraud_state_terms_json = excluded.fraud_state_terms_json,
                source_type = excluded.source_type,
                source_confidence = excluded.source_confidence,
                fraud_category = excluded.fraud_category,
                fraud_subcategory = excluded.fraud_subcategory,
                payment_rail = excluded.payment_rail,
                victim_segment = excluded.victim_segment,
                state = excluded.state,
                city = excluded.city,
                loss_amount = excluded.loss_amount,
                entities_named_json = excluded.entities_named_json,
                keywords_detected_json = excluded.keywords_detected_json,
                event_date = excluded.event_date,
                published_date = excluded.published_date,
                classification_version = excluded.classification_version,
                classification_confidence = excluded.classification_confidence
            """,
            (
                result_id,
                case_id,
                run_id,
                result.keyword,
                result.source_url,
                result.publisher,
                result.title,
                result.snippet,
                result.published_at,
                result.retrieved_at,
                result.retrieved_at,
                theme,
                classification_label,
                classification_basis,
                json.dumps(classification_terms),
                fraud_state_code,
                fraud_state_label,
                fraud_state_basis,
                json.dumps(fraud_state_terms),
                source_type,
                source_confidence,
                taxonomy.fraud_category,
                taxonomy.fraud_subcategory,
                taxonomy.payment_rail,
                taxonomy.victim_segment,
                state,
                result.city,
                result.loss_amount,
                json.dumps(result.entities_named),
                json.dumps(taxonomy.keywords_detected),
                event_date,
                published_date,
                taxonomy.classification_version,
                taxonomy.classification_confidence,
                created_at,
            ),
        )
        row = connection.execute(
            """
            SELECT *
            FROM news_results
            WHERE case_id = ? AND source_url = ? AND keyword = ?
            """,
            (case_id, result.source_url, result.keyword),
        ).fetchone()
        if row is not None and row["id"] not in {existing["id"] for existing in stored}:
            stored.append(row_to_news_result(row))
    return stored


def summarize_run_status(
    keywords: list[str],
    errors: list[str],
    stored_count: int,
) -> tuple[RunStatus, str]:
    if not errors:
        return "success", ""
    if len(errors) == len(keywords) and stored_count == 0:
        return "failed", "; ".join(errors)
    return "partial", "; ".join(errors)


def get_run_with_results(run_id: str, connection: sqlite3.Connection) -> dict[str, Any]:
    run_row = connection.execute(
        "SELECT * FROM news_ingestion_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    if run_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News run not found.")
    result_rows = connection.execute(
        """
        SELECT news_results.*,
            news_ingestion_runs.provider AS provider,
            COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
        FROM news_results
        JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
        LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
        WHERE run_id = ?
        ORDER BY retrieved_at DESC, created_at DESC
        """,
        (run_id,),
    ).fetchall()
    return row_to_news_run(run_row, [row_to_news_result(row) for row in result_rows])


@router.get("/cases/{case_id}/news-keyword-sets", response_model=list[KeywordSetRecord])
def list_keyword_sets(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = connection.execute(
            """
            SELECT *
            FROM news_keyword_sets
            WHERE case_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (case_id,),
        ).fetchall()
    return [row_to_keyword_set(row) for row in rows]


@router.post(
    "/cases/{case_id}/news-keyword-sets",
    response_model=KeywordSetRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_keyword_set(case_id: str, payload: KeywordSetCreate) -> dict[str, Any]:
    keyword_set_id = str(uuid4())
    now = utc_now()
    with connect() as connection:
        get_case_or_404(case_id, connection)
        connection.execute(
            """
            INSERT INTO news_keyword_sets (
                id, case_id, name, keywords_json, scope_notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                keyword_set_id,
                case_id,
                payload.name,
                json.dumps(payload.keywords),
                payload.scope_notes,
                now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM news_keyword_sets WHERE id = ?",
            (keyword_set_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("Keyword set was not stored.")
    return row_to_keyword_set(row)


@router.patch("/news-keyword-sets/{keyword_set_id}", response_model=KeywordSetRecord)
def update_keyword_set(keyword_set_id: str, payload: KeywordSetUpdate) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    with connect() as connection:
        current = get_keyword_set_or_404(keyword_set_id, connection)
        if not updates:
            return current
        column_values: dict[str, Any] = {}
        for key, value in updates.items():
            column_values["keywords_json" if key == "keywords" else key] = (
                json.dumps(value) if key == "keywords" else value
            )
        column_values["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in column_values)
        connection.execute(
            f"UPDATE news_keyword_sets SET {assignments} WHERE id = ?",
            tuple(column_values.values()) + (keyword_set_id,),
        )
        connection.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (column_values["updated_at"], current["case_id"]),
        )
        return get_keyword_set_or_404(keyword_set_id, connection)


@router.delete("/news-keyword-sets/{keyword_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_keyword_set(keyword_set_id: str) -> None:
    with connect() as connection:
        current = get_keyword_set_or_404(keyword_set_id, connection)
        connection.execute("DELETE FROM news_keyword_sets WHERE id = ?", (keyword_set_id,))
        connection.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (utc_now(), current["case_id"]),
        )


@router.post(
    "/cases/{case_id}/news-ingestion-runs",
    response_model=NewsIngestionRunRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_news_ingestion_run(case_id: str, payload: KeywordScanRequest) -> dict[str, Any]:
    started_at = utc_now()
    settings = get_settings()

    with connect() as connection:
        get_case_or_404(case_id, connection)
        keyword_set_id = payload.keyword_set_id
        if keyword_set_id:
            keyword_set = get_keyword_set_or_404(keyword_set_id, connection)
            if keyword_set["case_id"] != case_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Keyword set not found for this case.",
                )
            keywords = keyword_set["keywords"]
        elif payload.keywords:
            keywords = payload.keywords
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide keyword_set_id or keywords for a news scan.",
            )

        run_id = str(uuid4())
        all_results: list[ProviderResult] = []
        errors: list[str] = []
        for keyword in keywords:
            try:
                all_results.extend(search_public_news(keyword))
            except Exception as exc:
                errors.append(f"{keyword}: {exc}")

        connection.execute(
            """
            INSERT INTO news_ingestion_runs (
                id,
                case_id,
                keyword_set_id,
                provider,
                status,
                started_at,
                completed_at,
                query_keywords_json,
                result_count,
                error_message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                case_id,
                keyword_set_id,
                settings.news_search_provider,
                "failed",
                started_at,
                started_at,
                json.dumps(keywords),
                0,
                "",
                started_at,
            ),
        )
        stored_results = store_news_results(connection, case_id, run_id, all_results)
        completed_at = utc_now()
        run_status, error_message = summarize_run_status(keywords, errors, len(stored_results))
        connection.execute(
            """
            UPDATE news_ingestion_runs
            SET status = ?,
                completed_at = ?,
                result_count = ?,
                error_message = ?,
                created_at = ?
            WHERE id = ?
            """,
            (run_status, completed_at, len(stored_results), error_message, completed_at, run_id),
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (completed_at, case_id))
        return get_run_with_results(run_id, connection)


@router.get("/cases/{case_id}/news-ingestion-runs", response_model=list[NewsIngestionRunRecord])
def list_news_ingestion_runs(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        run_rows = connection.execute(
            """
            SELECT *
            FROM news_ingestion_runs
            WHERE case_id = ?
            ORDER BY created_at DESC
            """,
            (case_id,),
        ).fetchall()
        runs: list[dict[str, Any]] = []
        for row in run_rows:
            result_rows = connection.execute(
                """
                SELECT news_results.*,
                    news_ingestion_runs.provider AS provider,
                    COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
                FROM news_results
                JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
                LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
                WHERE news_results.run_id = ?
                ORDER BY news_results.retrieved_at DESC
                """,
                (row["id"],),
            ).fetchall()
            runs.append(row_to_news_run(row, [row_to_news_result(result) for result in result_rows]))
    return runs


@router.get("/cases/{case_id}/news-results", response_model=list[NewsResultRecord])
def list_news_results(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = connection.execute(
            """
            SELECT news_results.*,
                news_ingestion_runs.provider AS provider,
                COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
            FROM news_results
            JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
            LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
            WHERE news_results.case_id = ?
            ORDER BY news_results.retrieved_at DESC, news_results.created_at DESC
            """,
            (case_id,),
        ).fetchall()
    return [row_to_news_result(row) for row in rows]


@router.patch("/news-results/{result_id}", response_model=NewsResultRecord)
def update_news_result(result_id: str, payload: NewsResultUpdate) -> dict[str, Any]:
    with connect() as connection:
        get_news_result_or_404(result_id, connection)
        connection.execute(
            "UPDATE news_results SET review_status = ? WHERE id = ?",
            (payload.review_status, result_id),
        )
        return get_news_result_or_404(result_id, connection)


def get_evidence_link_or_404(
    evidence_link_id: str,
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM evidence_links WHERE id = ?",
        (evidence_link_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence link not found.")
    payload = dict(row)
    payload["artifacts"] = list_artifacts_for_evidence(connection, evidence_link_id)
    return payload


@router.post(
    "/news-results/{result_id}/evidence-links",
    response_model=EvidenceLinkRecord,
    status_code=status.HTTP_201_CREATED,
)
def save_news_result_as_evidence(
    result_id: str,
    payload: EvidenceLinkCreate,
) -> dict[str, Any]:
    with connect() as connection:
        result = get_news_result_or_404(result_id, connection)
        existing = connection.execute(
            "SELECT * FROM evidence_links WHERE news_result_id = ?",
            (result_id,),
        ).fetchone()
        if existing is not None:
            if payload.analyst_note:
                connection.execute(
                    "UPDATE evidence_links SET analyst_note = ? WHERE id = ?",
                    (payload.analyst_note, existing["id"]),
                )
                existing = connection.execute(
                    "SELECT * FROM evidence_links WHERE id = ?",
                    (existing["id"],),
                ).fetchone()
            if not list_artifacts_for_evidence(connection, existing["id"]):
                create_evidence_artifacts(
                    connection,
                    evidence_link_id=existing["id"],
                    result=result,
                    payload=payload,
                    captured_at=utc_now(),
                )
            return get_evidence_link_or_404(existing["id"], connection)

        evidence_id = str(uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO evidence_links (
                id,
                case_id,
                news_result_id,
                source_url,
                publisher,
                title,
                snippet,
                published_at,
                retrieved_at,
                query_keyword,
                analyst_note,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                result["case_id"],
                result_id,
                result["source_url"],
                result["publisher"],
                result["title"],
                result["snippet"],
                result["published_at"],
                result["retrieved_at"],
                result["keyword"],
                payload.analyst_note,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE news_results
            SET saved_as_evidence = 1, evidence_link_id = ?, review_status = 'relevant'
            WHERE id = ?
            """,
            (evidence_id, result_id),
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, result["case_id"]))
        create_evidence_artifacts(
            connection,
            evidence_link_id=evidence_id,
            result=result,
            payload=payload,
            captured_at=now,
        )
        row = connection.execute("SELECT * FROM evidence_links WHERE id = ?", (evidence_id,)).fetchone()
    if row is None:
        raise RuntimeError("Evidence link was not stored.")
    payload = dict(row)
    with connect() as connection:
        payload["artifacts"] = list_artifacts_for_evidence(connection, evidence_id)
    return payload


@router.patch("/evidence-links/{evidence_link_id}", response_model=EvidenceLinkRecord)
def update_evidence_link(
    evidence_link_id: str,
    payload: EvidenceLinkUpdate,
) -> dict[str, Any]:
    with connect() as connection:
        existing = get_evidence_link_or_404(evidence_link_id, connection)
        connection.execute(
            "UPDATE evidence_links SET analyst_note = ? WHERE id = ?",
            (payload.analyst_note, evidence_link_id),
        )
        connection.execute(
            "UPDATE cases SET updated_at = ? WHERE id = ?",
            (utc_now(), existing["case_id"]),
        )
        return get_evidence_link_or_404(evidence_link_id, connection)


@router.get("/cases/{case_id}/evidence-links", response_model=list[EvidenceLinkRecord])
def list_evidence_links(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = connection.execute(
            """
            SELECT *
            FROM evidence_links
            WHERE case_id = ?
            ORDER BY created_at DESC
            """,
            (case_id,),
        ).fetchall()
        return [get_evidence_link_or_404(row["id"], connection) for row in rows]


def bucket_time(value: str) -> str:
    if len(value) >= 10 and re.fullmatch(r"\d{4}-?\d{2}-?\d{2}", value[:10]):
        date = value[:10].replace("-", "")
        return f"{date[:4]}-{date[4:6]}-{date[6:8]}"
    return "retrieval window"


def build_group(group_type: TrendGroupType, label: str, rows: list[dict[str, Any]]) -> TrendGroup:
    publishers = sorted({row["publisher"] for row in rows if row["publisher"]})[:5]
    sample_titles = [row["title"] or row["source_url"] for row in rows[:3]]
    count = len(rows)
    qualifier = "Possible" if count < 3 else "Repeated"
    source_text = ", ".join(publishers) if publishers else "public search results"
    recency_counts = Counter(row.get("recency_cue", "unknown") for row in rows)
    fresh_or_recent = recency_counts["fresh"] + recency_counts["recent"]
    named_source_count = sum(1 for row in rows if row.get("source_quality") == "named_source")
    if count >= 3 and fresh_or_recent:
        priority_cue = "Prioritize for review: repeated recent public reporting."
    elif fresh_or_recent and named_source_count:
        priority_cue = "Review soon: recent public result from a named source."
    elif named_source_count:
        priority_cue = "Review when time allows: named source attribution is available."
    else:
        priority_cue = "Lower priority: attribution or publication date needs analyst review."
    return TrendGroup(
        group_type=group_type,
        label=label,
        result_count=count,
        sample_titles=sample_titles,
        source_attribution=publishers,
        priority_cue=priority_cue,
        confidence_language=(
            f"{qualifier} pattern based on {count} stored public result"
            f"{'' if count == 1 else 's'} from {source_text}; analyst review required."
        ),
    )


@router.get("/cases/{case_id}/news-trends", response_model=TrendSummary)
def get_news_trends(case_id: str) -> TrendSummary:
    with connect() as connection:
        get_case_or_404(case_id, connection)
        rows = [
            row_to_news_result(row)
            for row in connection.execute(
                """
                SELECT news_results.*,
                    news_ingestion_runs.provider AS provider,
                    COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
                FROM news_results
                JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
                LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
                WHERE news_results.case_id = ?
                ORDER BY news_results.retrieved_at DESC, news_results.created_at DESC
                """,
                (case_id,),
            ).fetchall()
        ]

    group_rows: list[TrendGroup] = []
    for group_type, key_fn in (
        ("keyword", lambda row: row["keyword"]),
        ("classification", lambda row: row["classification_label"] or GENERAL_FRAUD_LABEL),
        ("source", lambda row: row["publisher"] or "unknown source"),
        ("time_window", lambda row: bucket_time(row["published_at"] or row["retrieved_at"])),
        ("theme", lambda row: row["theme"] or "general public reporting"),
    ):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[key_fn(row)].append(row)
        for label, grouped_rows in sorted(
            grouped.items(),
            key=lambda item: (-len(item[1]), item[0]),
        )[:6]:
            group_rows.append(build_group(group_type, label, grouped_rows))

    return TrendSummary(case_id=case_id, generated_at=utc_now(), groups=group_rows)
