from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryItemCreate, MemoryItemRead
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[MemoryItemRead])
async def list_memory(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MemoryItemRead]:
    items = await MemoryRepository(db).all_for_user(current_user.id)
    return [MemoryItemRead.model_validate(i) for i in items]


@router.post("", response_model=MemoryItemRead, status_code=201)
async def add_memory(
    payload: MemoryItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryItemRead:
    item = await MemoryService(db).store(
        current_user.id, payload.content, payload.category, payload.importance
    )
    await db.commit()
    return MemoryItemRead.model_validate(item)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    repo = MemoryRepository(db)
    item = await repo.get(memory_id)
    if item is not None and item.user_id == current_user.id:
        await repo.delete(item)
        await db.commit()
