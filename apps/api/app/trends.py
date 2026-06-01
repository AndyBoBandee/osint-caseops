from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import json
import sqlite3
from typing import Any, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.cases import connect
from app.provider_registry import all_provider_metadata


router = APIRouter(prefix="/api/trends", tags=["trends"])

ReviewFilter = Literal["pending", "relevant", "not_relevant"]


class TrendFilters(BaseModel):
    from_date: str = ""
    to_date: str = ""
    source_type: str = ""
    confidence: str = ""
    fraud_category: str = ""
    state: str = ""
    review_status: ReviewFilter | Literal[""] = ""


class TrendBucket(BaseModel):
    label: str
    result_count: int
    source_count: int = 0
    sample_titles: list[str] = Field(default_factory=list)


class TrendAlert(BaseModel):
    title: str
    provider: str
    source_type: str
    source_confidence: str
    fraud_category: str
    state: str
    published_date: str
    source_url: str


class ProviderHealthRecord(BaseModel):
    provider: str
    display_name: str
    source_type: str
    source_confidence: str
    last_run_at: str
    last_success_at: str
    last_error: str
    results_last_24h: int
    enabled: bool
    default_enabled: bool
    fixture_mode_available: bool
    requires_api_key: bool
    tier: str


class TrendOverview(BaseModel):
    generated_at: str
    filters: TrendFilters
    top_categories_this_week: list[TrendBucket]
    official_source_alerts: list[TrendAlert]
    state_activity: list[TrendBucket]
    payment_rail_mentions: list[TrendBucket]
    emerging_keywords: list[TrendBucket]
    provider_health: list[ProviderHealthRecord]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)]


def build_where(filters: TrendFilters, case_id: str | None = None) -> tuple[str, list[Any]]:
    clauses = []
    params: list[Any] = []
    if case_id:
        clauses.append("news_results.case_id = ?")
        params.append(case_id)
    if filters.from_date:
        clauses.append("COALESCE(NULLIF(news_results.published_date, ''), substr(news_results.retrieved_at, 1, 10)) >= ?")
        params.append(filters.from_date)
    if filters.to_date:
        clauses.append("COALESCE(NULLIF(news_results.published_date, ''), substr(news_results.retrieved_at, 1, 10)) <= ?")
        params.append(filters.to_date)
    if filters.source_type:
        clauses.append("news_results.source_type = ?")
        params.append(filters.source_type)
    if filters.confidence:
        clauses.append("(news_results.source_confidence = ? OR news_results.classification_confidence = ?)")
        params.extend([filters.confidence, filters.confidence])
    if filters.fraud_category:
        clauses.append("news_results.fraud_category = ?")
        params.append(filters.fraud_category)
    if filters.state:
        clauses.append("(news_results.state = ? OR news_results.fraud_state_code = ?)")
        params.extend([filters.state, filters.state])
    if filters.review_status:
        clauses.append("news_results.review_status = ?")
        params.append(filters.review_status)
    return (" AND ".join(clauses) if clauses else "1 = 1"), params


def fetch_rows(connection: sqlite3.Connection, filters: TrendFilters, case_id: str | None = None) -> list[dict[str, Any]]:
    where_clause, params = build_where(filters, case_id)
    rows = connection.execute(
        f"""
        SELECT news_results.*,
            news_ingestion_runs.provider AS provider
        FROM news_results
        JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
        WHERE {where_clause}
        ORDER BY news_results.retrieved_at DESC, news_results.created_at DESC
        """,
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


def bucket_rows(rows: list[dict[str, Any]], field: str, fallback: str = "unknown", limit: int = 8) -> list[TrendBucket]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        label = str(row.get(field) or fallback)
        grouped[label].append(row)
    buckets = []
    for label, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]:
        buckets.append(
            TrendBucket(
                label=label,
                result_count=len(group),
                source_count=len({row.get("publisher") or row.get("provider") or "" for row in group}),
                sample_titles=[str(row.get("title") or row.get("source_url") or "") for row in group[:3]],
            )
        )
    return buckets


def keyword_buckets(rows: list[dict[str, Any]], limit: int = 10) -> list[TrendBucket]:
    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for keyword in parse_list(str(row.get("keywords_detected_json") or "[]")):
            counter[keyword] += 1
            if len(samples[keyword]) < 3:
                samples[keyword].append(str(row.get("title") or row.get("source_url") or ""))
    return [
        TrendBucket(label=label, result_count=count, sample_titles=samples[label])
        for label, count in counter.most_common(limit)
    ]


def official_alerts(rows: list[dict[str, Any]], limit: int = 8) -> list[TrendAlert]:
    alerts = []
    for row in rows:
        if row.get("source_confidence") != "high":
            continue
        alerts.append(
            TrendAlert(
                title=str(row.get("title") or row.get("source_url") or ""),
                provider=str(row.get("provider") or ""),
                source_type=str(row.get("source_type") or ""),
                source_confidence=str(row.get("source_confidence") or ""),
                fraud_category=str(row.get("fraud_category") or "unknown"),
                state=str(row.get("state") or row.get("fraud_state_code") or ""),
                published_date=str(row.get("published_date") or ""),
                source_url=str(row.get("source_url") or ""),
            )
        )
        if len(alerts) >= limit:
            break
    return alerts


