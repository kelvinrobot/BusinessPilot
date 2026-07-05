from __future__ import annotations

import asyncio

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.core.exceptions import NotFoundError
from app.core.json_utils import extract_json
from app.core.logging import get_logger
from app.services.email_service import EmailService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.qwen.client import get_qwen_client

logger = get_logger(__name__)

EMAIL_SYSTEM_PROMPT = """You are the Email Agent for BusinessPilot AI. You either (a) \
summarize/prioritize a list of inbox messages the user gives you, or (b) draft a new \
email or reply for the user. You NEVER send email yourself -- you only ever produce a \
draft for the user to review and approve.

If asked to draft/reply to an email, respond ONLY with JSON:
{"action": "draft", "to": ["<email address>"], "subject": "<subject>", "body": "<full \
professional email body>"}

If asked to summarize/prioritize inbox messages, respond ONLY with JSON:
{"action": "summarize", "reply": "<concise prioritized summary for the user>"}"""


class EmailAgent(BaseAgent):
    name = "email"
    description = (
        "Summarizes the inbox and drafts emails/replies. Never sends -- the user must "
        "explicitly approve a draft before it is sent via Gmail."
    )

    async def run(self, context: AgentContext, instruction: str) -> AgentResult:
        oauth = GoogleOAuthService(context.db)
        if not await oauth.is_connected(context.user_id):
            return AgentResult(
                agent=self.name,
                success=False,
                summary="Google account isn't connected yet. Connect it under Settings to use email features.",
            )

        email_service = EmailService(context.db)
        user_prompt = f"Business context:\n{context.memory_block()}\n\nRequest:\n{instruction}"

        if any(k in instruction.lower() for k in ("summarize", "inbox", "what's in my email", "prioritize")):
            try:
                messages = await email_service.list_recent_messages(context.user_id)
            except NotFoundError as exc:
                return AgentResult(agent=self.name, success=False, summary=str(exc))

            user_prompt += "\n\nInbox messages:\n" + "\n".join(
                f"- From {m['from']}, Subject: {m['subject']}, Snippet: {m['snippet']}" for m in messages
            )

        client = get_qwen_client()
        messages_payload = [
            {"role": "system", "content": EMAIL_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await asyncio.to_thread(client.chat, messages_payload, None, 0.4)
            parsed = extract_json(response.content)
        except Exception as exc:
            logger.error("email_agent_failed", error=str(exc))
            return AgentResult(agent=self.name, success=False, summary="Failed to process the email request.", error=str(exc))

        if parsed.get("action") == "summarize":
            return AgentResult(agent=self.name, success=True, summary=parsed.get("reply", ""))

        draft = await email_service.create_draft(
            user_id=context.user_id,
            to_addresses=parsed.get("to", []),
            subject=parsed.get("subject", ""),
            body=parsed.get("body", ""),
        )
        return AgentResult(
            agent=self.name,
            success=True,
            summary=f'Drafted an email to {", ".join(parsed.get("to", []))} ("{draft.subject}"). Awaiting your approval to send.',
            data={"email_draft_id": draft.id, "status": draft.status},
            requires_approval=True,
        )
