from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import sqlite3
import threading
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.cases import connect
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
ProviderStatus = Literal["ready", "missing_config", "unsupported", "timeout", "partial_success"]
EvidenceFilter = Literal["all", "saved", "unsaved"]
ValidationSeverity = Literal["error", "warning", "info"]
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


class FraudMonitorBulkReviewUpdate(BaseModel):
    result_ids: list[str] = Field(min_length=1, max_length=200)
    review_status: ReviewStatus


class FraudMonitorBulkReviewResult(BaseModel):
    updated_count: int
    results: list[NewsResultRecord]


class FraudMonitorExportMetadata(BaseModel):
    generated_at: str
    scope: str
    methodology: str
    provider_configuration: list[ProviderInfo]
    reviewed_result_count: int
    evidence_count: int
    local_only: bool
    responsible_use: str


class FraudMonitorEvidenceTableRow(BaseModel):
    source_url: str
    provider: str
    review_status: ReviewStatus
    analyst_note: str
    retrieved_at: str
    published_at: str
    title: str


class FraudMonitorExportBundle(BaseModel):
    metadata: FraudMonitorExportMetadata
    trend_summary: TrendSummary
    evidence_table: list[FraudMonitorEvidenceTableRow]
    reviewed_results: list[NewsResultRecord]
    limitations: list[str]


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
        provider_runs = [
            provider_row["provider"]
            for provider_row in connection.execute(
                """
                SELECT provider
                FROM fraud_monitor_job_runs
                WHERE job_id = ?
                ORDER BY provider
                """,
                (row["id"],),
            ).fetchall()
        ]
        jobs.append(row_to_job(row, provider_runs))
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
            )"""
        )
        search_param = f"%{cleaned_search.lower()}%"
        params.extend([search_param, search_param, search_param, search_param, search_param])
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
    return [row_to_news_result(row) for row in rows], page


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
            result_count,
            error_message,
            created_at
        )
        VALUES (?, ?, NULL, ?, 'failed', ?, ?, ?, 0, '', ?)
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
    stored_results = store_news_results(connection, case_id, run_id, provider_results)
    completed_at = utc_now()
    run_status, error_message = summarize_run_status([keyword], errors, len(stored_results))
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
    return run_id, run_status, len(stored_results), error_message


def run_fraud_monitor_job_locked(trigger_type: TriggerType = "manual") -> FraudMonitorJob:
    job_id = str(uuid4())
    started_at = utc_now()

    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        providers = provider_names_for_run()
        errors: list[str] = []
        result_count = 0
        successful_provider_runs = 0
        run_ids: list[tuple[str, str]] = []

        if not providers:
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
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (completed_at, case_id))
        row = connection.execute("SELECT * FROM fraud_monitor_jobs WHERE id = ?", (job_id,)).fetchone()

    if row is None:
        raise RuntimeError("Fraud monitor job was not stored.")
    return row_to_job(row, [provider for _, provider in run_ids])


def create_fraud_monitor_job(trigger_type: TriggerType = "manual") -> FraudMonitorJob:
    if not _job_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fraud monitor job is already running.",
        )
    try:
        return run_fraud_monitor_job_locked(trigger_type)
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
        last_error_message, last_error_at = latest_error(connection)
        providers = [
            provider_info(provider, connection, case_id, settings["next_run_at"])
            for provider in configured_providers()
        ]
        configuration_validation = validate_configuration(providers)

    trend_summary = get_news_trends(case_id)
    ready_provider_count = len(provider_names_for_run())

    return FraudMonitorDashboard(
        keyword=FRAUD_KEYWORD,
        case_id=case_id,
        providers=providers,
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
    return [row_to_news_result(row) for row in rows]


def export_limitations() -> list[str]:
    return [
        "Public results are leads for analyst review, not automated fraud conclusions.",
        "The bundle contains local data only and does not synchronize to a cloud service.",
        "Source links should be reopened before external sharing because public pages can change.",
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
                analyst_note=result["evidence_analyst_note"],
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
            local_only=True,
            responsible_use=(
                "Exports preserve source context and confidence-aware language. They must not be "
                "treated as unsupported allegations or shared without redaction review."
            ),
        ),
        trend_summary=trend_summary,
        evidence_table=evidence_rows,
        reviewed_results=reviewed_results,
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
                ["Title", "Source URL", "Provider", "Review", "Analyst note", "Retrieved", "Published"],
                [
                    [
                        row.title,
                        row.source_url,
                        row.provider,
                        row.review_status,
                        row.analyst_note,
                        row.retrieved_at,
                        row.published_at,
                    ]
                    for row in bundle.evidence_table
                ],
            )
        )
    else:
        lines.append("No reviewed fraud monitor results are available yet.")

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


@router.get("/configuration/validation", response_model=FraudMonitorConfigurationValidation)
def get_configuration_validation() -> FraudMonitorConfigurationValidation:
    return validate_configuration()


@router.post("/jobs", response_model=FraudMonitorJob)
def create_job() -> FraudMonitorJob:
    return create_fraud_monitor_job("manual")


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
    return update_news_result(result_id, payload)


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
    return save_news_result_as_evidence(result_id, payload)


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
    return update_evidence_link(evidence_link_id, payload)


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
