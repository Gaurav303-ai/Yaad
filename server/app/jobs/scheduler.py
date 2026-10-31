"""APScheduler configuration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.core.dates import INDIA_TIMEZONE
from app.jobs.digest import send_weekly_digest
from app.jobs.reminders import send_due_reminders

scheduler = AsyncIOScheduler(timezone=INDIA_TIMEZONE)
scheduler.add_job(
    send_due_reminders,
    "interval",
    minutes=1 if settings.demo_mode else 5,
    id="reminders",
)
scheduler.add_job(
    send_weekly_digest,
    CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=INDIA_TIMEZONE),
    id="weekly-digest",
)
