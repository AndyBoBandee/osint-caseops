from pathlib import Path

from fastapi.testclient import TestClient

from app import news_monitoring
from app.core.config import get_settings
from app.main import app


def make_client(data_dir: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    return TestClient(app)


def create_case(client: TestClient) -> dict:
    response = client.post(
        "/cases",
        json={
            "title": "Public scam trend review",
            "objective": "Monitor public reporting for scoped scam and impersonation terms.",
            "scope_category": "Scam review",
            "scope_notes": "Public news and search results only.",
            "case_type": "Public news monitoring",
            "scope_acknowledged": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_classification_prefers_title_before_snippet() -> None:
    label, basis, terms = news_monitoring.classify_public_result(
        "XYZ was charged for lending fraud",
        "The public report also mentioned phishing warnings.",
    )

    assert label == "lending fraud"
    assert basis == "title"
    assert terms == ["lending fraud"]


def test_keyword_sets_require_public_interest_terms(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)

        rejected = client.post(
            f"/cases/{case['id']}/news-keyword-sets",
            json={
                "name": "Private curiosity",
                "keywords": ["random local person"],
                "scope_notes": "Not a valid public-interest scan.",
            },
        )
        assert rejected.status_code == 422

        created = client.post(
            f"/cases/{case['id']}/news-keyword-sets",
            json={
                "name": "Scam reporting",
                "keywords": ["Scam alerts", "fraud warning", "Scam alerts"],
                "scope_notes": "Lawful public-source monitoring only.",
            },
        )
        assert created.status_code == 201
        keyword_set = created.json()
        assert keyword_set["keywords"] == ["scam alerts", "fraud warning"]

        updated = client.patch(
            f"/news-keyword-sets/{keyword_set['id']}",
            json={"keywords": ["impersonation scam"]},
        )
        assert updated.status_code == 200
        assert updated.json()["keywords"] == ["impersonation scam"]


def test_news_scan_stores_results_queue_evidence_trends_and_persists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_search(keyword: str) -> list[news_monitoring.ProviderResult]:
        return [
            news_monitoring.ProviderResult(
                keyword=keyword,
                source_url=f"https://news.example/{keyword.replace(' ', '-')}-1",
                publisher="Example News",
                title=f"Consumer warning about lending fraud tied to {keyword}",
                snippet="Police reported a repeated fraud theme in public alerts.",
                published_at="2026-05-29T10:00:00Z",
                retrieved_at="2026-05-30T12:00:00Z",
            ),
            news_monitoring.ProviderResult(
                keyword=keyword,
                source_url=f"https://daily.example/{keyword.replace(' ', '-')}-2",
                publisher="Daily Example",
                title=f"Public agencies track {keyword}",
                snippet="Officials described reports without identifying private individuals.",
                published_at="2026-05-28T08:00:00Z",
                retrieved_at="2026-05-30T12:01:00Z",
            ),
        ]

    monkeypatch.setattr(news_monitoring, "search_public_news", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        keyword_set_response = client.post(
            f"/cases/{case['id']}/news-keyword-sets",
            json={
                "name": "Fraud themes",
                "keywords": ["fraud warning", "impersonation scam"],
                "scope_notes": "Use confidence-aware public reporting language.",
            },
        )
        assert keyword_set_response.status_code == 201
        keyword_set = keyword_set_response.json()

        run_response = client.post(
            f"/cases/{case['id']}/news-ingestion-runs",
            json={"keyword_set_id": keyword_set["id"]},
        )
        assert run_response.status_code == 201
        run = run_response.json()
        assert run["status"] == "success"
        assert run["query_keywords"] == ["fraud warning", "impersonation scam"]
        assert run["result_count"] == 4
        assert len(run["results"]) == 4
        assert run["results"][0]["review_status"] == "pending"
        assert run["results"][0]["saved_as_evidence"] is False
        assert run["results"][0]["source_quality"] == "named_source"
        assert run["results"][0]["recency_cue"] in {"fresh", "recent"}
        classified_result = next(
            result for result in run["results"] if result["classification_label"] == "lending fraud"
        )
        assert classified_result["classification_basis"] == "title"
        assert classified_result["classification_terms"] == ["lending fraud"]
        assert "named source" in run["results"][0]["prioritization_cue"]

        results_response = client.get(f"/cases/{case['id']}/news-results")
        assert results_response.status_code == 200
        results = results_response.json()
        assert {result["keyword"] for result in results} == {
            "fraud warning",
            "impersonation scam",
        }

        review_response = client.patch(
            f"/news-results/{results[0]['id']}",
            json={"review_status": "relevant"},
        )
        assert review_response.status_code == 200
        assert review_response.json()["review_status"] == "relevant"

        evidence_response = client.post(
            f"/news-results/{results[0]['id']}/evidence-links",
            json={"analyst_note": "Saved for source attribution review."},
        )
        assert evidence_response.status_code == 201
        evidence = evidence_response.json()
        assert evidence["source_url"] == results[0]["source_url"]
        assert evidence["query_keyword"] == results[0]["keyword"]

        trends_response = client.get(f"/cases/{case['id']}/news-trends")
        assert trends_response.status_code == 200
        trends = trends_response.json()
        group_types = {group["group_type"] for group in trends["groups"]}
        assert {"keyword", "classification", "source", "time_window", "theme"}.issubset(group_types)
        assert any(group["label"] == "lending fraud" for group in trends["groups"])
        assert all("analyst review required" in group["confidence_language"] for group in trends["groups"])
        assert all(group["priority_cue"] for group in trends["groups"])

    with make_client(tmp_path, monkeypatch) as restarted_client:
        persisted_results = restarted_client.get(f"/cases/{case['id']}/news-results").json()
        persisted_evidence = restarted_client.get(f"/cases/{case['id']}/evidence-links").json()

    assert len(persisted_results) == 4
    assert len(persisted_evidence) == 1
    assert persisted_evidence[0]["id"] == evidence["id"]
    assert any(result["classification_label"] == "lending fraud" for result in persisted_results)


def test_news_scan_records_partial_provider_failures(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str) -> list[news_monitoring.ProviderResult]:
        if "fraud" in keyword:
            raise RuntimeError("provider timeout")
        return [
            news_monitoring.ProviderResult(
                keyword=keyword,
                source_url="https://news.example/impersonation-scam",
                publisher="Example News",
                title="Impersonation scam warning",
                snippet="Public reporting describes a possible repeated theme.",
                published_at="2026-05-30T09:00:00Z",
                retrieved_at="2026-05-30T12:02:00Z",
            )
        ]

    monkeypatch.setattr(news_monitoring, "search_public_news", fake_search)

    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        run_response = client.post(
            f"/cases/{case['id']}/news-ingestion-runs",
            json={"keywords": ["fraud warning", "impersonation scam"]},
        )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "partial"
    assert run["result_count"] == 1
    assert "fraud warning: provider timeout" in run["error_message"]
