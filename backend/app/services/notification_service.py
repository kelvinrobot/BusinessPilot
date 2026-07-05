from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository
from app.websocket.manager import notification_manager


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NotificationRepository(session)

    async def notify(
        self, user_id: str, type: str, title: str, body: str | None = None, link: str | None = None
    ) -> Notification:
        notification = Notification(user_id=user_id, type=type, title=title, body=body, link=link)
        await self.repo.add(notification)
        await self.session.commit()

        await notification_manager.send_json_to_user(
            user_id,
            {
                "id": notification.id,
                "type": notification.type,
                "title": notification.title,
                "body": notification.body,
                "link": notification.link,
                "created_at": notification.created_at.isoformat(),
            },
        )
        return notification
