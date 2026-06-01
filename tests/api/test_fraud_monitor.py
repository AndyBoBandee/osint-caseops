from pathlib import Path
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app import fraud_monitor, news_monitoring
from app.core.config import get_settings
from app.main import app
from app.news_monitoring import ProviderResult


def make_client(
    data_dir: Path,
    monkeypatch,
    providers: str = "gdelt,google_news_rss,hn_algolia",
    fixture_enabled: bool = False,
    brave_key: str | None = "test-brave-key",
) -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS", providers)
    if brave_key is None:
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    else:
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", brave_key)
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
    assert [provider["name"] for provider in dashboard["providers"]] == [
        "gdelt",
        "google_news_rss",
        "hn_algolia",
    ]
    assert dashboard["detailed_provider"]["name"] == "brave"
    assert dashboard["detailed_provider"]["status"] == "ready"
    assert dashboard["runtime"]["is_running"] is False
    assert dashboard["runtime"]["ready_provider_count"] == 3
    assert dashboard["runtime"]["last_error_message"] == ""
    assert dashboard["providers"][0]["request_limit"] == "Up to 10 result(s) per keyword per run."
    assert dashboard["providers"][0]["timeout_seconds"] == 8
    assert dashboard["providers"][0]["last_run_status"] == ""
    assert dashboard["configuration_validation"]["is_valid"] is True
    assert dashboard["configuration_validation"]["ready_provider_count"] == 3
    assert dashboard["configuration_validation"]["issues"] == []


def test_manual_fraud_job_runs_configured_providers_and_stores_results(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        assert keyword == "fraud"
        assert provider != "brave"
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard_response = client.get("/fraud-monitor/dashboard")

    assert run_response.status_code == 200
    job = run_response.json()
    assert job["status"] == "success"
    assert job["trigger_type"] == "manual"
    assert job["provider_runs"] == ["gdelt", "google_news_rss", "hn_algolia"]
    assert job["result_count"] == 3

    dashboard = dashboard_response.json()
    assert dashboard["total_results"] == 3
    assert dashboard["pending_results"] == 3
    assert {result["keyword"] for result in dashboard["results"]} == {"fraud"}
    assert {result["provider"] for result in dashboard["results"]} == {
        "gdelt",
        "google_news_rss",
        "hn_algolia",
    }
    summaries = dashboard["latest_job"]["provider_run_summaries"]
    assert {summary["provider"] for summary in summaries} == {"gdelt", "google_news_rss", "hn_algolia"}
    assert all(summary["raw_result_count"] == 1 for summary in summaries)
    assert all(summary["stored_result_count"] == 1 for summary in summaries)
    assert all(summary["filtered_result_count"] == 0 for summary in summaries)


def test_detailed_fraud_job_uses_brave_only_when_requested(
    tmp_path: Path,
    monkeypatch,
) -> None:
    requested_providers: list[str] = []

    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        requested_providers.append(provider)
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        standard_response = client.post("/fraud-monitor/jobs")
        detailed_response = client.post(
            "/fraud-monitor/jobs",
            json={"search_mode": "detailed"},
        )

    assert standard_response.status_code == 200
    assert detailed_response.status_code == 200
    assert standard_response.json()["provider_runs"] == ["gdelt", "google_news_rss", "hn_algolia"]
    assert detailed_response.json()["provider_runs"] == ["brave"]
    assert requested_providers == ["gdelt", "google_news_rss", "hn_algolia", "brave"]


def test_detailed_fraud_job_requires_brave_key_without_running_free_providers(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_search(keyword: str, provider: str) -> list[ProviderResult]:
        raise AssertionError("Detailed search should not call providers without a Brave key.")

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fail_search)

    with make_client(tmp_path, monkeypatch, brave_key=None) as client:
        response = client.post("/fraud-monitor/jobs", json={"search_mode": "detailed"})

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "failed"
    assert job["provider_count"] == 0
    assert job["provider_runs"] == []
    assert "BRAVE_SEARCH_API_KEY" in job["error_message"]


def test_brave_provider_uses_clean_query_and_keyed_readiness(tmp_path: Path, monkeypatch) -> None:
    assert (
        news_monitoring.build_provider_query("fraud", "brave")
        == "fraud (report OR warning OR investigation OR charged OR lawsuit OR enforcement)"
    )
    assert news_monitoring.build_provider_query("fraud", "hn_algolia") == "fraud"

    with make_client(tmp_path, monkeypatch, providers="brave", brave_key=None) as client:
        missing_dashboard = client.get("/fraud-monitor/dashboard").json()

    with make_client(tmp_path / "ready", monkeypatch, providers="brave", brave_key="local-test-key") as client:
        ready_dashboard = client.get("/fraud-monitor/dashboard").json()

    assert missing_dashboard["providers"][0]["status"] == "missing_config"
    assert ready_dashboard["providers"][0]["status"] == "ready"


def test_static_non_news_results_are_filtered_before_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://news.example/articles/fraud-warning",
                publisher="Example News",
                title="Agency fraud warning",
                snippet="Public reporting describes fraud enforcement activity.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:05:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://cdn.example/assets/app.js",
                publisher="Example CDN",
                title="",
                snippet="",
                published_at="",
                retrieved_at="2026-05-30T12:05:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://static.example.com/newsletter",
                publisher="Static Example",
                title="",
                snippet="",
                published_at="",
                retrieved_at="2026-05-30T12:05:00Z",
            ),
        ]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="brave") as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "success"
    assert run_response.json()["result_count"] == 1
    assert run_response.json()["error_message"] == ""
    assert dashboard["total_results"] == 1
    assert dashboard["results"][0]["source_url"] == "https://news.example/articles/fraud-warning"
    summary = dashboard["latest_job"]["provider_run_summaries"][0]
    assert summary["provider"] == "brave"
    assert summary["raw_result_count"] == 3
    assert summary["stored_result_count"] == 1
    assert summary["filtered_result_count"] == 2
    assert summary["note"] == "Filtered 2 static/non-news result(s)."
    assert dashboard["runtime"]["last_error_message"] == ""


