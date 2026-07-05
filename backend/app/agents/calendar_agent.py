from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.services.calendar_service import CalendarService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)

CALENDAR_SYSTEM_PROMPT = """You are the Calendar Agent for BusinessPilot AI. Your job is \
to interpret scheduling requests, resolve all dates and times to exact timezone-aware \
datetimes, and propose ONE specific meeting for the user to review and approve. You \
NEVER create the event yourself — you only propose it.

## Timezone rules (CRITICAL)
- The user's local timezone is provided to you as IANA format (e.g. Africa/Lagos, \
America/New_York, Europe/London). Use it for ALL date/time resolution.
- You are given "Current local time" — this is the exact moment "now" for the user.
- All output datetimes MUST include an explicit UTC offset, e.g. \
2026-07-15T14:00:00+01:00. Never output a bare datetime without an offset.
- Also include the user's IANA timezone name as a separate "timezone" field in your JSON.

## Natural language resolution (examples relative to the current local time given)
- "tomorrow at 2 PM"  → next calendar day, 14:00 in user timezone
- "next Friday at 10" → the coming Friday (not today if today is Friday), 10:00 user tz
- "in three hours"    → now + 3 hours, rounded to the next full 15-minute mark
- "Monday morning"    → next Monday, 09:00 user timezone
- "this afternoon"    → today, 15:00 user timezone
- If the user specifies no time, default to 10:00 user timezone
- If the user specifies no duration, default to 60 minutes
- Meetings may not start in the past — if the resolved time is already past, move to \
the next available slot the following day at the same time

## Busy-time avoidance
You will receive a list of already-busy ranges on the user's calendar. Do not propose \
a time that overlaps any busy range. Pick the next available slot if there is a conflict.

## Response format
Respond ONLY with valid JSON — no markdown, no explanation:
{
  "title": "<meeting title>",
  "description": "<agenda or notes>",
  "start_time": "<ISO 8601 with UTC offset, e.g. 2026-07-15T14:00:00+01:00>",
  "end_time":   "<ISO 8601 with UTC offset>",
  "timezone":   "<IANA timezone, e.g. Africa/Lagos>",
  "attendees":  ["<email>", ...]
}

Attendees is an empty list if none were mentioned."""


def _local_now(iana_tz: str) -> datetime:
    """Return the current datetime in the user's IANA timezone."""
    try:
        tz = ZoneInfo(iana_tz)
    except (ZoneInfoNotFoundError, Exception):
        tz = timezone.utc
    return datetime.now(tz)


class CalendarAgent(BaseAgent):
    name = "calendar"
    description = (
        "Checks availability and proposes meetings from natural language requests like "
        "'tomorrow at 2 PM', 'next Friday at 10', or 'in three hours'. Never creates "
        "an event — the user must approve the proposal first."
    )

    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        oauth = GoogleOAuthService(context.db)
        if not await oauth.is_connected(context.user_id):
            return AgentResult(
                agent=self.name,
                success=False,
                summary="Google account isn't connected yet. Connect it under Settings to use calendar features.",
            )

        calendar_service = CalendarService(context.db)
        user_tz = context.user_timezone or "UTC"
        local_now = _local_now(user_tz)
        utc_now = datetime.now(timezone.utc)
        window_end = utc_now + timedelta(days=14)

        try:
            busy_slots = await calendar_service.list_busy_slots(context.user_id, utc_now, window_end)
        except Exception as exc:
            logger.error("calendar_agent_freebusy_failed", error=str(exc))
            busy_slots = []

        client = get_qwen_client()
        messages = [
            {"role": "system", "content": CALENDAR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User's IANA timezone: {user_tz}\n"
                    f"Current local time: {local_now.strftime('%A, %Y-%m-%d %H:%M %Z%z')}\n"
                    f"Business context:\n{context.memory_block()}\n"
                    f"Busy time ranges (UTC, next 14 days): {busy_slots}\n"
                    f"Request:\n{instruction}"
                ),
            },
        ]

        try:
            response = await asyncio.to_thread(client.chat, messages, None, 0.2)
            parsed = extract_json(response.content)
            event_tz = parsed.get("timezone", user_tz)

            # Validate the timezone the model returned is usable; fall back to user tz.
            try:
                ZoneInfo(event_tz)
            except Exception:
                event_tz = user_tz

            start_time = datetime.fromisoformat(parsed["start_time"])
            end_time = datetime.fromisoformat(parsed["end_time"])

            # Ensure both datetimes are timezone-aware; attach user tz if the model
            # somehow returned a naive datetime despite the prompt instructions.
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=ZoneInfo(event_tz))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=ZoneInfo(event_tz))

        except Exception as exc:
            logger.error("calendar_agent_failed", error=str(exc))
            return AgentResult(
                agent=self.name, success=False, summary="Failed to propose a meeting time.", error=str(exc)
            )

        draft = await calendar_service.create_draft(
            user_id=context.user_id,
            title=parsed.get("title", "Meeting"),
            description=parsed.get("description"),
            start_time=start_time,
            end_time=end_time,
            attendees=parsed.get("attendees", []),
            timezone=event_tz,
        )

        return AgentResult(
            agent=self.name,
            success=True,
            summary=(
                f'Proposed "{draft.title}" on {start_time.strftime("%a %b %d, %I:%M %p %Z")}. '
                "Awaiting your approval to add it to your calendar."
            ),
            data={"calendar_draft_id": draft.id, "status": draft.status},
            requires_approval=True,
        )
