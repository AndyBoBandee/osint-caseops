from pathlib import Path

from test_fraud_monitor import make_client


def test_operations_status_reports_local_health(tmp_path: Path, monkeypatch) -> None:
    with make_client(tmp_path, monkeypatch, providers="hn_algolia") as client:
        response = client.get("/fraud-monitor/operations")

    assert response.status_code == 200
    operations = response.json()
    assert operations["local_only"] is True
    assert operations["data_directory"]["exists"] is True
    assert operations["data_directory"]["writable"] is True
    assert operations["database"]["exists"] is True
    assert operations["database"]["case_count"] == 1
    assert operations["scheduler"]["interval_minutes"] == 60
    assert operations["retention_candidates"] == []


def test_operations_backup_can_be_created_downloaded_and_cleaned_up(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with make_client(tmp_path, monkeypatch, providers="hn_algolia") as client:
        create_response = client.post(
            "/fraud-monitor/operations/backups",
            json={"note": "release gate backup"},
        )
        status_response = client.get("/fraud-monitor/operations")

        assert create_response.status_code == 201
        backup = create_response.json()
        assert backup["filename"].startswith("fraud-monitor-backup-")
        assert backup["byte_size"] > 0
        assert "reviewed export bundle" in backup["includes"]

        backup_path = Path(backup["path"])
        assert backup_path.exists()
        assert backup_path.is_relative_to(tmp_path / "exports" / "operations")

        download_response = client.get(backup["download_url"])
        assert download_response.status_code == 200
        assert "release gate backup" in download_response.text

        operations = status_response.json()
        assert len(operations["backups"]) == 1
        assert len(operations["retention_candidates"]) == 1
        candidate = operations["retention_candidates"][0]

        cleanup_response = client.request(
            "DELETE",
            "/fraud-monitor/operations/retention-candidates",
            json={"candidate_ids": [candidate["id"]]},
        )

    assert cleanup_response.status_code == 200
    cleanup = cleanup_response.json()
    assert cleanup["deleted_count"] == 1
    assert cleanup["deleted_bytes"] == backup["byte_size"]
    assert cleanup["remaining_candidates"] == []
    assert not backup_path.exists()