def test_all_static_results_are_filtered_without_failing_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://cdn.example/assets/fraud.css",
                publisher="Example CDN",
                title="",
                snippet="",
                published_at="",
                retrieved_at="2026-05-30T12:05:00Z",
            )
        ]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="brave") as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "success"
    assert run_response.json()["result_count"] == 0
    assert run_response.json()["error_message"] == ""
    assert dashboard["total_results"] == 0
    assert dashboard["providers"][0]["status"] == "ready"
    assert dashboard["latest_job"]["provider_run_summaries"][0]["filtered_result_count"] == 1


def test_docker_compose_passes_brave_key_and_defaults_to_free_providers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose_text = (repo_root / "infra/docker/docker-compose.yml").read_text()

    assert (
        "OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS: "
        "${OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS:-gdelt,google_news_rss,hn_algolia}"
    ) in compose_text
    assert "BRAVE_SEARCH_API_KEY: ${BRAVE_SEARCH_API_KEY:-}" in compose_text


def test_fraud_results_store_source_derived_state_metadata_and_search(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/california-fraud-report",
                publisher="Public Source",
                title="California lending fraud report",
                snippet="Public reporting describes a fraud pattern.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:05:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/new-york-warning",
                publisher="Public Source",
                title="Agency fraud warning",
                snippet="Public reporting describes a New York fraud pattern.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:06:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/provider-warning",
                publisher="Texas Tribune",
                title="Public fraud warning",
                snippet="Public reporting describes analyst review needs.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:07:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/washington-dc/fraud-warning",
                publisher="Public Source",
                title="Public fraud warning",
                snippet="Public reporting describes analyst review needs.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:08:00Z",
            ),
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/fraud-warning",
                publisher="Public Source",
                title="Public fraud warning",
                snippet="Public reporting describes analyst review needs.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:09:00Z",
            ),
        ]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        run_response = client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard?limit=100").json()
        california_search = client.get("/fraud-monitor/dashboard?search=california&limit=100").json()

    assert run_response.status_code == 200
    results_by_url = {result["source_url"]: result for result in dashboard["results"]}
    california = results_by_url["https://gdelt.example/california-fraud-report"]
    assert california["fraud_state_code"] == "CA"
    assert california["fraud_state_label"] == "California"
    assert california["fraud_state_basis"] == "title"
    assert california["fraud_state_terms"] == ["California"]

    new_york = results_by_url["https://gdelt.example/new-york-warning"]
    assert new_york["fraud_state_code"] == "NY"
    assert new_york["fraud_state_label"] == "New York"
    assert new_york["fraud_state_basis"] == "snippet"

    texas = results_by_url["https://gdelt.example/provider-warning"]
    assert texas["fraud_state_code"] == "TX"
    assert texas["fraud_state_basis"] == "publisher"

    district = results_by_url["https://gdelt.example/washington-dc/fraud-warning"]
    assert district["fraud_state_code"] == "DC"
    assert district["fraud_state_label"] == "District of Columbia"
    assert district["fraud_state_basis"] == "source_url"

    unknown = results_by_url["https://gdelt.example/fraud-warning"]
    assert unknown["fraud_state_code"] == ""
    assert unknown["fraud_state_label"] == "Unknown"
    assert unknown["fraud_state_basis"] == "unknown"
    assert unknown["fraud_state_terms"] == []

    assert california_search["result_page"]["total_matching"] == 1
    assert california_search["results"][0]["fraud_state_label"] == "California"


