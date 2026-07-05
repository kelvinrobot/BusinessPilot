"""Gmail integration. Reading/summarizing the inbox is unrestricted; sending mail is
only ever performed by `send_draft`, which the API layer calls exclusively from the
`/email/drafts/{id}/approve` endpoint after the user has explicitly approved a draft."""

from __future__ import annotations

import asyncio
import base64
import json
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ApprovalRequiredError, IntegrationError
from app.db.base import utcnow
from app.db.models.email_draft import EmailDraft
from app.repositories.email_draft_repository import EmailDraftRepository
from app.services.google_oauth_service import GoogleOAuthService


class EmailService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.oauth = GoogleOAuthService(session)
        self.drafts = EmailDraftRepository(session)

    async def _gmail_client(self, user_id: str):
        creds = await self.oauth.get_credentials(user_id)
        return await asyncio.to_thread(build, "gmail", "v1", credentials=creds)

    async def list_recent_messages(self, user_id: str, max_results: int = 10) -> list[dict]:
        service = await self._gmail_client(user_id)
        try:
            response = await asyncio.to_thread(
                lambda: service.users()
                .messages()
                .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
                .execute()
            )
        except HttpError as exc:
            raise IntegrationError(f"Gmail list failed: {exc}") from exc

        messages = []
        for ref in response.get("messages", []):
            detail = await asyncio.to_thread(
                lambda ref=ref: service.users()
                .messages()
                .get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            messages.append(
                {
                    "id": detail["id"],
                    "snippet": detail.get("snippet", ""),
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                }
            )
        return messages

    async def create_draft(
        self, user_id: str, to_addresses: list[str], subject: str, body: str, in_reply_to: str | None = None
    ) -> EmailDraft:
        draft = EmailDraft(
            user_id=user_id,
            to_addresses_json=json.dumps(to_addresses),
            subject=subject,
            body=body,
            in_reply_to_message_id=in_reply_to,
            status="pending_approval",
        )
        await self.drafts.add(draft)
        await self.session.commit()
        return draft

    async def approve_and_send(self, user_id: str, draft_id: str) -> EmailDraft:
        draft = await self.drafts.get(draft_id)
        if draft is None or draft.user_id != user_id:
            raise ApprovalRequiredError("Email draft not found.")
        if draft.status == "sent":
            return draft
        if draft.status not in ("pending_approval", "approved"):
            raise ApprovalRequiredError(f"Draft is in status '{draft.status}' and cannot be sent.")

        service = await self._gmail_client(user_id)
        to_addresses = json.loads(draft.to_addresses_json)

        message = MIMEText(draft.body)
        message["to"] = ", ".join(to_addresses)
        message["subject"] = draft.subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            await asyncio.to_thread(
                lambda: service.users().messages().send(userId="me", body={"raw": raw}).execute()
            )
        except HttpError as exc:
            draft.status = "failed"
            await self.session.commit()
            raise IntegrationError(f"Gmail send failed: {exc}") from exc

        draft.status = "sent"
        draft.sent_at = utcnow()
        await self.session.commit()
        return draft

    async def reject_draft(self, user_id: str, draft_id: str) -> EmailDraft:
        draft = await self.drafts.get(draft_id)
        if draft is None or draft.user_id != user_id:
            raise ApprovalRequiredError("Email draft not found.")
        draft.status = "rejected"
        await self.session.commit()
        return draft
