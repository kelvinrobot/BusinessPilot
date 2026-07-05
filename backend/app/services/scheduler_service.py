"""Background reminders: scans for upcoming approved meetings and notifies the user
shortly before they start. Runs inside the FastAPI process via APScheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models.calendar_event import CalendarEventDraft
from app.db.session import AsyncSessionLocal
from app.services.notification_service import NotificationService

logger = get_logger(__name__)

REMINDER_WINDOW_MINUTES = 30

_scheduler = AsyncIOScheduler()


async def _scan_upcoming_meetings() -> None:
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=REMINDER_WINDOW_MINUTES)

    async with AsyncSessionLocal() as db:
        stmt = select(CalendarEventDraft).where(
            CalendarEventDraft.status == "created",
            CalendarEventDraft.reminder_sent.is_(False),
            CalendarEventDraft.start_time <= window_end,
            CalendarEventDraft.start_time >= now,
        )
        result = await db.execute(stmt)
        upcoming = list(result.scalars().all())

        if not upcoming:
            return

        notifications = NotificationService(db)
        for event in upcoming:
            await notifications.notify(
                event.user_id,
                type="meeting_reminder",
                title=f'Upcoming meeting: "{event.title}"',
                body=f'Starts at {event.start_time.strftime("%I:%M %p")} UTC.',
            )
            event.reminder_sent = True

        await db.commit()


def start_scheduler() -> None:
    if not _scheduler.running:
        _scheduler.add_job(_scan_upcoming_meetings, "interval", minutes=5, id="meeting_reminders")
        _scheduler.start()
        logger.info("scheduler_started")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
