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
