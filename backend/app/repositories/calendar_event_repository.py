from app.db.models.calendar_event import CalendarEventDraft
from app.repositories.base_repository import BaseRepository


class CalendarEventRepository(BaseRepository[CalendarEventDraft]):
    model = CalendarEventDraft
