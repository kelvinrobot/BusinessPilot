import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationAppError
from app.db.models.user import User
from app.repositories.email_draft_repository import EmailDraftRepository
from app.schemas.email_draft import EmailDraftRead, EmailDraftUpdate
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/drafts", response_model=list[EmailDraftRead])
async def list_drafts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[EmailDraftRead]:
    drafts = await EmailDraftRepository(db).list_for_user(current_user.id, limit=limit)
    return [EmailDraftRead.from_orm_obj(d) for d in drafts]


@router.patch("/drafts/{draft_id}", response_model=EmailDraftRead)
async def update_draft(
    draft_id: str,
    payload: EmailDraftUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmailDraftRead:
    draft = await EmailDraftRepository(db).get(draft_id)
    if draft is None or draft.user_id != current_user.id:
        raise NotFoundError("Email draft not found.")
    if draft.status != "pending_approval":
        raise ValidationAppError("Only pending drafts can be edited.")
    if payload.to_addresses is not None:
        draft.to_addresses_json = json.dumps(payload.to_addresses)
    if payload.subject is not None:
        draft.subject = payload.subject
    if payload.body is not None:
        draft.body = payload.body
    await db.commit()
    await db.refresh(draft)
    return EmailDraftRead.from_orm_obj(draft)


@router.post("/drafts/{draft_id}/approve", response_model=EmailDraftRead)
async def approve_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> EmailDraftRead:
    draft = await EmailService(db).approve_and_send(current_user.id, draft_id)
    await NotificationService(db).notify(
        current_user.id, type="email_sent", title=f'Email sent: "{draft.subject}"'
    )
    return EmailDraftRead.from_orm_obj(draft)


@router.post("/drafts/{draft_id}/reject", response_model=EmailDraftRead)
async def reject_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> EmailDraftRead:
    draft = await EmailService(db).reject_draft(current_user.id, draft_id)
    return EmailDraftRead.from_orm_obj(draft)


@router.get("/drafts/{draft_id}", response_model=EmailDraftRead)
async def get_draft(
    draft_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> EmailDraftRead:
    draft = await EmailDraftRepository(db).get(draft_id)
    if draft is None or draft.user_id != current_user.id:
        raise NotFoundError("Email draft not found.")
    return EmailDraftRead.from_orm_obj(draft)
