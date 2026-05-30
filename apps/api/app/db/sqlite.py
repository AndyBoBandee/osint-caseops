from datetime import UTC, datetime
import sqlite3

from app.core.config import get_settings


def check_database() -> dict[str, str]:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_health (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                checked_at TEXT NOT NULL
            )
            """
        )
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
