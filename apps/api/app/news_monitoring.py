from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
import re
import sqlite3
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from xml.etree import ElementTree

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.cases import connect, get_case_or_404, normalize_long_text, normalize_required_text
from app.core.config import get_settings


RunStatus = Literal["success", "partial", "failed"]
ReviewStatus = Literal["pending", "relevant", "not_relevant"]
TrendGroupType = Literal["keyword", "source", "time_window", "theme"]

NEWS_TIMEOUT_SECONDS = 8
MAX_NEWS_BODY_BYTES = 512_000
MAX_KEYWORDS = 12
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
    theme: str
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
    result_count: int
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

    @field_validator("analyst_note")
    @classmethod
    def clean_analyst_note(cls, value: str) -> str:
        return normalize_long_text(value)


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


class TrendGroup(BaseModel):
    group_type: TrendGroupType
    label: str
    result_count: int
    sample_titles: list[str]
    source_attribution: list[str]
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
    payload["saved_as_evidence"] = bool(payload["saved_as_evidence"])
    return payload


def row_to_news_run(row: sqlite3.Row, results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = dict(row)
    payload["query_keywords"] = decode_json_list(payload.pop("query_keywords_json"))
    payload["results"] = results or []
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


def search_gdelt(keyword: str, max_results: int) -> list[ProviderResult]:
    params = urlencode(
        {
            "query": keyword,
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


def search_google_news_rss(keyword: str, max_results: int) -> list[ProviderResult]:
    params = urlencode({"q": keyword, "hl": "en-US", "gl": "US", "ceid": "US:en"})
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
    params = urlencode(
        {
            "query": keyword,
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

    params = urlencode({"q": keyword, "count": max(1, min(max_results, 20)), "freshness": "pm"})
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


def search_public_news(keyword: str, max_results: int | None = None) -> list[ProviderResult]:
    settings = get_settings()
    limit = max_results or settings.news_search_max_results
    provider = settings.news_search_provider.lower()

    if provider == "brave":
        return search_brave(keyword, limit)
    if provider == "gdelt":
        return search_gdelt(keyword, limit)
    if provider == "google_news_rss":
        return search_google_news_rss(keyword, limit)
    if provider == "hn_algolia":
        return search_hn_algolia(keyword, limit)
    raise RuntimeError(f"Unsupported news provider: {settings.news_search_provider}.")


def infer_theme(title: str, snippet: str) -> str:
    words = re.findall(r"[a-z0-9]{4,}", f"{title} {snippet}".lower())
    candidates = [word for word in words if word not in STOP_WORDS]
    if not candidates:
        return "general public reporting"
    common = Counter(candidates).most_common(2)
    return " ".join(word for word, _ in common)


def store_news_results(
    connection: sqlite3.Connection,
    case_id: str,
    run_id: str,
    results: list[ProviderResult],
) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for result in results:
        result_id = str(uuid4())
        created_at = utc_now()
        theme = infer_theme(result.title, result.snippet)
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
                theme,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, source_url, keyword) DO UPDATE SET
                run_id = excluded.run_id,
                publisher = excluded.publisher,
                title = excluded.title,
                snippet = excluded.snippet,
                published_at = excluded.published_at,
                retrieved_at = excluded.retrieved_at,
                theme = excluded.theme
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
                theme,
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
        if row is not None:
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
        SELECT *
        FROM news_results
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
                "SELECT * FROM news_results WHERE run_id = ? ORDER BY retrieved_at DESC",
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
            SELECT *
            FROM news_results
            WHERE case_id = ?
            ORDER BY retrieved_at DESC, created_at DESC
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
            return dict(existing)

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
        row = connection.execute("SELECT * FROM evidence_links WHERE id = ?", (evidence_id,)).fetchone()
    if row is None:
        raise RuntimeError("Evidence link was not stored.")
    return dict(row)


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
    return [dict(row) for row in rows]


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
    return TrendGroup(
        group_type=group_type,
        label=label,
        result_count=count,
        sample_titles=sample_titles,
        source_attribution=publishers,
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
                SELECT *
                FROM news_results
                WHERE case_id = ?
                ORDER BY retrieved_at DESC, created_at DESC
                """,
                (case_id,),
            ).fetchall()
        ]

    group_rows: list[TrendGroup] = []
    for group_type, key_fn in (
        ("keyword", lambda row: row["keyword"]),
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
