from fastapi import FastAPI

from app.core.config import get_settings
from app.db.sqlite import check_database


settings = get_settings()

app = FastAPI(
    title="OSINT CaseOps API",
    version="0.1.0",
    summary="Local-first API foundation for OSINT CaseOps.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.service_name,
    }


@app.get("/health/db")
def database_health() -> dict[str, str]:
    return check_database()
