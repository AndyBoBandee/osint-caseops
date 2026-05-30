from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "osint-caseops-api",
    }


def test_database_health_returns_ok() -> None:
    response = client.get("/health/db")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["database"].endswith("osint_caseops.sqlite3")
    assert payload["checked_at"]
