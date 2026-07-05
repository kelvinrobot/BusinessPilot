from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.core.security import encrypt_secret
from app.db.models.calendar_event import CalendarEventDraft
from app.db.models.email_draft import EmailDraft
from app.db.models.integration import Integration
from app.db.session import AsyncSessionLocal


async def _auth(client: AsyncClient, email: str) -> tuple[dict, str]:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "full_name": "Approval Tester"},
    )
    body = resp.json()
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    return {"Authorization": f"Bearer {body['access_token']}"}, me.json()["id"]


async def _connect_google(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            Integration(
                user_id=user_id,
                provider="google",
                encrypted_access_token=encrypt_secret("fake-access-token"),
                encrypted_refresh_token=encrypt_secret("fake-refresh-token"),
                scopes="https://www.googleapis.com/auth/gmail.send",
                account_email="founder@gmail.com",
            )
        )
        await db.commit()


async def _create_email_draft(user_id: str) -> str:
    async with AsyncSessionLocal() as db:
        draft = EmailDraft(
            user_id=user_id,
            to_addresses_json='["client@example.com"]',
            subject="Following up",
            body="Just checking in on the delivery.",
        )
        db.add(draft)
        await db.commit()
        return draft.id


async def _create_calendar_draft(user_id: str) -> str:
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        draft = CalendarEventDraft(
            user_id=user_id,
            title="Founder sync",
            description="Weekly check-in",
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, hours=1),
        )
        db.add(draft)
        await db.commit()
        return draft.id


def _fake_gmail_service() -> MagicMock:
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-123"}
    return service


def _fake_calendar_service() -> MagicMock:
    service = MagicMock()
    service.events.return_value.insert.return_value.execute.return_value = {"id": "evt-123"}
    return service


@pytest.mark.asyncio
async def test_email_draft_requires_approval_before_sending(client: AsyncClient, monkeypatch) -> None:
    headers, user_id = await _auth(client, "emailapprove@example.com")
    await _connect_google(user_id)
    draft_id = await _create_email_draft(user_id)

    monkeypatch.setattr("app.services.email_service.build", lambda *a, **k: _fake_gmail_service())

    list_resp = await client.get("/api/v1/email/drafts", headers=headers)
    assert list_resp.json()[0]["status"] == "pending_approval"

    approve_resp = await client.post(f"/api/v1/email/drafts/{draft_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_email_draft_can_be_rejected_instead_of_sent(client: AsyncClient) -> None:
    headers, user_id = await _auth(client, "emailreject@example.com")
    await _connect_google(user_id)
    draft_id = await _create_email_draft(user_id)

    reject_resp = await client.post(f"/api/v1/email/drafts/{draft_id}/reject", headers=headers)
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_calendar_draft_requires_approval_before_creating_event(client: AsyncClient, monkeypatch) -> None:
    headers, user_id = await _auth(client, "calapprove@example.com")
    await _connect_google(user_id)
    draft_id = await _create_calendar_draft(user_id)

    monkeypatch.setattr("app.services.calendar_service.build", lambda *a, **k: _fake_calendar_service())

    approve_resp = await client.post(f"/api/v1/calendar/events/{draft_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    body = approve_resp.json()
    assert body["status"] == "created"


@pytest.mark.asyncio
async def test_approval_endpoints_require_google_connection(client: AsyncClient) -> None:
    headers, user_id = await _auth(client, "noconnection@example.com")
    draft_id = await _create_email_draft(user_id)

    resp = await client.post(f"/api/v1/email/drafts/{draft_id}/approve", headers=headers)
    assert resp.status_code == 404