def test_duplicate_fraud_result_refreshes_state_metadata_without_resetting_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = {"count": 0}

    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        calls["count"] += 1
        state = "California" if calls["count"] == 1 else "Florida"
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/repeated-fraud-report",
                publisher="Public Source",
                title=f"{state} lending fraud report",
                snippet="Public reporting describes a fraud pattern.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at=f"2026-05-30T12:0{calls['count']}:00Z",
            )
        ]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        first_run = client.post("/fraud-monitor/jobs")
        first_result = client.get("/fraud-monitor/dashboard").json()["results"][0]
        result_id = first_result["id"]
        client.patch(
            f"/fraud-monitor/results/{result_id}",
            json={"review_status": "relevant"},
        )
        client.post(
            f"/fraud-monitor/results/{result_id}/evidence-links",
            json={"analyst_note": "Preserve this reviewed source."},
        )
        second_run = client.post("/fraud-monitor/jobs")
        updated_result = client.get("/fraud-monitor/dashboard").json()["results"][0]

    assert first_run.status_code == 200
    assert second_run.status_code == 200
    assert updated_result["id"] == result_id
    assert updated_result["review_status"] == "relevant"
    assert updated_result["saved_as_evidence"] is True
    assert updated_result["evidence_analyst_note"] == "Preserve this reviewed source."
    assert updated_result["seen_count"] == 2
    assert updated_result["fraud_state_code"] == "FL"
    assert updated_result["fraud_state_label"] == "Florida"


