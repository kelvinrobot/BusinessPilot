"""Integration tests for timezone-aware calendar event creation."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.core.security import encrypt_secret
from app.db.models.calendar_event import CalendarEventDraft
from app.db.models.integration import Integration
from app.db.session import AsyncSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client: AsyncClient, email: str, tz: str = "Africa/Lagos") -> tuple[dict, str]:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "full_name": "TZ Tester", "timezone": tz},
    )
    assert resp.status_code == 201, resp.text
    tokens = resp.json()
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    return {"Authorization": f"Bearer {tokens['access_token']}"}, me.json()["id"]


async def _connect_google(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Integration(
            user_id=user_id,
            provider="google",
            encrypted_access_token=encrypt_secret("fake-access-token"),
            encrypted_refresh_token=encrypt_secret("fake-refresh-token"),
            scopes="https://www.googleapis.com/auth/calendar",
            account_email="founder@gmail.com",
        ))
        await db.commit()


async def _create_draft(user_id: str, tz: str = "Africa/Lagos") -> str:
    """Insert a CalendarEventDraft directly, bypassing the agent."""
    now = datetime.now(ZoneInfo(tz))
    async with AsyncSessionLocal() as db:
        draft = CalendarEventDraft(
            user_id=user_id,
            title="Timezone Test Meeting",
            description="Checking timezone handling",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
            attendees_json='["attendee@example.com"]',
            timezone=tz,
        )
        db.add(draft)
        await db.commit()
        return draft.id


def _make_fake_calendar_build(event_body_capture: list):
    """Return a `build` replacement that records every events().insert() body."""
    def fake_build(*args, **kwargs):
        service = MagicMock()

        def capture_insert(**insert_kwargs):
            event_body_capture.append(insert_kwargs.get("body", {}))
            result = MagicMock()
            result.execute.return_value = {
                "id": "evt-tz-123",
                "hangoutLink": "https://meet.google.com/test",
            }
            return result

        service.events.return_value.insert.side_effect = capture_insert
        return service

    return fake_build


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_stores_timezone(client: AsyncClient) -> None:
    """Timezone submitted at signup is persisted and returned in /auth/me."""
    headers, _ = await _signup(client, "tz_signup@example.com", "Africa/Lagos")
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["timezone"] == "Africa/Lagos"


@pytest.mark.asyncio
async def test_patch_me_updates_timezone(client: AsyncClient) -> None:
    """PATCH /auth/me lets the user change their timezone after signup."""
    headers, _ = await _signup(client, "tz_patch@example.com", "UTC")
    resp = await client.patch("/api/v1/auth/me", json={"timezone": "America/New_York"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "America/New_York"
    # Confirm it persisted.
    assert (await client.get("/api/v1/auth/me", headers=headers)).json()["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_calendar_draft_stores_timezone(client: AsyncClient) -> None:
    """A calendar draft stores its timezone and exposes it via the API."""
    headers, user_id = await _signup(client, "tz_draft@example.com", "Africa/Lagos")
    await _connect_google(user_id)
    draft_id = await _create_draft(user_id, "Africa/Lagos")

    resp = await client.get(f"/api/v1/calendar/events/{draft_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "Africa/Lagos"


@pytest.mark.asyncio
async def test_approve_sends_timezone_to_google_api(client: AsyncClient, monkeypatch) -> None:
    """Approving a draft sends start/end with IANA timeZone field to the Google Calendar API."""
    headers, user_id = await _signup(client, "tz_approve@example.com", "Africa/Lagos")
    await _connect_google(user_id)
    draft_id = await _create_draft(user_id, "Africa/Lagos")

    captured: list[dict] = []
    monkeypatch.setattr("app.services.calendar_service.build", _make_fake_calendar_build(captured))

    resp = await client.post(f"/api/v1/calendar/events/{draft_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "created"

    assert len(captured) == 1, "expected exactly one events().insert() call"
    event_body = captured[0]
    assert "timeZone" in event_body["start"], "start must carry timeZone"
    assert "timeZone" in event_body["end"], "end must carry timeZone"
    assert event_body["start"]["timeZone"] == "Africa/Lagos"
    assert event_body["end"]["timeZone"] == "Africa/Lagos"
    # dateTime must be timezone-aware (offset present).
    start_dt = datetime.fromisoformat(event_body["start"]["dateTime"])
    assert start_dt.tzinfo is not None, f"start dateTime must be tz-aware, got: {event_body['start']['dateTime']}"


@pytest.mark.asyncio
async def test_approve_sends_timezone_aware_datetimes_utc(client: AsyncClient, monkeypatch) -> None:
    """UTC timezone drafts also produce timezone-aware datetimes in the Google API call."""
    headers, user_id = await _signup(client, "tz_utc@example.com", "UTC")
    await _connect_google(user_id)
    draft_id = await _create_draft(user_id, "UTC")

    captured: list[dict] = []
    monkeypatch.setattr("app.services.calendar_service.build", _make_fake_calendar_build(captured))

    resp = await client.post(f"/api/v1/calendar/events/{draft_id}/approve", headers=headers)
    assert resp.status_code == 200
    event_body = captured[0]
    assert event_body["start"]["timeZone"] == "UTC"
    assert datetime.fromisoformat(event_body["start"]["dateTime"]).tzinfo is not None


@pytest.mark.asyncio
async def test_approve_returns_meet_link(client: AsyncClient, monkeypatch) -> None:
    """The approval response includes the Google Meet link returned by the Calendar API."""
    headers, user_id = await _signup(client, "tz_meetlink@example.com", "Europe/London")
    await _connect_google(user_id)
    draft_id = await _create_draft(user_id, "Europe/London")

    captured: list[dict] = []
    monkeypatch.setattr("app.services.calendar_service.build", _make_fake_calendar_build(captured))

    resp = await client.post(f"/api/v1/calendar/events/{draft_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["meet_link"] == "https://meet.google.com/test"


@pytest.mark.asyncio
async def test_calendar_draft_list_exposes_timezone(client: AsyncClient) -> None:
    """GET /calendar/events returns the timezone field on every draft."""
    headers, user_id = await _signup(client, "tz_list@example.com", "Asia/Tokyo")
    await _connect_google(user_id)
    await _create_draft(user_id, "Asia/Tokyo")

    resp = await client.get("/api/v1/calendar/events", headers=headers)
    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 1
    assert drafts[0]["timezone"] == "Asia/Tokyo"
