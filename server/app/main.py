"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.jobs.scheduler import scheduler
from app.routers import conflicts, items, meetings, people, telegram


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start and stop the background scheduler with the application."""
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Yaad API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.client_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (meetings.router, items.router, conflicts.router, people.router, telegram.router):
    app.include_router(router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "ok"}
