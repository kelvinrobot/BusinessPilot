import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import AsyncSessionLocal
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.notification import NotificationRead
from app.websocket.manager import notification_manager

router = APIRouter(prefix="/notifications", tags=["notifications"])

AUTH_TIMEOUT_SECONDS = 10


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[NotificationRead]:
    notifications = await NotificationRepository(db).list_for_user(current_user.id)
    return [NotificationRead.model_validate(n) for n in notifications]


@router.post("/read-all", status_code=204)
async def mark_all_read(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await NotificationRepository(db).mark_all_read(current_user.id)
    await db.commit()


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket) -> None:
    """
    Auth protocol (token in first message, not URL):
      Client → {"type": "auth", "token": "<access_token>"}
    Server pushes NotificationRead JSON objects as they arrive.
    """
    await websocket.accept()

    # ── Auth handshake ─────────────────────────────────────────────────────
    try:
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4401)
        return

    if not isinstance(auth_data, dict) or auth_data.get("type") != "auth":
        await websocket.close(code=4401)
        return

    try:
        user_id = decode_token(auth_data.get("token", ""), expected_type="access")
    except ValueError:
        await websocket.close(code=4401)
        return

    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get(user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4401)
            return

    # ── Register and hold open ─────────────────────────────────────────────
    notification_manager.register(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive; server pushes via notification_manager
    except WebSocketDisconnect:
        pass
    finally:
        notification_manager.disconnect(user_id, websocket)
