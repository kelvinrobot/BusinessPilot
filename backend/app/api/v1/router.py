from fastapi import APIRouter

from app.api.v1 import auth, calendar, chat, documents, email, integrations, memory, notifications, tasks, voice

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(memory.router)
api_router.include_router(documents.router)
api_router.include_router(tasks.router)
api_router.include_router(integrations.router)
api_router.include_router(email.router)
api_router.include_router(calendar.router)
api_router.include_router(notifications.router)
api_router.include_router(voice.router)
