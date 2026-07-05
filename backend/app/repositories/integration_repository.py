from sqlalchemy import select

from app.db.models.integration import Integration
from app.repositories.base_repository import BaseRepository


class IntegrationRepository(BaseRepository[Integration]):
    model = Integration

    async def get_for_user(self, user_id: str, provider: str) -> Integration | None:
        stmt = select(Integration).where(
            Integration.user_id == user_id, Integration.provider == provider
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
