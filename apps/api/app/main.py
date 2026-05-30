from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cases import router as cases_router
from app.core.config import get_settings
from app.db.sqlite import check_database, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    yield

app = FastAPI(
    title="OSINT CaseOps API",
    version="0.1.0",
    summary="Local-first API for scoped OSINT case operations.",
    lifespan=lifespan,
)

app.include_router(cases_router)


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.service_name,
    }


@app.get("/health/db")
def database_health() -> dict[str, str]:
    return check_database()
