import json
from datetime import datetime

from pydantic import BaseModel


class CalendarEventDraftRead(BaseModel):
    id: str
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    attendees: list[str]
    status: str
    timezone: str
    meet_link: str | None
    created_at: datetime

    @classmethod
    def from_orm_obj(cls, draft) -> "CalendarEventDraftRead":
        return cls(
            id=draft.id,
            title=draft.title,
            description=draft.description,
            start_time=draft.start_time,
            end_time=draft.end_time,
            attendees=json.loads(draft.attendees_json),
            status=draft.status,
            timezone=draft.timezone,
            meet_link=draft.meet_link,
            created_at=draft.created_at,
        )
