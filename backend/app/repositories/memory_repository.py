from sqlalchemy import select

from app.db.models.memory import MemoryItem
from app.repositories.base_repository import BaseRepository


class MemoryRepository(BaseRepository[MemoryItem]):
    model = MemoryItem

    async def all_for_user(self, user_id: str, limit: int = 500) -> list[MemoryItem]:
        stmt = select(MemoryItem).where(MemoryItem.user_id == user_id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
