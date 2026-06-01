from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from app.cases import connect, normalize_long_text, normalize_required_text
from app.core.config import get_settings
from app.news_monitoring import (
    EvidenceLinkCreate,
    EvidenceLinkRecord,
    EvidenceLinkUpdate,
    NEWS_TIMEOUT_SECONDS,
    NewsResultRecord,
    NewsResultUpdate,
    ReviewStatus,
    RunStatus,
    TrendSummary,
    attach_artifacts_to_results,
    filter_static_news_results,
    get_evidence_link_or_404,
    get_news_result_or_404,
    get_news_trends,
    row_to_news_result,
    save_news_result_as_evidence,
    search_public_news_with_provider,
    store_news_results,
    summarize_run_status,
    update_evidence_link,
    update_news_result,
)


router = APIRouter(prefix="/fraud-monitor", tags=["fraud monitor"])

FRAUD_KEYWORD = "fraud"
FRAUD_MONITOR_CASE_ID = "fraud-monitor-system-case"
DEFAULT_INTERVAL_MINUTES = 60

TriggerType = Literal["manual", "scheduled"]
SearchMode = Literal["standard", "detailed"]
ProviderStatus = Literal["ready", "missing_config", "unsupported", "timeout", "partial_success"]
EvidenceFilter = Literal["all", "saved", "unsaved"]
ValidationSeverity = Literal["error", "warning", "info"]
FindingConfidence = Literal["high", "medium", "low", "unknown"]
FindingStatus = Literal["draft", "active", "resolved", "archived"]
TimelineEventType = Literal[
    "scan_run",
    "review_update",
    "evidence_save",
    "evidence_update",
    "finding_create",
    "finding_update",
    "export_generation",
]
ResultSort = Literal[
    "retrieved_desc",
    "retrieved_asc",
    "published_desc",
    "published_asc",
    "title_asc",
    "source_asc",
    "review_asc",
]

_scheduler_task: asyncio.Task[None] | None = None
_scheduler_stop_event: asyncio.Event | None = None
_job_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def minutes_from_now(minutes: int) -> str:
    return (
        datetime.now(UTC) + timedelta(minutes=minutes)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")


class ProviderInfo(BaseModel):
    name: str
    status: ProviderStatus
    note: str
    request_limit: str
    timeout_seconds: int
    last_run_status: RunStatus | Literal[""]
    last_result_count: int
    last_error_message: str
    next_retry_at: str


class ConfigurationIssue(BaseModel):
    severity: ValidationSeverity
    provider: str
    message: str


class FraudMonitorConfigurationValidation(BaseModel):
    is_valid: bool
    fixture_mode: bool
    provider_count: int
    ready_provider_count: int
    issues: list[ConfigurationIssue]
    recommendations: list[str]


class FraudMonitorSchedule(BaseModel):
    enabled: bool
    interval_minutes: int
    next_run_at: str
    last_started_at: str
    last_completed_at: str
    updated_at: str


class FraudMonitorScheduleUpdate(BaseModel):
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=5, le=1440)


class FraudMonitorRuntime(BaseModel):
    is_running: bool
    ready_provider_count: int
    last_error_message: str
    last_error_at: str


class FraudMonitorProviderRunSummary(BaseModel):
    provider: str
    status: RunStatus
    raw_result_count: int
    stored_result_count: int
    filtered_result_count: int
    note: str


class FraudMonitorJob(BaseModel):
    id: str
    keyword: str
    trigger_type: TriggerType
    status: RunStatus
    started_at: str
    completed_at: str
    provider_count: int
    result_count: int
    error_message: str
    created_at: str
    provider_runs: list[str] = Field(default_factory=list)
    provider_run_summaries: list[FraudMonitorProviderRunSummary] = Field(default_factory=list)


class FraudMonitorJobCreate(BaseModel):
    search_mode: SearchMode = "standard"


class FraudMonitorResultPage(BaseModel):
    total_matching: int
    limit: int
    offset: int
    has_next: bool
    has_previous: bool
    search: str
    sort: ResultSort
    review_filter: ReviewStatus | Literal["all"]
    provider_filter: str
    evidence_filter: EvidenceFilter


class FraudMonitorDashboard(BaseModel):
    keyword: str
    case_id: str
    providers: list[ProviderInfo]
    detailed_provider: ProviderInfo
    configuration_validation: FraudMonitorConfigurationValidation
    schedule: FraudMonitorSchedule
    latest_job: FraudMonitorJob | None
    jobs: list[FraudMonitorJob]
    results: list[NewsResultRecord]
    result_page: FraudMonitorResultPage
    evidence_count: int
    runtime: FraudMonitorRuntime
    trend_summary: TrendSummary
    total_results: int
    pending_results: int
    relevant_results: int
    not_relevant_results: int
    findings: list["FindingRecord"]
    timeline_events: list["TimelineEventRecord"]
    operations: "OperationsStatus"


class FraudMonitorBulkReviewUpdate(BaseModel):
    result_ids: list[str] = Field(min_length=1, max_length=200)
    review_status: ReviewStatus


class FraudMonitorBulkReviewResult(BaseModel):
    updated_count: int
    results: list[NewsResultRecord]


class LinkedEvidenceRecord(BaseModel):
    id: str
    source_url: str
    publisher: str
    title: str
    analyst_note: str
    review_status: ReviewStatus
    available_artifact_count: int
    created_at: str


class FindingBase(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=2000)
    confidence: FindingConfidence = "unknown"
    status: FindingStatus = "draft"
    analyst_notes: str = Field(default="", max_length=4000)
    evidence_link_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title", "summary")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("analyst_notes")
    @classmethod
    def clean_analyst_notes(cls, value: str) -> str:
        return normalize_long_text(value)

    @field_validator("evidence_link_ids")
    @classmethod
    def clean_evidence_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for evidence_id in value:
            normalized = evidence_id.strip()
            if normalized and normalized not in seen:
                cleaned.append(normalized)
                seen.add(normalized)
        return cleaned


class FindingCreate(FindingBase):
    pass


class FindingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    summary: str | None = Field(default=None, min_length=1, max_length=2000)
    confidence: FindingConfidence | None = None
    status: FindingStatus | None = None
    analyst_notes: str | None = Field(default=None, max_length=4000)
    evidence_link_ids: list[str] | None = Field(default=None, max_length=20)

    @field_validator("title", "summary")
    @classmethod
    def clean_optional_required_text(cls, value: str | None) -> str | None:
        return normalize_required_text(value) if value is not None else value

    @field_validator("analyst_notes")
    @classmethod
    def clean_optional_notes(cls, value: str | None) -> str | None:
        return normalize_long_text(value) if value is not None else value

    @field_validator("evidence_link_ids")
    @classmethod
    def clean_optional_evidence_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return FindingBase.clean_evidence_ids(value)


class FindingRecord(BaseModel):
    id: str
    case_id: str
    title: str
    summary: str
    confidence: FindingConfidence
    status: FindingStatus
    analyst_notes: str
    linked_evidence: list[LinkedEvidenceRecord]
    created_at: str
    updated_at: str


class TimelineEventRecord(BaseModel):
    id: str
    case_id: str
    event_type: TimelineEventType
    title: str
    summary: str
    actor: str
    related_result_id: str | None
    related_evidence_link_id: str | None
    related_finding_id: str | None
    metadata: dict[str, Any]
    created_at: str


class FraudMonitorExportMetadata(BaseModel):
    generated_at: str
    scope: str
    methodology: str
    provider_configuration: list[ProviderInfo]
    reviewed_result_count: int
    evidence_count: int
    finding_count: int
    timeline_event_count: int
    available_artifact_count: int
    local_only: bool
    responsible_use: str


class FraudMonitorEvidenceTableRow(BaseModel):
    source_url: str
    provider: str
    review_status: ReviewStatus
    classification_label: str
    fraud_state_label: str
    fraud_state_code: str
    analyst_note: str
    available_artifact_count: int
    vault_artifacts: list[str]
    retrieved_at: str
    published_at: str
    title: str


class FraudMonitorExportBundle(BaseModel):
    metadata: FraudMonitorExportMetadata
    trend_summary: TrendSummary
    evidence_table: list[FraudMonitorEvidenceTableRow]
    reviewed_results: list[NewsResultRecord]
    findings: list[FindingRecord]
    timeline_events: list[TimelineEventRecord]
    limitations: list[str]


