"""Google Calendar integration. Checking availability is unrestricted; creating an
event on the user's real calendar only happens in `approve_and_create`, called
exclusively from the `/calendar/events/{id}/approve` endpoint."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApprovalRequiredError, IntegrationError
from app.db.models.calendar_event import CalendarEventDraft
from app.repositories.calendar_event_repository import CalendarEventRepository
from app.services.google_oauth_service import GoogleOAuthService


class CalendarService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.oauth = GoogleOAuthService(session)
        self.events = CalendarEventRepository(session)

    async def _calendar_client(self, user_id: str):
        creds = await self.oauth.get_credentials(user_id)
        return await asyncio.to_thread(build, "calendar", "v3", credentials=creds)

    async def list_busy_slots(self, user_id: str, time_min: datetime, time_max: datetime) -> list[dict]:
        service = await self._calendar_client(user_id)
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": "primary"}],
        }
        try:
            response = await asyncio.to_thread(lambda: service.freebusy().query(body=body).execute())
        except HttpError as exc:
            raise IntegrationError(f"Calendar freebusy query failed: {exc}") from exc

        return response.get("calendars", {}).get("primary", {}).get("busy", [])

    async def create_draft(
        self,
        user_id: str,
        title: str,
        description: str | None,
        start_time: datetime,
        end_time: datetime,
        attendees: list[str] | None = None,
        timezone: str = "UTC",
    ) -> CalendarEventDraft:
        draft = CalendarEventDraft(
            user_id=user_id,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            attendees_json=json.dumps(attendees or []),
            timezone=timezone,
            status="pending_approval",
        )
        await self.events.add(draft)
        await self.session.commit()
        return draft

    async def approve_and_create(self, user_id: str, draft_id: str) -> CalendarEventDraft:
        draft = await self.events.get(draft_id)
        if draft is None or draft.user_id != user_id:
            raise ApprovalRequiredError("Calendar event draft not found.")
        if draft.status == "created":
            return draft
        if draft.status not in ("pending_approval", "approved"):
            raise ApprovalRequiredError(f"Draft is in status '{draft.status}' and cannot be created.")

        service = await self._calendar_client(user_id)
        attendees = [{"email": a} for a in json.loads(draft.attendees_json)]
        tz_name = draft.timezone or "UTC"

        # SQLite does not preserve timezone info  SQLAlchemy stores tz-aware datetimes
        # as naive UTC. Re-attach UTC so the ISO string carries the required "+00:00" offset.
        from datetime import timezone as _utc
        start_dt = draft.start_time
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=_utc.utc)
        end_dt = draft.end_time
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=_utc.utc)

        event_body = {
            "summary": draft.title,
            "description": draft.description or "",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_name},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz_name},
            "attendees": attendees,
            "conferenceData": {
                "createRequest": {
                    "requestId": draft.id,
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        try:
            created = await asyncio.to_thread(
                lambda: service.events()
                .insert(
                    calendarId="primary",
                    body=event_body,
                    conferenceDataVersion=1,
                    sendUpdates="all" if attendees else "none",
                )
                .execute()
            )
        except HttpError as exc:
            draft.status = "failed"
            await self.session.commit()
            raise IntegrationError(f"Calendar event creation failed: {exc}") from exc

        draft.status = "created"
        draft.google_event_id = created.get("id")
        draft.meet_link = created.get("hangoutLink")
        await self.session.commit()
        return draft

    async def reject_draft(self, user_id: str, draft_id: str) -> CalendarEventDraft:
        draft = await self.events.get(draft_id)
        if draft is None or draft.user_id != user_id:
            raise ApprovalRequiredError("Calendar event draft not found.")
        draft.status = "rejected"
        await self.session.commit()
        return draft
