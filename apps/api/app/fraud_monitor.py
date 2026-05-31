from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import sqlite3
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.cases import connect
from app.core.config import get_settings
from app.news_monitoring import (
    EvidenceLinkCreate,
    EvidenceLinkRecord,
    NewsResultRecord,
    NewsResultUpdate,
    RunStatus,
    TrendSummary,
    get_news_result_or_404,
    get_news_trends,
    row_to_news_result,
    save_news_result_as_evidence,
    search_public_news_with_provider,
    store_news_results,
    summarize_run_status,
    update_news_result,
)


router = APIRouter(prefix="/fraud-monitor", tags=["fraud monitor"])

FRAUD_KEYWORD = "fraud"
FRAUD_MONITOR_CASE_ID = "fraud-monitor-system-case"
DEFAULT_INTERVAL_MINUTES = 60

TriggerType = Literal["manual", "scheduled"]
ProviderStatus = Literal["ready", "needs_key", "unsupported"]

_scheduler_task: asyncio.Task[None] | None = None
_scheduler_stop_event: asyncio.Event | None = None


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


class FraudMonitorDashboard(BaseModel):
    keyword: str
    case_id: str
    providers: list[ProviderInfo]
    schedule: FraudMonitorSchedule
    latest_job: FraudMonitorJob | None
    jobs: list[FraudMonitorJob]
    results: list[NewsResultRecord]
    evidence_count: int
    trend_summary: TrendSummary
    total_results: int
    pending_results: int
    relevant_results: int
    not_relevant_results: int


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


def provider_info(provider: str) -> ProviderInfo:
    settings = get_settings()
    if provider == "brave" and not settings.brave_search_api_key:
        return ProviderInfo(
            name=provider,
            status="needs_key",
            note="Set BRAVE_SEARCH_API_KEY before using Brave News Search.",
        )
    if provider not in {"brave", "gdelt", "google_news_rss", "hn_algolia"}:
        return ProviderInfo(
            name=provider,
            status="unsupported",
            note="Unsupported provider; remove it from OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS.",
        )
    return ProviderInfo(name=provider, status="ready", note="Ready for passive public search.")


def provider_names_for_run() -> list[str]:
    return [info.name for info in map(provider_info, configured_providers()) if info.status == "ready"]


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


def list_results(connection: sqlite3.Connection, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM news_results
        WHERE case_id = ?
        ORDER BY retrieved_at DESC, created_at DESC
        LIMIT ?
        """,
        (case_id, limit),
    ).fetchall()
    return [row_to_news_result(row) for row in rows]


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
        errors.append(f"{provider}: {exc}")

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


def create_fraud_monitor_job(trigger_type: TriggerType = "manual") -> FraudMonitorJob:
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
        connection.execute(
            """
            UPDATE fraud_monitor_jobs
            SET status = ?,
                completed_at = ?,
                result_count = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, completed_at, result_count, "; ".join(errors), job_id),
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
            (started_at, completed_at, minutes_from_now(interval_minutes), completed_at),
        )
        connection.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (completed_at, case_id))
        row = connection.execute("SELECT * FROM fraud_monitor_jobs WHERE id = ?", (job_id,)).fetchone()

    if row is None:
        raise RuntimeError("Fraud monitor job was not stored.")
    return row_to_job(row, [provider for _, provider in run_ids])


def build_dashboard() -> FraudMonitorDashboard:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        case_id = settings["case_id"]
        jobs = list_jobs(connection)
        results = list_results(connection, case_id)
        counts = result_counts(connection, case_id)
        evidence_total = evidence_count(connection, case_id)

    trend_summary = get_news_trends(case_id)

    return FraudMonitorDashboard(
        keyword=FRAUD_KEYWORD,
        case_id=case_id,
        providers=[provider_info(provider) for provider in configured_providers()],
        schedule=row_to_schedule(settings),
        latest_job=jobs[0] if jobs else None,
        jobs=jobs,
        results=results,
        evidence_count=evidence_total,
        trend_summary=trend_summary,
        total_results=counts["total"],
        pending_results=counts["pending"],
        relevant_results=counts["relevant"],
        not_relevant_results=counts["not_relevant"],
    )


@router.get("/dashboard", response_model=FraudMonitorDashboard)
def get_dashboard() -> FraudMonitorDashboard:
    return build_dashboard()


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


def run_due_fraud_monitor_jobs() -> None:
    with connect() as connection:
        settings = ensure_monitor_settings(connection)
        if not settings["enabled"]:
            return
        if parse_utc(settings["next_run_at"]) > datetime.now(UTC):
            return
    create_fraud_monitor_job("scheduled")


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
