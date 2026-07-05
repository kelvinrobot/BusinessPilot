"""Voice WebSocket: browser handles STT (Web Speech API) and TTS (SpeechSynthesis).
Backend receives final transcripts as JSON, runs the same Orchestrator as text chat,
and returns text replies. One conversation, one memory, one agent pipeline.

Auth protocol (avoids JWT in URL / server logs):
  1. Client connects — no token in the URL.
  2. Client immediately sends:  {"type": "auth", "token": "<access_token>"}
  3. Server validates the token within AUTH_TIMEOUT_SECONDS; closes 4401 if invalid/missing.
  4. Normal transcript exchange begins.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.repositories.user_repository import UserRepository
from app.services.chat_turn_service import get_or_create_conversation, process_user_turn

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

AUTH_TIMEOUT_SECONDS = 10


async def _authenticate(token: str) -> str | None:
    try:
        user_id = decode_token(token, expected_type="access")
    except ValueError:
        return None
    async with AsyncSessionLocal() as db:
        user = await UserRepository(db).get(user_id)
        return user_id if user is not None and user.is_active else None


@router.websocket("/ws")
async def voice_ws(
    websocket: WebSocket,
    conversation_id: str | None = Query(default=None),
) -> None:
    """
    Auth (client → server, first message):
      {"type": "auth", "token": "<access_token>"}

    Transcript (client → server):
      {"type": "transcript", "text": "<final transcript>"}

    Reply (server → client):
      {"type": "reply_text", "text": "...", "conversation_id": "...",
       "documents": [...], "pending_approvals": [...]}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()

    #  Auth handshake 
    try:
        auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, Exception):
        await websocket.close(code=4401)
        return

    if not isinstance(auth_data, dict) or auth_data.get("type") != "auth":
        await websocket.close(code=4401)
        return

    user_id = await _authenticate(auth_data.get("token", ""))
    if user_id is None:
        await websocket.close(code=4401)
        return

    #  Transcript loop 
    active_conversation_id = conversation_id

    try:
        async for data in websocket.iter_json():
            if data.get("type") != "transcript":
                continue
            text = (data.get("text") or "").strip()
            if not text:
                continue

            async with AsyncSessionLocal() as db:
                conversation = await get_or_create_conversation(
                    db, user_id, active_conversation_id, text, channel="voice"
                )
                active_conversation_id = conversation.id
                outcome = await process_user_turn(db, user_id, conversation, text)

            await websocket.send_json(
                {
                    "type": "reply_text",
                    "text": outcome.result.reply,
                    "conversation_id": outcome.conversation_id,
                    "documents": outcome.result.documents,
                    "pending_approvals": outcome.result.pending_approvals,
                }
            )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("voice_ws_failed", error=str(exc), exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": "An error occurred. Please try again."})
        except Exception:
            pass
