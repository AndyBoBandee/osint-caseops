from pathlib import Path

from fastapi.testclient import TestClient

from app import enrichment
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
            "title": "Passive enrichment review",
            "objective": "Run passive enrichment for a scoped public target.",
            "scope_category": "Vendor review",
            "scope_notes": "Passive public-source review only.",
            "case_type": "Domain review",
            "scope_acknowledged": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_entity(client: TestClient, case_id: str, entity_type: str, value: str) -> dict:
    response = client.post(
        f"/cases/{case_id}/entities",
        json={"type": entity_type, "value": value},
    )
    assert response.status_code == 201
    return response.json()


def test_passive_enrichment_run_stores_module_results_and_errors(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def dns_runner(target: enrichment.EnrichmentTarget, context: dict) -> dict:
        return {"domain": target.domain, "addresses": ["93.184.216.34"]}

    def rdap_runner(target: enrichment.EnrichmentTarget, context: dict) -> dict:
        raise RuntimeError(f"RDAP lookup failed for {target.domain}.")

    monkeypatch.setattr(
        enrichment,
        "ENRICHMENT_MODULES",
        [
            ("dns_lookup", dns_runner),
            ("rdap_lookup", rdap_runner),
        ],
    )

    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        entity = create_entity(client, case["id"], "domain", "Example.COM.")

        run_response = client.post(f"/entities/{entity['id']}/enrichment-runs")
        assert run_response.status_code == 201
        run = run_response.json()
        assert run["case_id"] == case["id"]
        assert run["entity_id"] == entity["id"]
        assert run["module_name"] == "passive_enrichment"
        assert run["status"] == "partial"
        assert run["error_message"] == "1 enrichment module failed."
        assert [result["module_name"] for result in run["results"]] == [
            "dns_lookup",
            "rdap_lookup",
        ]
        assert run["results"][0]["status"] == "success"
        assert run["results"][0]["result"]["addresses"] == ["93.184.216.34"]
        assert run["results"][1]["status"] == "failed"
        assert "RDAP lookup failed for example.com." in run["results"][1]["error_message"]

        entity_response = client.get(f"/entities/{entity['id']}")
        assert entity_response.status_code == 200

    with make_client(tmp_path, monkeypatch) as restarted_client:
        runs_response = restarted_client.get(f"/entities/{entity['id']}/enrichment-runs")
        assert runs_response.status_code == 200
        persisted_runs = runs_response.json()
        assert len(persisted_runs) == 1
        assert persisted_runs[0]["id"] == run["id"]
        assert persisted_runs[0]["results"][1]["status"] == "failed"


def test_url_enrichment_derives_domain_and_url_target(tmp_path: Path, monkeypatch) -> None:
    def target_runner(target: enrichment.EnrichmentTarget, context: dict) -> dict:
        return {
            "domain": target.domain,
            "url": target.url,
            "hostname": target.hostname,
            "scheme": target.scheme,
            "port": target.port,
        }

    monkeypatch.setattr(enrichment, "ENRICHMENT_MODULES", [("http_status", target_runner)])

    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        entity = create_entity(
            client,
            case["id"],
            "url",
            "HTTPS://Example.com:8443/login?next=home#ignored",
        )

        run_response = client.post(f"/entities/{entity['id']}/enrichment-runs")
        assert run_response.status_code == 201
        result = run_response.json()["results"][0]["result"]

    assert result == {
        "domain": "example.com",
        "url": "https://example.com:8443/login?next=home",
        "hostname": "example.com",
        "scheme": "https",
        "port": 8443,
    }


def test_failed_http_metadata_is_cached_within_run(monkeypatch) -> None:
    calls = 0
    target = enrichment.EnrichmentTarget(
        entity_type="domain",
        entity_value="example.com",
        domain="example.com",
        url="https://example.com/",
        hostname="example.com",
        scheme="https",
    )
    context: dict = {}

    def fail_fetch(_: enrichment.EnrichmentTarget) -> dict:
        nonlocal calls
        calls += 1
        raise RuntimeError("HTTP request failed: timeout")

    monkeypatch.setattr(enrichment, "fetch_http_metadata", fail_fetch)

    first = enrichment.run_module("http_status", enrichment.summarize_http_status, target, context)
    second = enrichment.run_module(
        "redirect_chain",
        enrichment.summarize_redirect_chain,
        target,
        context,
    )

    assert calls == 1
    assert first["status"] == "failed"
    assert second["status"] == "failed"
    assert first["error_message"] == "HTTP request failed: timeout"
    assert second["error_message"] == "HTTP request failed: timeout"


def test_passive_enrichment_rejects_unsupported_entity_types(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        entity = create_entity(client, case["id"], "email", "analyst@example.com")

        response = client.post(f"/entities/{entity['id']}/enrichment-runs")

    assert response.status_code == 422
    assert response.json()["detail"] == "Passive enrichment is available for domain and URL entities."
