import json
from datetime import datetime

from pydantic import BaseModel, Field


class EmailDraftUpdate(BaseModel):
    to_addresses: list[str] | None = None
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=100_000)


class EmailDraftRead(BaseModel):
    id: str
    to_addresses: list[str]
    subject: str
    body: str
    status: str
    created_at: datetime

    @classmethod
    def from_orm_obj(cls, draft) -> "EmailDraftRead":
        return cls(
            id=draft.id,
            to_addresses=json.loads(draft.to_addresses_json),
            subject=draft.subject,
            body=draft.body,
            status=draft.status,
            created_at=draft.created_at,
        )
