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
        self.news_search_provider = getenv("OSINT_CASEOPS_NEWS_PROVIDER", "hn_algolia")
        self.brave_search_api_key = getenv("BRAVE_SEARCH_API_KEY", "")
        self.news_search_max_results = int(getenv("OSINT_CASEOPS_NEWS_MAX_RESULTS", "10"))
        providers = getenv("OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS", "gdelt,google_news_rss,hn_algolia")
        self.fraud_monitor_providers = [
            provider.strip().lower() for provider in providers.split(",") if provider.strip()
        ]
        self.fraud_monitor_scheduler_seconds = int(
            getenv("OSINT_CASEOPS_FRAUD_MONITOR_SCHEDULER_SECONDS", "60")
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
