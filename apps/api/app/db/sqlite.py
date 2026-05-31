from datetime import UTC, datetime
import sqlite3

from app.core.config import get_settings


def initialize_database() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_health (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                checked_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                objective TEXT NOT NULL,
                scope_category TEXT NOT NULL,
                scope_notes TEXT NOT NULL DEFAULT '',
                case_type TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'archived', 'closed')),
                scope_acknowledged INTEGER NOT NULL CHECK (scope_acknowledged IN (0, 1)),
                scope_acknowledged_at TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                analyst_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON cases(updated_at);

            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                type TEXT NOT NULL CHECK (
                    type IN ('domain', 'url', 'email', 'ip_address', 'organization')
                ),
                value TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                confidence TEXT NOT NULL CHECK (
                    confidence IN ('high', 'medium', 'low', 'unknown')
                ),
                tags_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id, type, value)
            );

            CREATE INDEX IF NOT EXISTS idx_entities_case_id ON entities(case_id);
            CREATE INDEX IF NOT EXISTS idx_entities_value ON entities(value);

            CREATE TABLE IF NOT EXISTS enrichment_runs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                module_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                result_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_enrichment_runs_case_id
                ON enrichment_runs(case_id);
            CREATE INDEX IF NOT EXISTS idx_enrichment_runs_entity_id
                ON enrichment_runs(entity_id);
            CREATE INDEX IF NOT EXISTS idx_enrichment_runs_created_at
                ON enrichment_runs(created_at);

            CREATE TABLE IF NOT EXISTS news_keyword_sets (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                keywords_json TEXT NOT NULL DEFAULT '[]',
                scope_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_news_keyword_sets_case_id
                ON news_keyword_sets(case_id);

            CREATE TABLE IF NOT EXISTS news_ingestion_runs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                keyword_set_id TEXT REFERENCES news_keyword_sets(id) ON DELETE SET NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                query_keywords_json TEXT NOT NULL DEFAULT '[]',
                result_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_news_ingestion_runs_case_id
                ON news_ingestion_runs(case_id);
            CREATE INDEX IF NOT EXISTS idx_news_ingestion_runs_created_at
                ON news_ingestion_runs(created_at);

            CREATE TABLE IF NOT EXISTS news_results (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                run_id TEXT NOT NULL REFERENCES news_ingestion_runs(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                source_url TEXT NOT NULL,
                publisher TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                snippet TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                retrieved_at TEXT NOT NULL,
                review_status TEXT NOT NULL CHECK (
                    review_status IN ('pending', 'relevant', 'not_relevant')
                ) DEFAULT 'pending',
                saved_as_evidence INTEGER NOT NULL CHECK (saved_as_evidence IN (0, 1)) DEFAULT 0,
                evidence_link_id TEXT,
                theme TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(case_id, source_url, keyword)
            );

            CREATE INDEX IF NOT EXISTS idx_news_results_case_id
                ON news_results(case_id);
            CREATE INDEX IF NOT EXISTS idx_news_results_run_id
                ON news_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_news_results_review_status
                ON news_results(review_status);
            CREATE INDEX IF NOT EXISTS idx_news_results_keyword
                ON news_results(keyword);

            CREATE TABLE IF NOT EXISTS evidence_links (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                news_result_id TEXT NOT NULL REFERENCES news_results(id) ON DELETE CASCADE,
                source_url TEXT NOT NULL,
                publisher TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                snippet TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                retrieved_at TEXT NOT NULL,
                query_keyword TEXT NOT NULL DEFAULT '',
                analyst_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_evidence_links_news_result_id
                ON evidence_links(news_result_id);
            CREATE INDEX IF NOT EXISTS idx_evidence_links_case_id
                ON evidence_links(case_id);

            CREATE TABLE IF NOT EXISTS fraud_monitor_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL CHECK (keyword = 'fraud'),
                enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)) DEFAULT 0,
                interval_minutes INTEGER NOT NULL DEFAULT 60,
                next_run_at TEXT NOT NULL,
                last_started_at TEXT NOT NULL DEFAULT '',
                last_completed_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fraud_monitor_jobs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL CHECK (keyword = 'fraud'),
                trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual', 'scheduled')),
                status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                provider_count INTEGER NOT NULL DEFAULT 0,
                result_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_fraud_monitor_jobs_created_at
                ON fraud_monitor_jobs(created_at);

            CREATE TABLE IF NOT EXISTS fraud_monitor_job_runs (
                job_id TEXT NOT NULL REFERENCES fraud_monitor_jobs(id) ON DELETE CASCADE,
                news_run_id TEXT NOT NULL REFERENCES news_ingestion_runs(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                PRIMARY KEY (job_id, news_run_id)
            );
            """
        )


def check_database() -> dict[str, str]:
    settings = get_settings()
    initialize_database()

    with sqlite3.connect(settings.database_path) as connection:
        checked_at = datetime.now(UTC).isoformat()
        connection.execute(
            """
            INSERT INTO app_health (id, checked_at)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET checked_at = excluded.checked_at
            """,
            (checked_at,),
        )
        value = connection.execute("SELECT checked_at FROM app_health WHERE id = 1").fetchone()

    return {
        "status": "ok",
        "database": str(settings.database_path),
        "checked_at": value[0] if value else checked_at,
    }