class OperationsDataDirectoryHealth(BaseModel):
    status: Literal["ok", "warning", "error"]
    path: str
    exists: bool
    writable: bool
    file_count: int
    byte_size: int


class OperationsDatabaseHealth(BaseModel):
    status: Literal["ok", "warning", "error"]
    path: str
    exists: bool
    byte_size: int
    case_count: int
    result_count: int
    evidence_count: int
    job_count: int
    checked_at: str


class OperationsSchedulerHealth(BaseModel):
    status: Literal["idle", "running", "disabled"]
    enabled: bool
    task_active: bool
    job_running: bool
    interval_minutes: int
    next_run_at: str
    last_completed_at: str


class OperationsWarning(BaseModel):
    severity: ValidationSeverity
    message: str


class OperationsBackupArtifact(BaseModel):
    filename: str
    path: str
    byte_size: int
    created_at: str
    includes: list[str]
    download_url: str


class OperationsRetentionCandidate(BaseModel):
    id: str
    filename: str
    path: str
    reason: str
    byte_size: int
    created_at: str


class OperationsStatus(BaseModel):
    generated_at: str
    local_only: bool
    data_directory: OperationsDataDirectoryHealth
    database: OperationsDatabaseHealth
    scheduler: OperationsSchedulerHealth
    warnings: list[OperationsWarning]
    backups: list[OperationsBackupArtifact]
    retention_candidates: list[OperationsRetentionCandidate]


class OperationsBackupCreate(BaseModel):
    note: str = Field(default="", max_length=400)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        return normalize_long_text(value)


class OperationsCleanupRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=50)


class OperationsCleanupResult(BaseModel):
    deleted_count: int
    deleted_bytes: int
    remaining_candidates: list[OperationsRetentionCandidate]


def configured_providers() -> list[str]:
    settings = get_settings()
    providers = settings.fraud_monitor_providers or ["gdelt", "google_news_rss", "hn_algolia"]
    normalized: list[str] = []
    seen: set[str] = set()
    for provider in providers:
        name = provider.strip().lower()
        if name and name not in seen:
            normalized.append(name)
            seen.add(name)
    return normalized


def provider_result_cap(provider: str) -> int:
    return {
        "brave": 20,
        "fixture": 2,
        "gdelt": 50,
        "google_news_rss": 50,
        "hn_algolia": 50,
    }.get(provider, 0)


def provider_request_limit(provider: str) -> str:
    cap = provider_result_cap(provider)
    if cap == 0:
        return "Unsupported provider; no requests are made."
    configured_limit = max(1, get_settings().news_search_max_results)
    return f"Up to {min(configured_limit, cap)} result(s) per keyword per run."


def provider_info(
    provider: str,
    connection: sqlite3.Connection | None = None,
    case_id: str | None = None,
    next_retry_at: str = "",
) -> ProviderInfo:
    settings = get_settings()
    base = {
        "name": provider,
        "request_limit": provider_request_limit(provider),
        "timeout_seconds": NEWS_TIMEOUT_SECONDS,
        "last_run_status": "",
        "last_result_count": 0,
        "last_error_message": "",
        "next_retry_at": "",
    }
    if provider == "fixture" and not settings.enable_fixture_provider:
        return ProviderInfo(
            **base,
            status="unsupported",
            note="Set OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1 before using the fixture provider.",
        )
    if provider == "brave" and not settings.brave_search_api_key:
        return ProviderInfo(
            **base,
            status="missing_config",
            note="Set BRAVE_SEARCH_API_KEY before using Brave News Search.",
        )
    if provider not in {"brave", "fixture", "gdelt", "google_news_rss", "hn_algolia"}:
        return ProviderInfo(
            **base,
            status="unsupported",
            note="Unsupported provider; remove it from OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS.",
        )
    if connection is None or case_id is None:
        return ProviderInfo(
            **base,
            status="ready",
            note="Ready for passive public search.",
        )

    row = connection.execute(
        """
        SELECT status, result_count, error_message, completed_at
        FROM news_ingestion_runs
        WHERE case_id = ? AND provider = ?
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """,
        (case_id, provider),
    ).fetchone()
    if row is None:
        return ProviderInfo(
            **base,
            status="ready",
            note="Ready for passive public search; no recent run recorded.",
        )

    error_message = row["error_message"] or ""
    if "timed out" in error_message.lower() or "timeout" in error_message.lower():
        status_value: ProviderStatus = "timeout"
        note = "Last run timed out; scheduled runs use bounded backoff before retrying."
    elif row["status"] == "partial":
        status_value = "partial_success"
        note = "Last run returned some public results and recorded provider issues."
    elif row["status"] == "failed" and error_message:
        status_value = "timeout"
        note = "Last run did not contribute results; check provider availability before relying on it."
    else:
        status_value = "ready"
        note = "Ready for passive public search."

    return ProviderInfo(
        **{
            **base,
            "status": status_value,
            "note": note,
            "last_run_status": row["status"],
            "last_result_count": int(row["result_count"]),
            "last_error_message": error_message,
            "next_retry_at": next_retry_at if status_value in {"timeout", "partial_success"} else "",
        }
    )


def provider_names_for_run() -> list[str]:
    return [info.name for info in map(provider_info, configured_providers()) if info.status == "ready"]


def provider_names_for_search_mode(search_mode: SearchMode) -> list[str]:
    if search_mode == "detailed":
        return ["brave"] if provider_info("brave").status == "ready" else []
    return provider_names_for_run()


def validate_configuration(providers: list[ProviderInfo] | None = None) -> FraudMonitorConfigurationValidation:
    settings = get_settings()
    provider_details = providers or [provider_info(provider) for provider in configured_providers()]
    issues: list[ConfigurationIssue] = []
    recommendations = [
        "Use fixture provider only for deterministic tests and smoke checks.",
        "Use no-key public providers for local pilot runs unless an optional key is configured.",
        "Keep API keys and exported reports out of Git.",
    ]
    if not provider_details:
        issues.append(
            ConfigurationIssue(
                severity="error",
                provider="all",
                message="No fraud monitor providers are configured.",
            )
        )
    for provider in provider_details:
        if provider.status == "missing_config":
            issues.append(
                ConfigurationIssue(
                    severity="error",
                    provider=provider.name,
                    message=provider.note,
                )
            )
        elif provider.status == "unsupported":
            issues.append(
                ConfigurationIssue(
                    severity="error",
                    provider=provider.name,
                    message=provider.note,
                )
            )
        if provider.name == "fixture" and provider.status == "ready":
            issues.append(
                ConfigurationIssue(
                    severity="warning",
                    provider=provider.name,
                    message="Fixture provider is test-only; do not use fixture exports as real public-source findings.",
                )
            )
    ready_count = sum(1 for provider in provider_details if provider.status == "ready")
    if ready_count == 0:
        issues.append(
            ConfigurationIssue(
                severity="error",
                provider="all",
                message="At least one ready provider is required before running the monitor.",
            )
        )
    return FraudMonitorConfigurationValidation(
        is_valid=not any(issue.severity == "error" for issue in issues),
        fixture_mode=settings.enable_fixture_provider,
        provider_count=len(provider_details),
        ready_provider_count=ready_count,
        issues=issues,
        recommendations=recommendations,
    )


