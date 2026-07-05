from sqlalchemy import select

from app.db.models.notification import Notification
from app.repositories.base_repository import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def unread_count(self, user_id: str) -> int:
        items = await self.list_for_user(user_id, limit=1000)
        return sum(1 for i in items if not i.is_read)

    async def mark_all_read(self, user_id: str) -> None:
        stmt = select(Notification).where(
            Notification.user_id == user_id, Notification.is_read.is_(False)
        )
        result = await self.session.execute(stmt)
        for item in result.scalars().all():
            item.is_read = True
        await self.session.flush()
