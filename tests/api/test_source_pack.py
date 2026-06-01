from pathlib import Path

from fastapi.testclient import TestClient

from app import news_monitoring
from app.core.config import get_settings
from app.main import app
from app.provider_registry import provider_metadata
from app.taxonomy import classify_fraud_taxonomy
from app.news_monitoring import ProviderResult


def make_client(data_dir: Path, monkeypatch, providers: str = "doj_news") -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS", providers)
    monkeypatch.delenv("OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER", raising=False)
    monkeypatch.delenv("OSINT_CASEOPS_FTC_CONSUMER_SENTINEL_PATH", raising=False)
    get_settings.cache_clear()
    return TestClient(app)


def test_provider_registry_exposes_source_pack_metadata() -> None:
    doj = provider_metadata("doj_news")
    assert doj is not None
    assert doj.display_name == "DOJ News API"
    assert doj.source_type == "official_enforcement"
    assert doj.source_confidence == "high"
    assert doj.requires_api_key is False
    assert "wire_fraud" in doj.fraud_categories

    gdelt = provider_metadata("gdelt")
    assert gdelt is not None
    assert gdelt.alias_for == "gdelt_doc"

    sec = provider_metadata("sec_litigation_releases")
    assert sec is not None
    assert sec.enabled is False
    assert sec.tier == "tier2_stub"


def test_taxonomy_classifier_covers_category_rail_segment_and_unknown() -> None:
    classified = classify_fraud_taxonomy(
        "Bank warns elder customers about Zelle account takeover fraud",
        "The advisory described phishing text messages and business email compromise.",
    )

    assert classified.fraud_category == "account_takeover"
    assert classified.payment_rail == "zelle"
    assert classified.victim_segment == "elder"
    assert classified.classification_confidence == "high"
    assert "account takeover" in classified.keywords_detected

    unknown = classify_fraud_taxonomy("General public report", "No matching terms.")
    assert unknown.fraud_category == "unknown"
    assert unknown.payment_rail == "unknown"
    assert unknown.victim_segment == "unknown"


def test_tier1_provider_adapters_normalize_to_provider_results(tmp_path: Path, monkeypatch) -> None:
    def fake_fetch_json(url: str, headers=None):
        if "gdeltproject.org" in url:
            return {
                "articles": [
                    {
                        "url": "https://official.example/fraud-warning",
                        "sourceCommonName": "Official Example",
                        "title": "Fraud warning from GDELT DOC",
                        "seendate": "20260530T120000Z",
                    }
                ]
            }
        if "justice.gov" in url:
            return {
                "results": [
                    {
                        "title": "Defendant charged with wire fraud",
                        "url": "https://www.justice.gov/opa/pr/example",
                        "date": "1782864000",
                        "body": "<p>Official summary only.</p>",
                    }
                ]
            }
        if "consumerfinance.gov" in url:
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "complaint_id": "123",
                                "product": "Money transfer",
                                "issue": "Fraud or scam",
                                "state": "CA",
                                "date_received": "2026-05-01",
                                "consumer_complaint_narrative": "must not be stored",
                            }
                        }
                    ]
                }
            }
        raise AssertionError(url)

    class FakeHtmlResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, limit: int) -> bytes:
            return (
                b"<html><body>FinCEN Alert about fraud, money mule activity, and suspicious activity reports 2026</body></html>"
            )

    monkeypatch.setattr(news_monitoring, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(news_monitoring, "urlopen", lambda request, timeout: FakeHtmlResponse())
    gdelt = news_monitoring.search_public_news_with_provider("fraud", "gdelt_doc", 5)
    doj = news_monitoring.search_public_news_with_provider("fraud", "doj_news", 5)
    cfpb = news_monitoring.search_public_news_with_provider("fraud", "cfpb_complaints", 5)
    fincen = news_monitoring.search_public_news_with_provider("fraud", "fincen_advisories", 5)

    assert gdelt[0].publisher == "Official Example"
    assert doj[0].publisher == "U.S. Department of Justice"
    assert doj[0].source_confidence == "high"
    assert "Official summary only" in doj[0].snippet
    assert cfpb[0].publisher == "Consumer Financial Protection Bureau"
    assert cfpb[0].state == "CA"
    assert "must not be stored" not in cfpb[0].snippet
    assert fincen[0].publisher == "Financial Crimes Enforcement Network"
    assert fincen[0].source_type == "official_advisory"

    csv_path = tmp_path / "sentinel.csv"
    csv_path.write_text("Category,State,Reports,Year\nImposter Fraud,NY,42,2024\n", encoding="utf-8")
    monkeypatch.setenv("OSINT_CASEOPS_FTC_CONSUMER_SENTINEL_PATH", str(csv_path))
    get_settings.cache_clear()
    ftc = news_monitoring.search_public_news_with_provider("fraud", "ftc_consumer_sentinel_import", 5)
    assert ftc[0].publisher == "Federal Trade Commission"
    assert ftc[0].state == "NY"
    assert ftc[0].source_url.startswith("https://www.ftc.gov/")


def test_trend_endpoints_use_normalized_source_pack_fields(tmp_path: Path, monkeypatch) -> None:
    def fake_search(keyword: str, provider: str) -> list[ProviderResult]:
        return [
            ProviderResult(
                keyword=keyword,
                source_url="https://www.justice.gov/opa/pr/wire-fraud-zelle",
                publisher="U.S. Department of Justice",
                title="California elder Zelle account takeover wire fraud case",
                snippet="Official source describes elder victims and Zelle transfers.",
                published_at="2026-05-30T12:00:00Z",
                retrieved_at="2026-05-30T12:05:00Z",
                source_type="official_enforcement",
                source_confidence="high",
            )
        ]

    monkeypatch.setattr("app.fraud_monitor.search_public_news_with_provider", fake_search)
    with make_client(tmp_path, monkeypatch, providers="doj_news") as client:
        run_response = client.post("/fraud-monitor/jobs")
        summary_response = client.get("/api/trends/summary?confidence=high")
        category_response = client.get("/api/trends/categories?fraud_category=account_takeover")
        state_response = client.get("/api/trends/states?state=CA")
        rail_response = client.get("/api/trends/payment-rails")
        watchlist_response = client.get("/api/trends/watchlist")
        dashboard_response = client.get("/fraud-monitor/dashboard")

    assert run_response.status_code == 200
    summary = summary_response.json()
    assert summary["official_source_alerts"][0]["source_confidence"] == "high"
    assert summary["provider_health"]
    assert category_response.json()[0]["label"] == "account_takeover"
    assert state_response.json()[0]["label"] == "CA"
    assert rail_response.json()[0]["label"] == "zelle"
    assert any(item["label"] == "account takeover" for item in watchlist_response.json())
    dashboard = dashboard_response.json()
    assert dashboard["trend_overview"]["top_categories_this_week"]
    assert dashboard["results"][0]["fraud_category"] == "account_takeover"
    assert dashboard["results"][0]["payment_rail"] == "zelle"
