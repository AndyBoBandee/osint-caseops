from functools import lru_cache
from os import getenv
from pathlib import Path


class Settings:
    """Runtime settings for the local-first API."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        data_dir = getenv("OSINT_CASEOPS_DATA_DIR")
        self.data_dir = Path(data_dir).expanduser().resolve() if data_dir else repo_root / "data"
        self.database_path = self.data_dir / "osint_caseops.sqlite3"
        self.service_name = "osint-caseops-api"


@lru_cache
def get_settings() -> Settings:
    return Settings()
