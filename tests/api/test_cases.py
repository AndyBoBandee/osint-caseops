from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def make_client(data_dir: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("OSINT_CASEOPS_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    return TestClient(app)


def case_payload(**overrides):
    payload = {
        "title": "Vendor domain review",
        "objective": "Review public web presence for the vendor domain.",
        "scope_category": "Vendor review",
        "scope_notes": "Passive public-source review only.",
        "case_type": "Vendor risk snapshot",
        "scope_acknowledged": True,
        "tags": ["Vendor", "domain", "vendor"],
        "analyst_notes": "Initial intake note.",
    }
    payload.update(overrides)
    return payload


def create_case(client: TestClient, **overrides) -> dict:
    response = client.post("/cases", json=case_payload(**overrides))
    assert response.status_code == 201
    return response.json()


def test_case_creation_requires_scope_acknowledgment(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/cases",
            json=case_payload(scope_acknowledged=False),
        )

    assert response.status_code == 422


def test_case_crud_normalizes_tags_and_persists(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        created = create_case(client, title="  Vendor Domain Review  ")

        assert created["title"] == "Vendor Domain Review"
        assert created["scope_acknowledged"] is True
        assert created["entity_count"] == 0
        assert created["tags"] == ["vendor", "domain"]

        update_response = client.patch(
            f"/cases/{created['id']}",
            json={
                "status": "archived",
                "analyst_notes": "Updated note.",
                "tags": ["archive", "review"],
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["status"] == "archived"
        assert updated["entity_count"] == 0
        assert updated["analyst_notes"] == "Updated note."
        assert updated["tags"] == ["archive", "review"]

    with make_client(tmp_path, monkeypatch) as restarted_client:
        persisted_response = restarted_client.get(f"/cases/{created['id']}")
        assert persisted_response.status_code == 200
        persisted = persisted_response.json()
        assert persisted["id"] == created["id"]
        assert persisted["status"] == "archived"
        assert persisted["entity_count"] == 0


def test_entity_crud_supports_domain_and_url_and_persists(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)

        domain_response = client.post(
            f"/cases/{case['id']}/entities",
            json={
                "type": "domain",
                "value": "Example.COM.",
                "description": "Primary vendor domain.",
                "confidence": "medium",
                "tags": ["Primary", "Vendor"],
                "notes": "Added from intake.",
            },
        )
        assert domain_response.status_code == 201
        domain = domain_response.json()
        assert domain["value"] == "example.com"
        assert domain["display_name"] == "example.com"
        assert domain["tags"] == ["primary", "vendor"]

        url_response = client.post(
            f"/cases/{case['id']}/entities",
            json={
                "type": "url",
                "value": "HTTPS://Example.com/login?next=home#ignored",
                "display_name": "Login page",
                "confidence": "low",
            },
        )
        assert url_response.status_code == 201
        url = url_response.json()
        assert url["value"] == "https://example.com/login?next=home"

        update_response = client.patch(
            f"/entities/{domain['id']}",
            json={
                "display_name": "Vendor root domain",
                "confidence": "high",
                "notes": "Confirmed in public website footer.",
            },
        )
        assert update_response.status_code == 200
        updated_domain = update_response.json()
        assert updated_domain["display_name"] == "Vendor root domain"
        assert updated_domain["confidence"] == "high"
        assert updated_domain["notes"] == "Confirmed in public website footer."

    with make_client(tmp_path, monkeypatch) as restarted_client:
        entities_response = restarted_client.get(f"/cases/{case['id']}/entities")
        assert entities_response.status_code == 200
        entities = entities_response.json()
        assert {entity["value"] for entity in entities} == {
            "example.com",
            "https://example.com/login?next=home",
        }

        delete_response = restarted_client.delete(f"/entities/{url['id']}")
        assert delete_response.status_code == 204

        remaining_response = restarted_client.get(f"/cases/{case['id']}/entities")
        assert remaining_response.status_code == 200
        remaining = remaining_response.json()
        assert [entity["id"] for entity in remaining] == [domain["id"]]


def test_entity_validation_and_duplicate_protection(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)

        invalid_domain = client.post(
            f"/cases/{case['id']}/entities",
            json={"type": "domain", "value": "https://example.com/path"},
        )
        assert invalid_domain.status_code == 422

        invalid_url = client.post(
            f"/cases/{case['id']}/entities",
            json={"type": "url", "value": "example.com"},
        )
        assert invalid_url.status_code == 422

        first = client.post(
            f"/cases/{case['id']}/entities",
            json={"type": "domain", "value": "example.com"},
        )
        assert first.status_code == 201

        duplicate = client.post(
            f"/cases/{case['id']}/entities",
            json={"type": "domain", "value": "EXAMPLE.com"},
        )
        assert duplicate.status_code == 409


def test_deleting_case_removes_entities(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch) as client:
        case = create_case(client)
        entity_response = client.post(
            f"/cases/{case['id']}/entities",
            json={"type": "domain", "value": "example.com"},
        )
        assert entity_response.status_code == 201
        entity_id = entity_response.json()["id"]

        delete_response = client.delete(f"/cases/{case['id']}")
        assert delete_response.status_code == 204

        assert client.get(f"/cases/{case['id']}").status_code == 404
        assert client.get(f"/entities/{entity_id}").status_code == 404
