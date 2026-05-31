from pathlib import Path

from fastapi.testclient import TestClient

from app import fraud_monitor
from app.core.config import get_settings
from app.main import app
from app.news_monitoring import ProviderResult


def make_client(
    data_dir: Path,
    monkeypatch,
    providers: str = "gdelt,hn_algolia",
    fixture_enabled: bool = False,
) -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS", providers)
    if fixture_enabled:
        monkeypatch.setenv("OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER", "1")
    else:
        monkeypatch.delenv("OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER", raising=False)
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
    assert dashboard["runtime"]["is_running"] is False
    assert dashboard["runtime"]["ready_provider_count"] == 2
    assert dashboard["runtime"]["last_error_message"] == ""


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
    assert {result["provider"] for result in dashboard["results"]} == {"gdelt", "hn_algolia"}


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
    assert "gdelt: Provider request timed out" in job["error_message"]


def test_manual_fraud_job_rejects_overlap(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        acquired = fraud_monitor._job_lock.acquire(blocking=False)
        assert acquired is True
        try:
            response = client.post("/fraud-monitor/jobs")
        finally:
            fraud_monitor._job_lock.release()

    assert response.status_code == 409
    assert response.json()["detail"] == "A fraud monitor job is already running."


def test_due_scheduled_job_skips_overlap_without_advancing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        schedule_response = client.patch(
            "/fraud-monitor/schedule",
            json={"enabled": True, "interval_minutes": 5},
        )
        assert schedule_response.status_code == 200
        due_at = "2000-01-01T00:00:00Z"
        with fraud_monitor.connect() as connection:
            fraud_monitor.ensure_monitor_settings(connection)
            connection.execute(
                "UPDATE fraud_monitor_settings SET next_run_at = ? WHERE id = 1",
                (due_at,),
            )

        acquired = fraud_monitor._job_lock.acquire(blocking=False)
        assert acquired is True
        try:
            fraud_monitor.run_due_fraud_monitor_jobs()
        finally:
            fraud_monitor._job_lock.release()

        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert dashboard["latest_job"] is None
    assert dashboard["schedule"]["next_run_at"] == due_at


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


def test_fixture_provider_is_gated_and_deterministic(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch, providers="fixture") as client:
        gated_dashboard = client.get("/fraud-monitor/dashboard").json()
        gated_run = client.post("/fraud-monitor/jobs")

    assert gated_dashboard["providers"][0]["status"] == "unsupported"
    assert gated_run.json()["status"] == "failed"
    assert gated_run.json()["provider_count"] == 0

    with make_client(
        tmp_path / "fixture-enabled",
        monkeypatch,
        providers="fixture",
        fixture_enabled=True,
    ) as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "success"
    assert run_response.json()["result_count"] == 2
    assert dashboard["providers"][0]["status"] == "ready"
    assert {result["provider"] for result in dashboard["results"]} == {"fixture"}


def test_review_operations_search_pagination_bulk_notes_and_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for index in range(12):
            source_index = 3 if index == 9 else index
            results.append(
                ProviderResult(
                    keyword=keyword,
                    source_url=f"https://{provider}.example/fraud-{source_index}",
                    publisher="Priority Source" if index % 2 == 0 else "Routine Source",
                    title=f"{'Priority' if index % 2 == 0 else 'Routine'} fraud report {index:02d}",
                    snippet="Public reporting describes fraud patterns requiring analyst review.",
                    published_at=f"2026-05-{30 - (index % 5):02d}T12:00:00Z",
                    retrieved_at=f"2026-05-30T12:{index:02d}:00Z",
                )
            )
        return results

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        run_response = client.post("/fraud-monitor/jobs")
        first_page_response = client.get("/fraud-monitor/dashboard?limit=5&sort=title_asc")
        second_page_response = client.get("/fraud-monitor/dashboard?limit=5&offset=5")
        search_response = client.get("/fraud-monitor/dashboard?search=priority&limit=100")
        all_response = client.get("/fraud-monitor/dashboard?limit=100")

        assert run_response.status_code == 200
        assert run_response.json()["result_count"] == 11

        first_page = first_page_response.json()
        second_page = second_page_response.json()
        search_page = search_response.json()
        all_page = all_response.json()
        assert first_page["result_page"]["total_matching"] == 11
        assert first_page["result_page"]["has_next"] is True
        assert first_page["result_page"]["limit"] == 5
        assert len(first_page["results"]) == 5
        assert second_page["result_page"]["has_previous"] is True
        assert len(second_page["results"]) == 5
        assert {result["publisher"] for result in search_page["results"]} == {"Priority Source"}
        assert any(result["duplicate_count"] == 1 and result["seen_count"] == 2 for result in all_page["results"])

        selected_ids = [result["id"] for result in first_page["results"][:2]]
        bulk_response = client.patch(
            "/fraud-monitor/review-batches",
            json={"result_ids": selected_ids, "review_status": "not_relevant"},
        )
        assert bulk_response.status_code == 200
        assert bulk_response.json()["updated_count"] == 2
        assert {result["review_status"] for result in bulk_response.json()["results"]} == {"not_relevant"}

        evidence_response = client.post(
            f"/fraud-monitor/results/{selected_ids[0]}/evidence-links",
            json={"analyst_note": "Initial review note."},
        )
        evidence = evidence_response.json()
        note_response = client.patch(
            f"/fraud-monitor/evidence-links/{evidence['id']}",
            json={"analyst_note": "Corrected review note."},
        )
        saved_response = client.get("/fraud-monitor/dashboard?evidence=saved&limit=10")

    assert evidence_response.status_code == 201
    assert note_response.status_code == 200
    assert note_response.json()["analyst_note"] == "Corrected review note."
    saved_results = saved_response.json()["results"]
    assert len(saved_results) == 1
    assert saved_results[0]["saved_as_evidence"] is True
    assert saved_results[0]["evidence_analyst_note"] == "Corrected review note."