def provider_health(connection: sqlite3.Connection) -> list[ProviderHealthRecord]:
    records = []
    for metadata in all_provider_metadata():
        last_row = connection.execute(
            """
            SELECT provider, completed_at, status, error_message
            FROM news_ingestion_runs
            WHERE provider = ?
            ORDER BY completed_at DESC, created_at DESC
            LIMIT 1
            """,
            (metadata.provider_id,),
        ).fetchone()
        success_row = connection.execute(
            """
            SELECT completed_at
            FROM news_ingestion_runs
            WHERE provider = ? AND status IN ('success', 'partial') AND result_count > 0
            ORDER BY completed_at DESC, created_at DESC
            LIMIT 1
            """,
            (metadata.provider_id,),
        ).fetchone()
        count_row = connection.execute(
            """
            SELECT COUNT(news_results.id) AS count
            FROM news_results
            JOIN news_ingestion_runs ON news_ingestion_runs.id = news_results.run_id
            WHERE news_ingestion_runs.provider = ?
                AND datetime(news_results.retrieved_at) >= datetime('now', '-1 day')
            """,
            (metadata.provider_id,),
        ).fetchone()
        records.append(
            ProviderHealthRecord(
                provider=metadata.provider_id,
                display_name=metadata.display_name,
                source_type=metadata.source_type,
                source_confidence=metadata.source_confidence,
                last_run_at=last_row["completed_at"] if last_row else "",
                last_success_at=success_row["completed_at"] if success_row else "",
                last_error=last_row["error_message"] if last_row and last_row["error_message"] else "",
                results_last_24h=int(count_row["count"] if count_row else 0),
                enabled=metadata.enabled,
                default_enabled=metadata.default_enabled,
                fixture_mode_available=metadata.fixture_mode_supported,
                requires_api_key=metadata.requires_api_key,
                tier=metadata.tier,
            )
        )
    return records


def default_filters(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = "",
) -> TrendFilters:
    return TrendFilters(
        from_date=from_date,
        to_date=to_date,
        source_type=source_type,
        confidence=confidence,
        fraud_category=fraud_category,
        state=state,
        review_status=review_status,
    )


def build_trend_overview(filters: TrendFilters | None = None, case_id: str | None = None) -> TrendOverview:
    filters = filters or TrendFilters()
    week_start = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()
    weekly_filters = filters.model_copy(update={"from_date": filters.from_date or week_start})
    with connect() as connection:
        rows = fetch_rows(connection, filters, case_id)
        weekly_rows = fetch_rows(connection, weekly_filters, case_id)
        health = provider_health(connection)
    return TrendOverview(
        generated_at=utc_now(),
        filters=filters,
        top_categories_this_week=bucket_rows(weekly_rows, "fraud_category"),
        official_source_alerts=official_alerts(rows),
        state_activity=bucket_rows(rows, "state"),
        payment_rail_mentions=bucket_rows(rows, "payment_rail"),
        emerging_keywords=keyword_buckets(rows),
        provider_health=health,
    )


@router.get("/summary", response_model=TrendOverview)
def get_trend_summary(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = Query(default=""),
) -> TrendOverview:
    return build_trend_overview(
        default_filters(from_date, to_date, source_type, confidence, fraud_category, state, review_status)
    )


@router.get("/categories", response_model=list[TrendBucket])
def get_category_trends(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = Query(default=""),
) -> list[TrendBucket]:
    filters = default_filters(from_date, to_date, source_type, confidence, fraud_category, state, review_status)
    with connect() as connection:
        return bucket_rows(fetch_rows(connection, filters), "fraud_category")


@router.get("/states", response_model=list[TrendBucket])
def get_state_trends(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = Query(default=""),
) -> list[TrendBucket]:
    filters = default_filters(from_date, to_date, source_type, confidence, fraud_category, state, review_status)
    with connect() as connection:
        return bucket_rows(fetch_rows(connection, filters), "state")


@router.get("/payment-rails", response_model=list[TrendBucket])
def get_payment_rail_trends(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = Query(default=""),
) -> list[TrendBucket]:
    filters = default_filters(from_date, to_date, source_type, confidence, fraud_category, state, review_status)
    with connect() as connection:
        return bucket_rows(fetch_rows(connection, filters), "payment_rail")


@router.get("/watchlist", response_model=list[TrendBucket])
def get_watchlist_trends(
    from_date: str = "",
    to_date: str = "",
    source_type: str = "",
    confidence: str = "",
    fraud_category: str = "",
    state: str = "",
    review_status: ReviewFilter | Literal[""] = Query(default=""),
) -> list[TrendBucket]:
    filters = default_filters(from_date, to_date, source_type, confidence, fraud_category, state, review_status)
    with connect() as connection:
        return keyword_buckets(fetch_rows(connection, filters))
