from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.db.models.conversation import Conversation
from app.db.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import ChatRequest, ChatResponse, ConversationDetail, ConversationRead
from app.services.chat_turn_service import get_or_create_conversation, process_user_turn

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    conversation = await get_or_create_conversation(
        db, current_user.id, payload.conversation_id, payload.message, channel="text"
    )
    outcome = await process_user_turn(db, current_user.id, conversation, payload.message)

    return ChatResponse(
        conversation_id=outcome.conversation_id,
        reply=outcome.result.reply,
        pending_approvals=outcome.result.pending_approvals,
        documents=outcome.result.documents,
        agent_run_id=outcome.result.agent_run_id,
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Conversation]:
    return await ConversationRepository(db).list_for_user(current_user.id, limit=limit)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    conversation = await ConversationRepository(db).get_with_messages(conversation_id)
    if conversation is None or conversation.user_id != current_user.id:
        raise NotFoundError("Conversation not found.")
    return conversation