def test_fraud_job_records_partial_provider_failures(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        if provider == "gdelt":
            raise RuntimeError("provider timeout")
        return [fake_result(keyword, provider)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt,hn_algolia") as client:
        response = client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "partial"
    assert job["result_count"] == 1
    assert "gdelt: Provider request timed out" in job["error_message"]
    gdelt = next(provider for provider in dashboard["providers"] if provider["name"] == "gdelt")
    assert gdelt["status"] == "timeout"
    assert gdelt["last_run_status"] == "failed"
    assert "timed out" in gdelt["last_error_message"]


def test_provider_health_distinguishes_missing_config_unsupported_and_partial_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(
        tmp_path,
        monkeypatch,
        providers="brave,unknown,hn_algolia",
        brave_key=None,
    ) as client:
        client.get("/fraud-monitor/dashboard")
        with fraud_monitor.connect() as connection:
            settings = fraud_monitor.ensure_monitor_settings(connection)
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
                VALUES (?, ?, NULL, 'hn_algolia', 'partial', ?, ?, ?, 1, ?, ?)
                """,
                (
                    str(uuid4()),
                    settings["case_id"],
                    "2030-01-01T00:00:00Z",
                    "2030-01-01T00:00:03Z",
                    '["fraud"]',
                    "fraud: provider returned a partial response",
                    "2030-01-01T00:00:03Z",
                ),
            )
        dashboard = client.get("/fraud-monitor/dashboard").json()

    statuses = {provider["name"]: provider["status"] for provider in dashboard["providers"]}
    assert statuses == {
        "brave": "missing_config",
        "unknown": "unsupported",
        "hn_algolia": "partial_success",
    }


def test_configuration_validation_flags_provider_errors_and_fixture_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(
        tmp_path,
        monkeypatch,
        providers="brave,unknown,fixture",
        brave_key=None,
    ) as client:
        invalid_response = client.get("/fraud-monitor/configuration/validation")

    assert invalid_response.status_code == 200
    invalid = invalid_response.json()
    assert invalid["is_valid"] is False
    assert invalid["fixture_mode"] is False
    assert invalid["ready_provider_count"] == 0
    assert {issue["provider"] for issue in invalid["issues"] if issue["severity"] == "error"} == {
        "all",
        "brave",
        "fixture",
        "unknown",
    }

    with make_client(
        tmp_path / "fixture-validation",
        monkeypatch,
        providers="fixture",
        fixture_enabled=True,
    ) as client:
        fixture_response = client.get("/fraud-monitor/configuration/validation")
        dashboard = client.get("/fraud-monitor/dashboard").json()

    assert fixture_response.status_code == 200
    fixture = fixture_response.json()
    assert fixture["is_valid"] is True
    assert fixture["fixture_mode"] is True
    assert fixture["ready_provider_count"] == 1
    assert fixture["issues"][0]["severity"] == "warning"
    assert "test-only" in fixture["issues"][0]["message"]
    assert dashboard["configuration_validation"]["fixture_mode"] is True


def test_scheduled_provider_timeout_uses_bounded_backoff(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        client.patch("/fraud-monitor/schedule", json={"enabled": True, "interval_minutes": 5})
        with fraud_monitor.connect() as connection:
            fraud_monitor.ensure_monitor_settings(connection)
            connection.execute(
                "UPDATE fraud_monitor_settings SET next_run_at = ? WHERE id = 1",
                ("2000-01-01T00:00:00Z",),
            )
        before = datetime.now(UTC)
        fraud_monitor.run_due_fraud_monitor_jobs()
        dashboard = client.get("/fraud-monitor/dashboard").json()

    next_run_at = fraud_monitor.parse_utc(dashboard["schedule"]["next_run_at"])
    assert dashboard["latest_job"]["trigger_type"] == "scheduled"
    assert dashboard["latest_job"]["status"] == "failed"
    assert timedelta(minutes=9) <= next_run_at - before <= timedelta(minutes=11)
    assert dashboard["providers"][0]["next_retry_at"] == dashboard["schedule"]["next_run_at"]


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
    assert dashboard["total_results"] == 3


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
    assert {artifact["artifact_type"] for artifact in evidence_response.json()["artifacts"]} == {
        "source_url",
        "text_snapshot",
    }
    assert refreshed["evidence_count"] == 1
    assert refreshed["relevant_results"] == 1
    assert refreshed["results"][0]["available_artifact_count"] == 2
    assert refreshed["results"][0]["vault_state"] == "artifacts_available"


def test_saving_evidence_preserves_local_vault_artifacts_under_data_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [fake_result(keyword, provider, 1)]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    screenshot = "data:image/png;base64,iVBORw0KGgo="
    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        client.post("/fraud-monitor/jobs")
        result_id = client.get("/fraud-monitor/dashboard").json()["results"][0]["id"]
        evidence_response = client.post(
            f"/fraud-monitor/results/{result_id}/evidence-links",
            json={
                "analyst_note": "Vault capture with local artifacts.",
                "html_snapshot": "<html><body>public source</body></html>",
                "text_snapshot": "Public source text snapshot.",
                "screenshot_data_url": screenshot,
            },
        )
        dashboard = client.get("/fraud-monitor/dashboard").json()
        export_response = client.get("/fraud-monitor/exports/json")

    assert evidence_response.status_code == 201
    artifacts = evidence_response.json()["artifacts"]
    artifact_types = {artifact["artifact_type"] for artifact in artifacts}
    assert artifact_types == {"source_url", "text_snapshot", "html_snapshot", "screenshot"}
    available = [artifact for artifact in artifacts if artifact["availability"] == "available"]
    assert len(available) == 4
    for artifact in available:
        if artifact["storage_path"]:
            artifact_path = tmp_path / artifact["storage_path"]
            assert artifact_path.exists()
            assert tmp_path in artifact_path.parents
            assert artifact["byte_size"] == artifact_path.stat().st_size
        assert artifact["content_hash"]
        assert artifact["captured_at"]

    result = dashboard["results"][0]
    assert result["available_artifact_count"] == 4
    assert result["vault_state"] == "artifacts_available"
    bundle = export_response.json()
    assert bundle["metadata"]["available_artifact_count"] == 4
    assert len(bundle["evidence_table"][0]["vault_artifacts"]) == 4


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


def test_exports_handle_empty_reviewed_state(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch, providers="fixture", fixture_enabled=True) as client:
        json_response = client.get("/fraud-monitor/exports/json")
        markdown_response = client.get("/fraud-monitor/exports/markdown")

    assert json_response.status_code == 200
    bundle = json_response.json()
    assert bundle["metadata"]["local_only"] is True
    assert bundle["metadata"]["reviewed_result_count"] == 0
    assert bundle["evidence_table"] == []
    assert bundle["reviewed_results"] == []
    assert "unsupported allegations" in bundle["metadata"]["responsible_use"]
    assert markdown_response.status_code == 200
    assert "No reviewed fraud monitor results are available yet." in markdown_response.text


def test_exports_include_reviewed_results_metadata_trends_and_escaped_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://gdelt.example/fraud-report",
                publisher="GDELT | Example",
                title="California agency | charged lending fraud\nwarning",
                snippet="Public reporting describes a fraud pattern for analyst review.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:05:00Z",
            )
        ]

    monkeypatch.setattr(fraud_monitor, "search_public_news_with_provider", fake_search)

    with make_client(tmp_path, monkeypatch, providers="gdelt") as client:
        client.post("/fraud-monitor/jobs")
        dashboard = client.get("/fraud-monitor/dashboard").json()
        result_id = dashboard["results"][0]["id"]
        client.patch(
            f"/fraud-monitor/results/{result_id}",
            json={"review_status": "relevant"},
        )
        client.post(
            f"/fraud-monitor/results/{result_id}/evidence-links",
            json={"analyst_note": "Analyst | note\nwith newline."},
        )

        json_response = client.get("/fraud-monitor/exports/json")
        markdown_response = client.get("/fraud-monitor/exports/markdown")

    assert json_response.status_code == 200
    bundle = json_response.json()
    assert bundle["metadata"]["scope"] == "Fixed-keyword passive public-source fraud monitoring."
    assert bundle["metadata"]["reviewed_result_count"] == 1
    assert bundle["metadata"]["provider_configuration"][0]["name"] == "gdelt"
    assert bundle["evidence_table"][0]["source_url"] == "https://gdelt.example/fraud-report"
    assert bundle["evidence_table"][0]["provider"] == "gdelt"
    assert bundle["evidence_table"][0]["review_status"] == "relevant"
    assert bundle["evidence_table"][0]["classification_label"] == "lending fraud"
    assert bundle["evidence_table"][0]["fraud_state_label"] == "California"
    assert bundle["evidence_table"][0]["fraud_state_code"] == "CA"
    assert bundle["evidence_table"][0]["analyst_note"] == "Analyst | note\nwith newline."
    assert bundle["reviewed_results"][0]["title"] == "California agency | charged lending fraud\nwarning"
    assert bundle["reviewed_results"][0]["classification_label"] == "lending fraud"
    assert bundle["reviewed_results"][0]["fraud_state_label"] == "California"
    assert any("analyst review required" in group["confidence_language"] for group in bundle["trend_summary"]["groups"])

    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-disposition"] == 'attachment; filename="fraud-monitor-export.md"'
    assert "California agency \\| charged lending fraud warning" in markdown_response.text
    assert "lending fraud" in markdown_response.text
    assert "California" in markdown_response.text
    assert "Analyst \\| note with newline." in markdown_response.text
    assert "Public results are leads for analyst review" in markdown_response.text


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
                    title=f"{'Priority' if index % 2 == 0 else 'Routine'} lending fraud report {index:02d}",
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
        classification_search_response = client.get("/fraud-monitor/dashboard?search=lending&limit=100")
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
        assert classification_search_response.json()["result_page"]["total_matching"] == 11
        assert {result["classification_label"] for result in classification_search_response.json()["results"]} == {
            "lending fraud"
        }
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