def ensure_monitor_case(connection: sqlite3.Connection) -> str:
    now = utc_now()
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
        VALUES (?, ?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            objective = excluded.objective,
            scope_category = excluded.scope_category,
            scope_notes = excluded.scope_notes,
            case_type = excluded.case_type,
            status = 'active',
            updated_at = cases.updated_at
        """,
        (
            FRAUD_MONITOR_CASE_ID,
            "Fraud Monitor",
            "Monitor public web and news results for the keyword fraud.",
            "Public fraud monitoring",
            "Passive public-source monitoring for one fixed keyword: fraud.",
            "Fraud monitor",
            now,
            json.dumps(["system", "fraud-monitor"]),
            "Created automatically for the dedicated fraud monitor dashboard.",
            now,
            now,
        ),
    )
    return FRAUD_MONITOR_CASE_ID


def ensure_monitor_settings(connection: sqlite3.Connection) -> dict[str, Any]:
    case_id = ensure_monitor_case(connection)
    now = utc_now()
    connection.execute(
        """
        INSERT INTO fraud_monitor_settings (
            id,
            case_id,
            keyword,
            enabled,
            interval_minutes,
            next_run_at,
            updated_at
        )
        VALUES (1, ?, 'fraud', 0, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (case_id, DEFAULT_INTERVAL_MINUTES, minutes_from_now(DEFAULT_INTERVAL_MINUTES), now),
    )
    row = connection.execute("SELECT * FROM fraud_monitor_settings WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("Fraud monitor settings were not stored.")
    return dict(row)


def row_to_schedule(row: dict[str, Any]) -> FraudMonitorSchedule:
    return FraudMonitorSchedule(
        enabled=bool(row["enabled"]),
        interval_minutes=row["interval_minutes"],
        next_run_at=row["next_run_at"],
        last_started_at=row["last_started_at"],
        last_completed_at=row["last_completed_at"],
        updated_at=row["updated_at"],
    )


def row_to_job(row: sqlite3.Row, provider_runs: list[str]) -> FraudMonitorJob:
    payload = dict(row)
    payload["provider_runs"] = provider_runs
    payload["provider_run_summaries"] = []
    return FraudMonitorJob(**payload)


def list_jobs(connection: sqlite3.Connection, limit: int = 12) -> list[FraudMonitorJob]:
    rows = connection.execute(
        """
        SELECT *
        FROM fraud_monitor_jobs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    jobs: list[FraudMonitorJob] = []
    for row in rows:
        provider_rows = connection.execute(
            """
            SELECT
                fraud_monitor_job_runs.provider,
                news_ingestion_runs.status,
                news_ingestion_runs.raw_result_count,
                news_ingestion_runs.result_count,
                news_ingestion_runs.filtered_result_count
            FROM fraud_monitor_job_runs
            JOIN news_ingestion_runs ON news_ingestion_runs.id = fraud_monitor_job_runs.news_run_id
            WHERE fraud_monitor_job_runs.job_id = ?
            ORDER BY fraud_monitor_job_runs.provider
            """,
            (row["id"],),
        ).fetchall()
        provider_runs = [provider_row["provider"] for provider_row in provider_rows]
        job = row_to_job(row, provider_runs)
        job.provider_run_summaries = [
            FraudMonitorProviderRunSummary(
                provider=provider_row["provider"],
                status=provider_row["status"],
                raw_result_count=int(provider_row["raw_result_count"] or 0),
                stored_result_count=int(provider_row["result_count"] or 0),
                filtered_result_count=int(provider_row["filtered_result_count"] or 0),
                note=(
                    f"Filtered {int(provider_row['filtered_result_count'] or 0)} static/non-news result(s)."
                    if int(provider_row["filtered_result_count"] or 0) > 0
                    else "No static/non-news results filtered."
                ),
            )
            for provider_row in provider_rows
        ]
        jobs.append(job)
    return jobs


def build_result_filters(
    case_id: str,
    search: str,
    review_filter: ReviewStatus | Literal["all"],
    provider_filter: str,
    evidence_filter: EvidenceFilter,
) -> tuple[list[str], list[Any]]:
    clauses = ["news_results.case_id = ?"]
    params: list[Any] = [case_id]
    cleaned_search = " ".join(search.split())
    if cleaned_search:
        clauses.append(
            """(
                LOWER(news_results.title) LIKE ?
                OR LOWER(news_results.snippet) LIKE ?
                OR LOWER(news_results.publisher) LIKE ?
                OR LOWER(news_results.source_url) LIKE ?
                OR LOWER(news_results.theme) LIKE ?
                OR LOWER(news_results.classification_label) LIKE ?
                OR LOWER(news_results.classification_terms_json) LIKE ?
                OR LOWER(news_results.fraud_state_label) LIKE ?
                OR LOWER(news_results.fraud_state_code) LIKE ?
                OR LOWER(news_results.fraud_state_terms_json) LIKE ?
            )"""
        )
        search_param = f"%{cleaned_search.lower()}%"
        params.extend(
            [
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
                search_param,
            ]
        )
    if review_filter != "all":
        clauses.append("news_results.review_status = ?")
        params.append(review_filter)
    if provider_filter != "all":
        clauses.append("news_ingestion_runs.provider = ?")
        params.append(provider_filter)
    if evidence_filter == "saved":
        clauses.append("news_results.saved_as_evidence = 1")
    elif evidence_filter == "unsaved":
        clauses.append("news_results.saved_as_evidence = 0")
    return clauses, params


def result_order_clause(sort: ResultSort) -> str:
    return {
        "retrieved_desc": "news_results.retrieved_at DESC, news_results.created_at DESC",
        "retrieved_asc": "news_results.retrieved_at ASC, news_results.created_at ASC",
        "published_desc": "news_results.published_at DESC, news_results.retrieved_at DESC",
        "published_asc": "news_results.published_at ASC, news_results.retrieved_at ASC",
        "title_asc": "LOWER(news_results.title) ASC, news_results.retrieved_at DESC",
        "source_asc": "LOWER(news_results.publisher) ASC, news_results.retrieved_at DESC",
        "review_asc": "news_results.review_status ASC, news_results.retrieved_at DESC",
    }[sort]


def list_results(
    connection: sqlite3.Connection,
    case_id: str,
    search: str = "",
    review_filter: ReviewStatus | Literal["all"] = "all",
    provider_filter: str = "all",
    evidence_filter: EvidenceFilter = "all",
    sort: ResultSort = "retrieved_desc",
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], FraudMonitorResultPage]:
    clauses, params = build_result_filters(
        case_id,
        search,
        review_filter,
        provider_filter,
        evidence_filter,
    )
    where_clause = " AND ".join(clauses)
    total_row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM news_results
        JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
        WHERE {where_clause}
        """,
        tuple(params),
    ).fetchone()
    total_matching = int(total_row["count"] if total_row else 0)
    rows = connection.execute(
        f"""
        SELECT news_results.*,
            news_ingestion_runs.provider AS provider,
            COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
        FROM news_results
        JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
        LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
        WHERE {where_clause}
        ORDER BY {result_order_clause(sort)}
        LIMIT ? OFFSET ?
        """,
        tuple(params + [limit, offset]),
    ).fetchall()
    page = FraudMonitorResultPage(
        total_matching=total_matching,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total_matching,
        has_previous=offset > 0,
        search=" ".join(search.split()),
        sort=sort,
        review_filter=review_filter,
        provider_filter=provider_filter,
        evidence_filter=evidence_filter,
    )
    return attach_artifacts_to_results(connection, [row_to_news_result(row) for row in rows]), page


def result_counts(connection: sqlite3.Connection, case_id: str) -> dict[str, int]:
    counts = {
        "total": 0,
        "pending": 0,
        "relevant": 0,
        "not_relevant": 0,
    }
    rows = connection.execute(
        """
        SELECT review_status, COUNT(*) AS count
        FROM news_results
        WHERE case_id = ?
        GROUP BY review_status
        """,
        (case_id,),
    ).fetchall()
    for row in rows:
        status_value = row["review_status"]
        count = row["count"]
        counts["total"] += count
        if status_value in counts:
            counts[status_value] = count
    return counts


def evidence_count(connection: sqlite3.Connection, case_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM evidence_links WHERE case_id = ?",
        (case_id,),
    ).fetchone()
    return int(row["count"] if row else 0)


def available_artifact_count(connection: sqlite3.Connection, case_id: str) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM evidence_artifacts
        WHERE case_id = ? AND availability = 'available'
        """,
        (case_id,),
    ).fetchone()
    return int(row["count"] if row else 0)


def path_byte_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def path_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for child in path.rglob("*") if child.is_file())


def operation_exports_dir() -> Path:
    exports_dir = get_settings().data_dir / "exports" / "operations"
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def backup_created_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def list_operation_backups(limit: int = 5) -> list[OperationsBackupArtifact]:
    exports_dir = operation_exports_dir()
    backups = sorted(
        exports_dir.glob("fraud-monitor-backup-*.json"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    artifacts: list[OperationsBackupArtifact] = []
    for backup in backups[:limit]:
        artifacts.append(
            OperationsBackupArtifact(
                filename=backup.name,
                path=str(backup),
                byte_size=backup.stat().st_size,
                created_at=backup_created_at(backup),
                includes=[
                    "operation health snapshot",
                    "provider configuration",
                    "reviewed export bundle",
                    "retention plan",
                ],
                download_url=f"/fraud-monitor/operations/backups/{backup.name}",
            )
        )
    return artifacts


def retention_candidate_id(path: Path) -> str:
    relative = path.relative_to(operation_exports_dir()).as_posix()
    return hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]


def list_retention_candidates(max_age_days: int = 0) -> list[OperationsRetentionCandidate]:
    exports_dir = operation_exports_dir()
    now = datetime.now(UTC)
    candidates: list[OperationsRetentionCandidate] = []
    for path in sorted(exports_dir.glob("fraud-monitor-backup-*.json")):
        created = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        age_days = (now - created).days
        if age_days < max_age_days:
            continue
        candidates.append(
            OperationsRetentionCandidate(
                id=retention_candidate_id(path),
                filename=path.name,
                path=str(path),
                reason=(
                    "Generated local operations backup. Review before cleanup; "
                    "deleting it does not delete the live database."
                ),
                byte_size=path.stat().st_size,
                created_at=created.isoformat(timespec="seconds").replace("+00:00", "Z"),
            )
        )
    return candidates


def resolve_retention_candidate(candidate_id: str) -> Path | None:
    for candidate in list_retention_candidates(max_age_days=0):
        if candidate.id == candidate_id:
            path = Path(candidate.path).resolve()
            exports_dir = operation_exports_dir().resolve()
            if exports_dir in path.parents and path.is_file():
                return path
    return None


def build_database_health(connection: sqlite3.Connection) -> OperationsDatabaseHealth:
    settings = get_settings()
    case_count = int(connection.execute("SELECT COUNT(*) AS count FROM cases").fetchone()["count"])
    result_count = int(connection.execute("SELECT COUNT(*) AS count FROM news_results").fetchone()["count"])
    evidence_total = int(connection.execute("SELECT COUNT(*) AS count FROM evidence_links").fetchone()["count"])
    job_count = int(connection.execute("SELECT COUNT(*) AS count FROM fraud_monitor_jobs").fetchone()["count"])
    database_path = settings.database_path
    exists = database_path.exists()
    return OperationsDatabaseHealth(
        status="ok" if exists else "error",
        path=str(database_path),
        exists=exists,
        byte_size=database_path.stat().st_size if exists else 0,
        case_count=case_count,
        result_count=result_count,
        evidence_count=evidence_total,
        job_count=job_count,
        checked_at=utc_now(),
    )


def build_data_directory_health() -> OperationsDataDirectoryHealth:
    data_dir = get_settings().data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    probe = data_dir / ".write-test"
    writable = False
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
    return OperationsDataDirectoryHealth(
        status="ok" if data_dir.exists() and writable else "error",
        path=str(data_dir),
        exists=data_dir.exists(),
        writable=writable,
        file_count=path_file_count(data_dir),
        byte_size=path_byte_size(data_dir),
    )


def build_scheduler_health(settings_row: dict[str, Any]) -> OperationsSchedulerHealth:
    enabled = bool(settings_row["enabled"])
    job_running = _job_lock.locked()
    task_active = _scheduler_task is not None and not _scheduler_task.done()
    if job_running:
        status_value: Literal["idle", "running", "disabled"] = "running"
    elif enabled:
        status_value = "idle"
    else:
        status_value = "disabled"
    return OperationsSchedulerHealth(
        status=status_value,
        enabled=enabled,
        task_active=task_active,
        job_running=job_running,
        interval_minutes=int(settings_row["interval_minutes"]),
        next_run_at=settings_row["next_run_at"],
        last_completed_at=settings_row["last_completed_at"],
    )


def build_operation_warnings(
    validation: FraudMonitorConfigurationValidation,
    data_directory: OperationsDataDirectoryHealth,
    database: OperationsDatabaseHealth,
) -> list[OperationsWarning]:
    warnings = [
        OperationsWarning(severity=issue.severity, message=f"{issue.provider}: {issue.message}")
        for issue in validation.issues
    ]
    if data_directory.status != "ok":
        warnings.append(
            OperationsWarning(
                severity="error",
                message="Data directory is not writable; scans, backups, and cleanup may fail.",
            )
        )
    if database.status != "ok":
        warnings.append(
            OperationsWarning(
                severity="error",
                message="SQLite database is missing or unavailable.",
            )
        )
    if not warnings:
        warnings.append(
            OperationsWarning(
                severity="info",
                message="Operations checks are local-only and found no immediate maintenance warnings.",
            )
        )
    return warnings


def build_operations_status(
    connection: sqlite3.Connection,
    settings_row: dict[str, Any],
    providers: list[ProviderInfo],
) -> OperationsStatus:
    validation = validate_configuration(providers)
    data_directory = build_data_directory_health()
    database = build_database_health(connection)
    return OperationsStatus(
        generated_at=utc_now(),
        local_only=True,
        data_directory=data_directory,
        database=database,
        scheduler=build_scheduler_health(settings_row),
        warnings=build_operation_warnings(validation, data_directory, database),
        backups=list_operation_backups(),
        retention_candidates=list_retention_candidates(max_age_days=0),
    )


def row_to_timeline_event(row: sqlite3.Row) -> TimelineEventRecord:
    metadata = json.loads(row["metadata_json"] or "{}")
    if not isinstance(metadata, dict):
        metadata = {}
    return TimelineEventRecord(
        id=row["id"],
        case_id=row["case_id"],
        event_type=row["event_type"],
        title=row["title"],
        summary=row["summary"],
        actor=row["actor"],
        related_result_id=row["related_result_id"],
        related_evidence_link_id=row["related_evidence_link_id"],
        related_finding_id=row["related_finding_id"],
        metadata=metadata,
        created_at=row["created_at"],
    )


def record_timeline_event(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    event_type: TimelineEventType,
    title: str,
    summary: str = "",
    related_result_id: str | None = None,
    related_evidence_link_id: str | None = None,
    related_finding_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    event_id = str(uuid4())
    created_at = utc_now()
    connection.execute(
        """
        INSERT INTO timeline_events (
            id,
            case_id,
            event_type,
            title,
            summary,
            actor,
            related_result_id,
            related_evidence_link_id,
            related_finding_id,
            metadata_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, 'analyst', ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            case_id,
            event_type,
            title,
            summary,
            related_result_id,
            related_evidence_link_id,
            related_finding_id,
            json.dumps(metadata or {}, sort_keys=True),
            created_at,
        ),
    )
    return event_id


def list_timeline_events(
    connection: sqlite3.Connection,
    case_id: str,
    limit: int = 25,
) -> list[TimelineEventRecord]:
    rows = connection.execute(
        """
        SELECT *
        FROM timeline_events
        WHERE case_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (case_id, limit),
    ).fetchall()
    return [row_to_timeline_event(row) for row in rows]


def evidence_summary_rows(
    connection: sqlite3.Connection,
    evidence_link_ids: list[str],
) -> dict[str, LinkedEvidenceRecord]:
    if not evidence_link_ids:
        return {}
    placeholders = ", ".join("?" for _ in evidence_link_ids)
    rows = connection.execute(
        f"""
        SELECT evidence_links.*,
            news_results.review_status,
            COUNT(evidence_artifacts.id) AS available_artifact_count
        FROM evidence_links
        JOIN news_results ON news_results.id = evidence_links.news_result_id
        LEFT JOIN evidence_artifacts
            ON evidence_artifacts.evidence_link_id = evidence_links.id
            AND evidence_artifacts.availability = 'available'
        WHERE evidence_links.id IN ({placeholders})
        GROUP BY evidence_links.id
        """,
        tuple(evidence_link_ids),
    ).fetchall()
    return {
        row["id"]: LinkedEvidenceRecord(
            id=row["id"],
            source_url=row["source_url"],
            publisher=row["publisher"],
            title=row["title"] or row["source_url"],
            analyst_note=row["analyst_note"],
            review_status=row["review_status"],
            available_artifact_count=int(row["available_artifact_count"] or 0),
            created_at=row["created_at"],
        )
        for row in rows
    }


def row_to_finding(
    row: sqlite3.Row,
    linked_evidence: list[LinkedEvidenceRecord],
) -> FindingRecord:
    return FindingRecord(
        id=row["id"],
        case_id=row["case_id"],
        title=row["title"],
        summary=row["summary"],
        confidence=row["confidence"],
        status=row["status"],
        analyst_notes=row["analyst_notes"],
        linked_evidence=linked_evidence,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_findings(connection: sqlite3.Connection, case_id: str) -> list[FindingRecord]:
    rows = connection.execute(
        """
        SELECT *
        FROM findings
        WHERE case_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (case_id,),
    ).fetchall()
    finding_ids = [row["id"] for row in rows]
    linked_by_finding: dict[str, list[str]] = {finding_id: [] for finding_id in finding_ids}
    if finding_ids:
        placeholders = ", ".join("?" for _ in finding_ids)
        link_rows = connection.execute(
            f"""
            SELECT finding_id, evidence_link_id
            FROM finding_evidence_links
            WHERE finding_id IN ({placeholders})
            ORDER BY created_at ASC
            """,
            tuple(finding_ids),
        ).fetchall()
        for link_row in link_rows:
            linked_by_finding.setdefault(link_row["finding_id"], []).append(link_row["evidence_link_id"])

    all_evidence_ids = [
        evidence_id
        for evidence_ids in linked_by_finding.values()
        for evidence_id in evidence_ids
    ]
    evidence_by_id = evidence_summary_rows(connection, all_evidence_ids)
    return [
        row_to_finding(
            row,
            [
                evidence_by_id[evidence_id]
                for evidence_id in linked_by_finding[row["id"]]
                if evidence_id in evidence_by_id
            ],
        )
        for row in rows
    ]


def get_finding_or_404(
    connection: sqlite3.Connection,
    finding_id: str,
    case_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM findings WHERE id = ? AND case_id = ?",
        (finding_id, case_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")
    return row


def get_finding_record_or_404(
    connection: sqlite3.Connection,
    finding_id: str,
    case_id: str,
) -> FindingRecord:
    row = get_finding_or_404(connection, finding_id, case_id)
    link_rows = connection.execute(
        """
        SELECT evidence_link_id
        FROM finding_evidence_links
        WHERE finding_id = ?
        ORDER BY created_at ASC
        """,
        (finding_id,),
    ).fetchall()
    evidence_ids = [link_row["evidence_link_id"] for link_row in link_rows]
    evidence_by_id = evidence_summary_rows(connection, evidence_ids)
    return row_to_finding(
        row,
        [
            evidence_by_id[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
        ],
    )


def validate_evidence_links(
    connection: sqlite3.Connection,
    case_id: str,
    evidence_link_ids: list[str],
) -> None:
    if not evidence_link_ids:
        return
    placeholders = ", ".join("?" for _ in evidence_link_ids)
    rows = connection.execute(
        f"""
        SELECT id
        FROM evidence_links
        WHERE case_id = ? AND id IN ({placeholders})
        """,
        tuple([case_id, *evidence_link_ids]),
    ).fetchall()
    existing_ids = {row["id"] for row in rows}
    if existing_ids != set(evidence_link_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more evidence links were not found.",
        )


def replace_finding_evidence_links(
    connection: sqlite3.Connection,
    *,
    finding_id: str,
    evidence_link_ids: list[str],
    created_at: str,
) -> None:
    connection.execute("DELETE FROM finding_evidence_links WHERE finding_id = ?", (finding_id,))
    for evidence_link_id in evidence_link_ids:
        connection.execute(
            """
            INSERT INTO finding_evidence_links (finding_id, evidence_link_id, created_at)
            VALUES (?, ?, ?)
            """,
            (finding_id, evidence_link_id, created_at),
        )


def latest_error(connection: sqlite3.Connection) -> tuple[str, str]:
    row = connection.execute(
        """
        SELECT error_message, completed_at
        FROM fraud_monitor_jobs
        WHERE error_message != ''
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """,
    ).fetchone()
    if row is None:
        return "", ""
    return row["error_message"], row["completed_at"]


def normalize_provider_error(provider: str, exc: Exception) -> str:
    message = " ".join(str(exc).split())
    if "BRAVE_SEARCH_API_KEY" in message:
        message = "Set BRAVE_SEARCH_API_KEY before using Brave News Search."
    elif "HTTP " in message:
        message = message.replace("News provider returned ", "Provider returned ")
    elif "timed out" in message.lower() or "timeout" in message.lower():
        message = "Provider request timed out; try again later."
    elif "Unsupported news provider" in message:
        message = "Unsupported provider; remove it from the provider configuration."
    elif not message:
        message = "Provider request failed; check network or provider availability."
    elif len(message) > 180:
        message = f"{message[:177]}..."
    return f"{provider}: {message}"


def retry_backoff_minutes(interval_minutes: int, status_value: RunStatus, error_message: str) -> int:
    if status_value == "success" or not error_message:
        return interval_minutes
    base_interval = max(interval_minutes, 5)
    if "timed out" in error_message.lower() or "timeout" in error_message.lower():
        return min(base_interval * 2, 240)
    return min(base_interval + 15, 240)


def next_run_after(
    trigger_type: TriggerType,
    status_value: RunStatus,
    interval_minutes: int,
    error_message: str,
) -> str:
    if trigger_type == "scheduled":
        return minutes_from_now(retry_backoff_minutes(interval_minutes, status_value, error_message))
    return minutes_from_now(interval_minutes)


def filter_note(filtered_reasons: list[str]) -> str:
    if not filtered_reasons:
        return ""
    return f"Filtered {len(filtered_reasons)} static/non-news result(s)."


def create_provider_run(
    connection: sqlite3.Connection,
    case_id: str,
    provider: str,
    keyword: str,
) -> tuple[str, RunStatus, int, str]:
    started_at = utc_now()
    run_id = str(uuid4())
    errors: list[str] = []
    provider_results = []

    try:
        provider_results = search_public_news_with_provider(keyword, provider)
    except Exception as exc:
        errors.append(normalize_provider_error(provider, exc))

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
                raw_result_count,
                result_count,
                filtered_result_count,
                error_message,
                created_at
            )
        VALUES (?, ?, NULL, ?, 'failed', ?, ?, ?, 0, 0, 0, '', ?)
        """,
        (
            run_id,
            case_id,
            provider,
            started_at,
            started_at,
            json.dumps([keyword]),
            started_at,
        ),
    )
    raw_result_count = len(provider_results)
    filtered_results, filtered_reasons = filter_static_news_results(provider_results)
    stored_results = store_news_results(connection, case_id, run_id, filtered_results)
    completed_at = utc_now()
    run_status, error_message = summarize_run_status(
        [keyword],
        errors,
        len(stored_results) + len(filtered_reasons),
    )
    connection.execute(
        """
        UPDATE news_ingestion_runs
        SET status = ?,
            completed_at = ?,
            raw_result_count = ?,
            result_count = ?,
            filtered_result_count = ?,
            error_message = ?,
            created_at = ?
        WHERE id = ?
        """,
        (
            run_status,
            completed_at,
            raw_result_count,
            len(stored_results),
            len(filtered_reasons),
            error_message,
            completed_at,
            run_id,
        ),
    )
    return run_id, run_status, len(stored_results), error_message


def run_fraud_monitor_job_locked(
    trigger_type: TriggerType = "manual",
    search_mode: SearchMode = "standard",
) -> FraudMonitorJob:
    job_id = str(uuid4())
    started_at = utc_now()

    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        providers = provider_names_for_search_mode(search_mode)
        errors: list[str] = []
        result_count = 0
        successful_provider_runs = 0
        run_ids: list[tuple[str, str]] = []

        if not providers and search_mode == "detailed":
            errors.append("Detailed search requires BRAVE_SEARCH_API_KEY before using Brave News Search.")
        elif not providers:
            errors.append("No ready fraud monitor providers are configured.")

        connection.execute(
            """
            INSERT INTO fraud_monitor_jobs (
                id,
                case_id,
                keyword,
                trigger_type,
                status,
                started_at,
                completed_at,
                provider_count,
                result_count,
                error_message,
                created_at
            )
            VALUES (?, ?, 'fraud', ?, 'failed', ?, ?, ?, 0, '', ?)
            """,
            (job_id, case_id, trigger_type, started_at, started_at, len(providers), started_at),
        )

        for provider in providers:
            run_id, run_status, provider_result_count, error_message = create_provider_run(
                connection,
                case_id,
                provider,
                FRAUD_KEYWORD,
            )
            run_ids.append((run_id, provider))
            result_count += provider_result_count
            if run_status == "success":
                successful_provider_runs += 1
            if error_message:
                errors.append(error_message)
            connection.execute(
                """
                INSERT INTO fraud_monitor_job_runs (job_id, news_run_id, provider)
                VALUES (?, ?, ?)
                """,
                (job_id, run_id, provider),
            )

        if not providers or (successful_provider_runs == 0 and result_count == 0):
            status: RunStatus = "failed"
        elif errors:
            status = "partial"
        else:
            status = "success"

        completed_at = utc_now()
        interval_minutes = int(settings["interval_minutes"])
        error_message = "; ".join(errors)
        connection.execute(
            """
            UPDATE fraud_monitor_jobs
            SET status = ?,
                completed_at = ?,
                result_count = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, completed_at, result_count, error_message, job_id),
        )
        connection.execute(
            """
            UPDATE fraud_monitor_settings
            SET last_started_at = ?,
                last_completed_at = ?,
                next_run_at = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                started_at,
                completed_at,
                next_run_after(trigger_type, status, interval_minutes, error_message),
                completed_at,
            ),
        )
        record_timeline_event(
            connection,
            case_id=case_id,
            event_type="scan_run",
            title=f"{trigger_type.title()} fraud scan completed",
            summary=f"{result_count} result(s) stored with {status} status.",
            metadata={
                "job_id": job_id,
                "trigger_type": trigger_type,
                "status": status,
                "provider_count": len(providers),
                "result_count": result_count,
                "providers": providers,
            },
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (completed_at, case_id))
        row = connection.execute("SELECT * FROM fraud_monitor_jobs WHERE id = ?", (job_id,)).fetchone()

    if row is None:
        raise RuntimeError("Fraud monitor job was not stored.")
    return row_to_job(row, [provider for _, provider in run_ids])


def create_fraud_monitor_job(
    trigger_type: TriggerType = "manual",
    search_mode: SearchMode = "standard",
) -> FraudMonitorJob:
    if not _job_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fraud monitor job is already running.",
        )
    try:
        return run_fraud_monitor_job_locked(trigger_type, search_mode)
    finally:
        _job_lock.release()


def build_dashboard(
    search: str = "",
    review_filter: ReviewStatus | Literal["all"] = "all",
    provider_filter: str = "all",
    evidence_filter: EvidenceFilter = "all",
    sort: ResultSort = "retrieved_desc",
    limit: int = 25,
    offset: int = 0,
) -> FraudMonitorDashboard:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        jobs = list_jobs(connection)
        results, result_page = list_results(
            connection,
            case_id,
            search=search,
            review_filter=review_filter,
            provider_filter=provider_filter,
            evidence_filter=evidence_filter,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        counts = result_counts(connection, case_id)
        evidence_total = evidence_count(connection, case_id)
        findings = list_findings(connection, case_id)
        timeline_events = list_timeline_events(connection, case_id)
        last_error_message, last_error_at = latest_error(connection)
        providers = [
            provider_info(provider, connection, case_id, settings["next_run_at"])
            for provider in configured_providers()
        ]
        detailed_provider = provider_info("brave", connection, case_id, settings["next_run_at"])
        configuration_validation = validate_configuration(providers)
        operations = build_operations_status(connection, settings, providers)

    trend_summary = get_news_trends(case_id)
    ready_provider_count = len(provider_names_for_run())

    return FraudMonitorDashboard(
        keyword=FRAUD_KEYWORD,
        case_id=case_id,
        providers=providers,
        detailed_provider=detailed_provider,
        configuration_validation=configuration_validation,
        schedule=row_to_schedule(settings),
        latest_job=jobs[0] if jobs else None,
        jobs=jobs,
        results=results,
        result_page=result_page,
        evidence_count=evidence_total,
        runtime=FraudMonitorRuntime(
            is_running=_job_lock.locked(),
            ready_provider_count=ready_provider_count,
            last_error_message=last_error_message,
            last_error_at=last_error_at,
        ),
        trend_summary=trend_summary,
        total_results=counts["total"],
        pending_results=counts["pending"],
        relevant_results=counts["relevant"],
        not_relevant_results=counts["not_relevant"],
        findings=findings,
        timeline_events=timeline_events,
        operations=operations,
    )


def list_reviewed_results(connection: sqlite3.Connection, case_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT news_results.*,
            news_ingestion_runs.provider AS provider,
            COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
        FROM news_results
        JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
        LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
        WHERE news_results.case_id = ?
            AND news_results.review_status != 'pending'
        ORDER BY news_results.review_status ASC,
            news_results.retrieved_at DESC,
            news_results.created_at DESC
        """,
        (case_id,),
    ).fetchall()
    return attach_artifacts_to_results(connection, [row_to_news_result(row) for row in rows])


def export_limitations() -> list[str]:
    return [
        "Public results are leads for analyst review, not automated fraud conclusions.",
        "The bundle contains local data only and does not synchronize to a cloud service.",
        "Vault artifacts are local preservation aids; source links should still be reopened before external sharing.",
        "Redact sensitive details before sending exports outside the local investigation context.",
    ]


def build_export_bundle() -> FraudMonitorExportBundle:
    generated_at = utc_now()
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        reviewed_results = list_reviewed_results(connection, case_id)
        evidence_rows = [
            FraudMonitorEvidenceTableRow(
                source_url=result["source_url"],
                provider=result["provider"],
                review_status=result["review_status"],
                classification_label=result["classification_label"],
                fraud_state_label=result["fraud_state_label"],
                fraud_state_code=result["fraud_state_code"],
                analyst_note=result["evidence_analyst_note"],
                available_artifact_count=result["available_artifact_count"],
                vault_artifacts=[
                    artifact["storage_path"] or artifact["source_url"]
                    for artifact in result["evidence_artifacts"]
                    if artifact["availability"] == "available"
                ],
                retrieved_at=result["retrieved_at"],
                published_at=result["published_at"],
                title=result["title"] or result["source_url"],
            )
            for result in reviewed_results
        ]
        providers = [
            provider_info(provider, connection, case_id, settings["next_run_at"])
            for provider in configured_providers()
        ]
        evidence_total = evidence_count(connection, case_id)
        artifact_total = available_artifact_count(connection, case_id)
        findings = list_findings(connection, case_id)
        record_timeline_event(
            connection,
            case_id=case_id,
            event_type="export_generation",
            title="Fraud Monitor export generated",
            summary="Local export bundle prepared with reviewed evidence, findings, and timeline context.",
            metadata={
                "reviewed_result_count": len(reviewed_results),
                "evidence_count": evidence_total,
                "finding_count": len(findings),
            },
        )
        timeline_events = list_timeline_events(connection, case_id, limit=100)

    trend_summary = get_news_trends(case_id)
    return FraudMonitorExportBundle(
        metadata=FraudMonitorExportMetadata(
            generated_at=generated_at,
            scope="Fixed-keyword passive public-source fraud monitoring.",
            methodology=(
                "Passive HTTP GET requests to configured public search providers, local review "
                "status decisions, and saved public source links with analyst notes."
            ),
            provider_configuration=providers,
            reviewed_result_count=len(reviewed_results),
            evidence_count=evidence_total,
            finding_count=len(findings),
            timeline_event_count=len(timeline_events),
            available_artifact_count=artifact_total,
            local_only=True,
            responsible_use=(
                "Exports preserve source context and confidence-aware language. They must not be "
                "treated as unsupported allegations or shared without redaction review."
            ),
        ),
        trend_summary=trend_summary,
        evidence_table=evidence_rows,
        reviewed_results=reviewed_results,
        findings=findings,
        timeline_events=timeline_events,
        limitations=export_limitations(),
    )


def markdown_cell(value: str | int) -> str:
    return " ".join(str(value).split()).replace("\\", "\\\\").replace("|", "\\|")


def markdown_table(headers: list[str], rows: list[list[str | int]]) -> list[str]:
    output = [
        "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend("| " + " | ".join(markdown_cell(cell) for cell in row) + " |" for row in rows)
    return output


def export_bundle_to_markdown(bundle: FraudMonitorExportBundle) -> str:
    lines = [
        "# Fraud Monitor Export",
        "",
        "## Export Metadata",
        "",
        f"- Generated at: {bundle.metadata.generated_at}",
        f"- Scope: {bundle.metadata.scope}",
        f"- Methodology: {bundle.metadata.methodology}",
        f"- Reviewed results: {bundle.metadata.reviewed_result_count}",
        f"- Evidence links: {bundle.metadata.evidence_count}",
        f"- Findings: {bundle.metadata.finding_count}",
        f"- Timeline events: {bundle.metadata.timeline_event_count}",
        f"- Available vault artifacts: {bundle.metadata.available_artifact_count}",
        f"- Local only: {'yes' if bundle.metadata.local_only else 'no'}",
        f"- Responsible use: {bundle.metadata.responsible_use}",
        "",
        "## Provider Configuration",
        "",
        *markdown_table(
            ["Provider", "Status", "Request limit", "Timeout", "Last run", "Last issue"],
            [
                [
                    provider.name,
                    provider.status,
                    provider.request_limit,
                    f"{provider.timeout_seconds}s",
                    provider.last_run_status or "not run",
                    provider.last_error_message,
                ]
                for provider in bundle.metadata.provider_configuration
            ],
        ),
        "",
        "## Trend Summary",
        "",
    ]

    if bundle.trend_summary.groups:
        lines.extend(
            markdown_table(
                ["Group", "Count", "Priority cue", "Confidence wording"],
                [
                    [
                        f"{group.group_type}: {group.label}",
                        group.result_count,
                        group.priority_cue,
                        group.confidence_language,
                    ]
                    for group in bundle.trend_summary.groups
                ],
            )
        )
    else:
        lines.append("No trend groups are available yet.")

    lines.extend(["", "## Evidence Table", ""])
    if bundle.evidence_table:
        lines.extend(
            markdown_table(
                [
                    "Title",
                    "Reported category",
                    "Reported state",
                    "Source URL",
                    "Provider",
                    "Review",
                    "Analyst note",
                    "Vault artifacts",
                    "Retrieved",
                    "Published",
                ],
                [
                    [
                        row.title,
                        row.classification_label,
                        row.fraud_state_label,
                        row.source_url,
                        row.provider,
                        row.review_status,
                        row.analyst_note,
                        ", ".join(row.vault_artifacts) or "metadata only",
                        row.retrieved_at,
                        row.published_at,
                    ]
                    for row in bundle.evidence_table
                ],
            )
        )
    else:
        lines.append("No reviewed fraud monitor results are available yet.")

    lines.extend(["", "## Analyst Findings", ""])
    if bundle.findings:
        for finding in bundle.findings:
            evidence_titles = ", ".join(evidence.title for evidence in finding.linked_evidence) or "No linked evidence"
            lines.extend(
                [
                    f"### {finding.title}",
                    "",
                    f"- Confidence: {finding.confidence}",
                    f"- Status: {finding.status}",
                    f"- Summary: {finding.summary}",
                    f"- Linked evidence: {evidence_titles}",
                ]
            )
            if finding.analyst_notes:
                lines.append(f"- Analyst notes: {finding.analyst_notes}")
            lines.append("")
    else:
        lines.append("No analyst-authored findings are available yet.")

    lines.extend(["", "## Timeline", ""])
    if bundle.timeline_events:
        lines.extend(
            markdown_table(
                ["Time", "Event", "Summary"],
                [
                    [
                        event.created_at,
                        event.title,
                        event.summary,
                    ]
                    for event in bundle.timeline_events
                ],
            )
        )
    else:
        lines.append("No timeline events are available yet.")

    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in bundle.limitations)
    lines.append("")
    return "\n".join(lines)


@router.get("/dashboard", response_model=FraudMonitorDashboard)
def get_dashboard(
    search: str = Query(default="", max_length=200),
    review: ReviewStatus | Literal["all"] = "all",
    provider: str = Query(default="all", max_length=80),
    evidence: EvidenceFilter = "all",
    sort: ResultSort = "retrieved_desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> FraudMonitorDashboard:
    return build_dashboard(
        search=search,
        review_filter=review,
        provider_filter=provider,
        evidence_filter=evidence,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/exports/json", response_model=FraudMonitorExportBundle)
def export_json_bundle() -> FraudMonitorExportBundle:
    return build_export_bundle()


@router.get("/exports/markdown", response_class=PlainTextResponse)
def export_markdown_report() -> PlainTextResponse:
    return PlainTextResponse(
        export_bundle_to_markdown(build_export_bundle()),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fraud-monitor-export.md"'},
    )


@router.get("/operations", response_model=OperationsStatus)
def get_operations_status() -> OperationsStatus:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        providers = [
            provider_info(provider, connection, case_id, settings["next_run_at"])
            for provider in configured_providers()
        ]
        return build_operations_status(connection, settings, providers)


@router.post("/operations/backups", response_model=OperationsBackupArtifact, status_code=status.HTTP_201_CREATED)
def create_operations_backup(payload: OperationsBackupCreate | None = None) -> OperationsBackupArtifact:
    note = payload.note if payload is not None else ""
    generated_at = utc_now()
    safe_stamp = generated_at.replace(":", "").replace("-", "").replace("Z", "Z")
    filename = f"fraud-monitor-backup-{safe_stamp}.json"
    path = operation_exports_dir() / filename
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        providers = [
            provider_info(provider, connection, case_id, settings["next_run_at"])
            for provider in configured_providers()
        ]
        operations = build_operations_status(connection, settings, providers)

    bundle = build_export_bundle()
    payload_json = {
        "metadata": {
            "generated_at": generated_at,
            "note": note,
            "local_only": True,
            "includes": [
                "operation health snapshot",
                "provider configuration",
                "reviewed export bundle",
                "retention plan",
            ],
            "responsible_use": (
                "This artifact is generated locally. Review and redact before sharing outside "
                "the local investigation context."
            ),
        },
        "operations": operations.model_dump(mode="json"),
        "export_bundle": bundle.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload_json, indent=2, sort_keys=True), encoding="utf-8")
    return OperationsBackupArtifact(
        filename=path.name,
        path=str(path),
        byte_size=path.stat().st_size,
        created_at=backup_created_at(path),
        includes=payload_json["metadata"]["includes"],
        download_url=f"/fraud-monitor/operations/backups/{path.name}",
    )


@router.get("/operations/backups/{filename}", response_class=PlainTextResponse)
def download_operations_backup(filename: str) -> PlainTextResponse:
    if "/" in filename or "\\" in filename or not filename.startswith("fraud-monitor-backup-"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup artifact not found.")
    path = (operation_exports_dir() / filename).resolve()
    exports_dir = operation_exports_dir().resolve()
    if exports_dir not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup artifact not found.")
    return PlainTextResponse(
        path.read_text(encoding="utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@router.delete("/operations/retention-candidates", response_model=OperationsCleanupResult)
def cleanup_retention_candidates(payload: OperationsCleanupRequest) -> OperationsCleanupResult:
    deleted_count = 0
    deleted_bytes = 0
    for candidate_id in dict.fromkeys(payload.candidate_ids):
        path = resolve_retention_candidate(candidate_id)
        if path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more retention candidates were not found.",
            )
        size = path.stat().st_size
        path.unlink()
        deleted_count += 1
        deleted_bytes += size
    return OperationsCleanupResult(
        deleted_count=deleted_count,
        deleted_bytes=deleted_bytes,
        remaining_candidates=list_retention_candidates(max_age_days=0),
    )


@router.get("/findings", response_model=list[FindingRecord])
def get_findings() -> list[FindingRecord]:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        return list_findings(connection, settings["case_id"])


@router.post("/findings", response_model=FindingRecord, status_code=status.HTTP_201_CREATED)
def create_finding(payload: FindingCreate) -> FindingRecord:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        validate_evidence_links(connection, case_id, payload.evidence_link_ids)
        finding_id = str(uuid4())
        now = utc_now()
        connection.execute(
            """
            INSERT INTO findings (
                id,
                case_id,
                title,
                summary,
                confidence,
                status,
                analyst_notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding_id,
                case_id,
                payload.title,
                payload.summary,
                payload.confidence,
                payload.status,
                payload.analyst_notes,
                now,
                now,
            ),
        )
        replace_finding_evidence_links(
            connection,
            finding_id=finding_id,
            evidence_link_ids=payload.evidence_link_ids,
            created_at=now,
        )
        record_timeline_event(
            connection,
            case_id=case_id,
            event_type="finding_create",
            title="Finding created",
            summary=f"Analyst-authored finding: {payload.title}",
            related_finding_id=finding_id,
            metadata={
                "confidence": payload.confidence,
                "status": payload.status,
                "linked_evidence_count": len(payload.evidence_link_ids),
            },
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
        return get_finding_record_or_404(connection, finding_id, case_id)


@router.patch("/findings/{finding_id}", response_model=FindingRecord)
def update_finding(finding_id: str, payload: FindingUpdate) -> FindingRecord:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        existing = get_finding_or_404(connection, finding_id, case_id)
        if payload.evidence_link_ids is not None:
            validate_evidence_links(connection, case_id, payload.evidence_link_ids)
        title = payload.title if payload.title is not None else existing["title"]
        summary = payload.summary if payload.summary is not None else existing["summary"]
        confidence = payload.confidence if payload.confidence is not None else existing["confidence"]
        finding_status = payload.status if payload.status is not None else existing["status"]
        analyst_notes = (
            payload.analyst_notes
            if payload.analyst_notes is not None
            else existing["analyst_notes"]
        )
        now = utc_now()
        connection.execute(
            """
            UPDATE findings
            SET title = ?,
                summary = ?,
                confidence = ?,
                status = ?,
                analyst_notes = ?,
                updated_at = ?
            WHERE id = ? AND case_id = ?
            """,
            (
                title,
                summary,
                confidence,
                finding_status,
                analyst_notes,
                now,
                finding_id,
                case_id,
            ),
        )
        if payload.evidence_link_ids is not None:
            replace_finding_evidence_links(
                connection,
                finding_id=finding_id,
                evidence_link_ids=payload.evidence_link_ids,
                created_at=now,
            )
        record_timeline_event(
            connection,
            case_id=case_id,
            event_type="finding_update",
            title="Finding updated",
            summary=f"Analyst-updated finding: {title}",
            related_finding_id=finding_id,
            metadata={
                "confidence": confidence,
                "status": finding_status,
                "linked_evidence_count": len(payload.evidence_link_ids or []),
            },
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
        return get_finding_record_or_404(connection, finding_id, case_id)


@router.get("/configuration/validation", response_model=FraudMonitorConfigurationValidation)
def get_configuration_validation() -> FraudMonitorConfigurationValidation:
    return validate_configuration()


@router.post("/jobs", response_model=FraudMonitorJob)
def create_job(payload: FraudMonitorJobCreate | None = None) -> FraudMonitorJob:
    search_mode = payload.search_mode if payload is not None else "standard"
    return create_fraud_monitor_job("manual", search_mode)


@router.patch("/schedule", response_model=FraudMonitorSchedule)
def update_schedule(payload: FraudMonitorScheduleUpdate) -> FraudMonitorSchedule:
    with connect() as connection:
        current = ensure_monitor_settings(connection)
        enabled = bool(current["enabled"]) if payload.enabled is None else payload.enabled
        interval_minutes = (
            int(current["interval_minutes"])
            if payload.interval_minutes is None
            else payload.interval_minutes
        )
        now = utc_now()
        next_run_at = current["next_run_at"]
        if payload.enabled is not None or payload.interval_minutes is not None:
            next_run_at = minutes_from_now(interval_minutes)
        connection.execute(
            """
            UPDATE fraud_monitor_settings
            SET enabled = ?,
                interval_minutes = ?,
                next_run_at = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (1 if enabled else 0, interval_minutes, next_run_at, now),
        )
        row = connection.execute("SELECT * FROM fraud_monitor_settings WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("Fraud monitor schedule was not stored.")
    return row_to_schedule(dict(row))


@router.patch("/results/{result_id}", response_model=NewsResultRecord)
def update_result(result_id: str, payload: NewsResultUpdate) -> dict[str, Any]:
    with connect() as connection:
        result = get_news_result_or_404(result_id, connection)
        settings = ensure_monitor_settings(connection)
        if result["case_id"] != settings["case_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    updated = update_news_result(result_id, payload)
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        record_timeline_event(
            connection,
            case_id=settings["case_id"],
            event_type="review_update",
            title="Review status updated",
            summary=f"Result marked {payload.review_status.replace('_', ' ')}.",
            related_result_id=result_id,
            metadata={"review_status": payload.review_status},
        )
    return updated


@router.patch("/review-batches", response_model=FraudMonitorBulkReviewResult)
def bulk_update_results(payload: FraudMonitorBulkReviewUpdate) -> FraudMonitorBulkReviewResult:
    result_ids = list(dict.fromkeys(payload.result_ids))
    placeholders = ", ".join("?" for _ in result_ids)
    now = utc_now()
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        existing_rows = connection.execute(
            f"""
            SELECT id
            FROM news_results
            WHERE case_id = ? AND id IN ({placeholders})
            """,
            tuple([case_id, *result_ids]),
        ).fetchall()
        existing_ids = {row["id"] for row in existing_rows}
        if existing_ids != set(result_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more results were not found.")

        connection.execute(
            f"""
            UPDATE news_results
            SET review_status = ?
            WHERE case_id = ? AND id IN ({placeholders})
            """,
            tuple([payload.review_status, case_id, *result_ids]),
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (now, case_id))
        record_timeline_event(
            connection,
            case_id=case_id,
            event_type="review_update",
            title="Bulk review status updated",
            summary=f"{len(existing_ids)} result(s) marked {payload.review_status.replace('_', ' ')}.",
            metadata={
                "review_status": payload.review_status,
                "result_count": len(existing_ids),
            },
        )
        rows = connection.execute(
            f"""
            SELECT news_results.*,
                news_ingestion_runs.provider AS provider,
                COALESCE(evidence_links.analyst_note, '') AS evidence_analyst_note
            FROM news_results
            JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
            LEFT JOIN evidence_links ON evidence_links.id = news_results.evidence_link_id
            WHERE news_results.case_id = ? AND news_results.id IN ({placeholders})
            ORDER BY news_results.retrieved_at DESC, news_results.created_at DESC
            """,
            tuple([case_id, *result_ids]),
        ).fetchall()

    return FraudMonitorBulkReviewResult(
        updated_count=len(rows),
        results=[row_to_news_result(row) for row in rows],
    )


@router.post(
    "/results/{result_id}/evidence-links",
    response_model=EvidenceLinkRecord,
    status_code=201,
)
def save_result_evidence(result_id: str, payload: EvidenceLinkCreate) -> dict[str, Any]:
    with connect() as connection:
        result = get_news_result_or_404(result_id, connection)
        settings = ensure_monitor_settings(connection)
        if result["case_id"] != settings["case_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")
    evidence = save_news_result_as_evidence(result_id, payload)
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        record_timeline_event(
            connection,
            case_id=settings["case_id"],
            event_type="evidence_save",
            title="Evidence link saved",
            summary=evidence["title"] or evidence["source_url"],
            related_result_id=result_id,
            related_evidence_link_id=evidence["id"],
            metadata={"source_url": evidence["source_url"]},
        )
    return evidence


@router.patch("/evidence-links/{evidence_link_id}", response_model=EvidenceLinkRecord)
def update_result_evidence_note(
    evidence_link_id: str,
    payload: EvidenceLinkUpdate,
) -> dict[str, Any]:
    with connect() as connection:
        evidence_link = get_evidence_link_or_404(evidence_link_id, connection)
        settings = ensure_monitor_settings(connection)
        if evidence_link["case_id"] != settings["case_id"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence link not found.")
    updated = update_evidence_link(evidence_link_id, payload)
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        record_timeline_event(
            connection,
            case_id=settings["case_id"],
            event_type="evidence_update",
            title="Evidence note updated",
            summary=updated["title"] or updated["source_url"],
            related_result_id=updated["news_result_id"],
            related_evidence_link_id=evidence_link_id,
            metadata={"source_url": updated["source_url"]},
        )
    return updated


def run_due_fraud_monitor_jobs() -> None:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        if not settings["enabled"]:
            return
        if parse_utc(settings["next_run_at"]) > datetime.now(UTC):
            return
    if not _job_lock.acquire(blocking=False):
        return
    try:
        run_fraud_monitor_job_locked("scheduled")
    finally:
        _job_lock.release()


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(run_due_fraud_monitor_jobs)
        except Exception:
            # The dashboard records provider failures; scheduler failures should not kill the API.
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=get_settings().fraud_monitor_scheduler_seconds)
        except TimeoutError:
            continue


def start_scheduler() -> None:
    global _scheduler_stop_event, _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(scheduler_loop(_scheduler_stop_event))


async def stop_scheduler() -> None:
    global _scheduler_stop_event, _scheduler_task
    if _scheduler_stop_event is not None:
        _scheduler_stop_event.set()
    if _scheduler_task is not None:
        await _scheduler_task
    _scheduler_stop_event = None
    _scheduler_task = None
