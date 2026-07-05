from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.db.models.user import User
from app.repositories.calendar_event_repository import CalendarEventRepository
from app.schemas.calendar_event import CalendarEventDraftRead
from app.services.calendar_service import CalendarService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events", response_model=list[CalendarEventDraftRead])
async def list_drafts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CalendarEventDraftRead]:
    drafts = await CalendarEventRepository(db).list_for_user(current_user.id, limit=limit)
    return [CalendarEventDraftRead.from_orm_obj(d) for d in drafts]


@router.post("/events/{draft_id}/approve", response_model=CalendarEventDraftRead)
async def approve_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CalendarEventDraftRead:
    draft = await CalendarService(db).approve_and_create(current_user.id, draft_id)
    await NotificationService(db).notify(
        current_user.id, type="meeting_scheduled", title=f'Meeting scheduled: "{draft.title}"'
    )
    return CalendarEventDraftRead.from_orm_obj(draft)


@router.post("/events/{draft_id}/reject", response_model=CalendarEventDraftRead)
async def reject_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CalendarEventDraftRead:
    draft = await CalendarService(db).reject_draft(current_user.id, draft_id)
    return CalendarEventDraftRead.from_orm_obj(draft)


@router.get("/events/{draft_id}", response_model=CalendarEventDraftRead)
async def get_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> CalendarEventDraftRead:
    draft = await CalendarEventRepository(db).get(draft_id)
    if draft is None or draft.user_id != current_user.id:
        raise NotFoundError("Calendar event draft not found.")
    return CalendarEventDraftRead.from_orm_obj(draft)
