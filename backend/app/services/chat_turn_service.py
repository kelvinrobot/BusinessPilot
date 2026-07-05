"""Single shared code path for processing one user turn (persist message, run the
multi-agent orchestrator, persist the reply, fire notifications). Used by both the text
`/chat` endpoint and the `/voice` WebSocket so text and voice share identical behavior."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import OrchestratorResult, run_orchestrator
from app.db.models.conversation import Conversation, Message
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.services.notification_service import NotificationService


@dataclass
class ChatTurnOutcome:
    conversation_id: str
    result: OrchestratorResult


async def get_or_create_conversation(
    db: AsyncSession, user_id: str, conversation_id: str | None, seed_title: str, channel: str
) -> Conversation:
    conv_repo = ConversationRepository(db)
    if conversation_id:
        conversation = await conv_repo.get(conversation_id)
        if conversation is not None and conversation.user_id == user_id:
            return conversation

    conversation = Conversation(user_id=user_id, title=seed_title[:60], channel=channel)
    await conv_repo.add(conversation)
    await db.commit()
    return conversation


async def process_user_turn(
    db: AsyncSession, user_id: str, conversation: Conversation, user_message: str
) -> ChatTurnOutcome:
    msg_repo = MessageRepository(db)

    history_rows = await msg_repo.list_for_conversation(conversation.id)
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    await msg_repo.add(Message(conversation_id=conversation.id, role="user", content=user_message))
    await db.commit()

    result = await run_orchestrator(user_id, db, conversation.id, user_message, history)

    await msg_repo.add(Message(conversation_id=conversation.id, role="assistant", content=result.reply))
    await db.commit()

    notifications = NotificationService(db)
    for doc in result.documents:
        await notifications.notify(
            user_id,
            type="document_ready",
            title=f'Document ready: {doc.get("title") or "Untitled"}',
            body="Your document has finished generating and is ready to download.",
            link=doc.get("download_url"),
        )
    for approval in result.pending_approvals:
        kind = "email draft" if "email_draft_id" in approval else "calendar proposal"
        await notifications.notify(
            user_id,
            type="approval_pending",
            title=f"A {kind} is ready for your approval",
            body=result.reply,
        )

    return ChatTurnOutcome(conversation_id=conversation.id, result=result)
