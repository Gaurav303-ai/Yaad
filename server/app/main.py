"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.supabase_client import create_supabase_admin
from app.core.telegram import start_telegram
from app.jobs.reminders import send_due_reminders
from app.jobs.scheduler import scheduler
from app.routers import conflicts, items, meetings, memory, people, telegram
from app.routers.telegram import process_telegram_update


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Create shared service clients and start the background scheduler."""
    supabase_admin = await create_supabase_admin()
    app.state.supabase_admin = supabase_admin
    scheduler.add_job(
        send_due_reminders,
        "interval",
        minutes=5,
        id="reminders",
        args=(supabase_admin,),
        replace_existing=True,
    )
    telegram_task = await start_telegram(
        lambda update: process_telegram_update(supabase_admin, update)
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if telegram_task is not None:
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass
        await supabase_admin.postgrest.aclose()


app = FastAPI(title="Yaad API", lifespan=lifespan)
client_origins = [settings.client_url]
client_origin_regex = None
if settings.app_env == "development":
    client_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
app.add_middleware(
    CORSMiddleware,
    allow_origins=client_origins,
    allow_origin_regex=client_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (meetings.router, items.router, conflicts.router, memory.router, people.router, telegram.router):
    app.include_router(router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the service health status."""
    return {"status": "ok"}
