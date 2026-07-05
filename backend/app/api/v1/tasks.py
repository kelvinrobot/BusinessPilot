from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.db.models.task import Task
from app.db.models.user import User
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Task]:
    return await TaskRepository(db).list_for_user(current_user.id, limit=limit)


@router.post("", response_model=TaskRead, status_code=201)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    task = Task(user_id=current_user.id, **payload.model_dump())
    repo = TaskRepository(db)
    await repo.add(task)
    await db.commit()
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: str,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.user_id != current_user.id:
        raise NotFoundError("Task not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    await db.commit()
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = TaskRepository(db)
    task = await repo.get(task_id)
    if task is None or task.user_id != current_user.id:
        raise NotFoundError("Task not found.")
    await repo.delete(task)
    await db.commit()
