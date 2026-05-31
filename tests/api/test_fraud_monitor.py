from pathlib import Path

from fastapi.testclient import TestClient

from app import fraud_monitor
from app.core.config import get_settings
from app.main import app
from app.news_monitoring import ProviderResult


def make_client(data_dir: Path, monkeypatch, providers: str = "gdelt,hn_algolia") -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS", providers)
    get_settings.cache_clear()
    return TestClient(app)


def fake_result(keyword: str, provider: str, index: int = 1) -> ProviderResult:
    return ProviderResult(
        keyword=keyword,
        source_url=f"https://{provider}.example/fraud-{index}",
        publisher=f"{provider} example",
        title=f"{provider} fraud alert",
        snippet="Public reporting describes fraud patterns requiring analyst review.",
        published_at="2026-05-30T12:00:00Z",
        retrieved_at="2026-05-30T12:05:00Z",
    )


def test_dashboard_bootstraps_single_fraud_monitor_case(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/fraud-monitor/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["keyword"] == "fraud"
    assert dashboard["case_id"] == fraud_monitor.FRAUD_MONITOR_CASE_ID
    assert dashboard["schedule"]["enabled"] is False
    assert dashboard["schedule"]["interval_minutes"] == 60
    assert [provider["name"] for provider in dashboard["providers"]] == ["gdelt", "hn_algolia"]


def test_manual_fraud_job_runs_configured_providers_and_stores_results(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        assert keyword == "fraud"
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard_response = client.get("/fraud-monitor/dashboard")

    assert run_response.status_code == 200
    job = run_response.json()
    assert job["status"] == "success"
    assert job["trigger_type"] == "manual"
    assert job["provider_runs"] == ["gdelt", "hn_algolia"]
    assert job["result_count"] == 2

    dashboard = dashboard_response.json()
    assert dashboard["total_results"] == 2
    assert dashboard["pending_results"] == 2
    assert {result["keyword"] for result in dashboard["results"]} == {"fraud"}


def test_fraud_job_records_partial_provider_failures(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        if provider == "gdelt":
            raise RuntimeError("provider timeout")
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        response = client.post("/fraud-monitor/jobs")

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "partial"
    assert job["result_count"] == 1
    assert "gdelt: provider timeout" in job["error_message"]


def test_schedule_update_and_due_job(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        schedule_response = client.patch(
            "/fraud-monitor/schedule",
            json={"enabled": True, "interval_minutes": 5},
        )
        assert schedule_response.status_code == 200
        assert schedule_response.json()["enabled"] is True

        with fraud_monitor.connect() as connection:
            fraud_monitor.ensure_monitor_settings(connection)
            connection.execute(
                "UPDATE fraud_monitor_settings SET next_run_at = ? WHERE id = 1",
                ("2000-01-01T00:00:00Z",),
            )

        fraud_monitor.run_due_fraud_monitor_jobs()
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert dashboard["latest_job"]["trigger_type"] == "scheduled"
    assert dashboard["latest_job"]["status"] == "success"
    assert dashboard["total_results"] == 2


def test_review_and_evidence_wrappers_update_fraud_results(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [fake_result(keyword, provider, 1)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()
        result_id = dashboard["results"][0]["id"]

        review_response = client.patch(
            f"/fraud-monitor/results/{result_id}",
            json={"review_status": "relevant"},
        )
        evidence_response = client.post(
            f"/fraud-monitor/results/{result_id}/evidence-links",
            json={"analyst_note": "Saved for fraud trend review."},
        )
        refreshed = client.get("/fraud-monitor/dashboard").json()

    assert review_response.status_code == 200
    assert review_response.json()["review_status"] == "relevant"
    assert evidence_response.status_code == 201
    assert refreshed["evidence_count"] == 1
    assert refreshed["relevant_results"] == 1
