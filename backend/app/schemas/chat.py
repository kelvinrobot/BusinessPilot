from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    conversation_id: str | None = None


class PendingApproval(BaseModel):
    agent: str
    email_draft_id: str | None = None
    calendar_draft_id: str | None = None
    status: str | None = None


class GeneratedDocument(BaseModel):
    document_id: str
    title: str | None = None
    download_url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    pending_approvals: list[dict] = []
    documents: list[dict] = []
    agent_run_id: str | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    channel: str
    created_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = []
