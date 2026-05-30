import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def make_client(data_dir: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    return TestClient(app)


def test_health_returns_ok(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "osint-caseops-api",
    }


def test_database_health_reads_and_writes_sqlite(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "osint_caseops.sqlite3"

    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/health/db")

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["database"] == str(database_path)
    assert payload["checked_at"]

    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT checked_at FROM app_health WHERE id = 1").fetchone()

    assert row == (payload["checked_at"],)
