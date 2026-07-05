from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.db.models.user import User
from app.repositories.integration_repository import IntegrationRepository
from app.services.google_oauth_service import GoogleOAuthService, build_authorization_url

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _make_state_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "purpose": "google_oauth_state",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _read_state_token(state: str) -> str:
    try:
        payload = jwt.decode(state, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired OAuth state") from exc
    if payload.get("purpose") != "google_oauth_state":
        raise UnauthorizedError("Invalid OAuth state")
    return payload["sub"]


@router.get("/google/connect")
async def google_connect(current_user: User = Depends(get_current_user)) -> dict:
    state = _make_state_token(current_user.id)
    return {"authorization_url": build_authorization_url(state)}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...), state: str = Query(...), db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    logger.info("oauth_callback_started")
    try:
        user_id = _read_state_token(state)
        logger.info("oauth_callback_state_validation_passed", user_id=user_id)

        service = GoogleOAuthService(db)
        await service.handle_callback(user_id, code)

        logger.info("oauth_callback_redirecting", user_id=user_id, result="connected")
        return RedirectResponse(url=f"{settings.frontend_origin}/settings?google=connected")
    except Exception as exc:
        logger.error(
            "oauth_callback_failed_redirecting_with_error",
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return RedirectResponse(url=f"{settings.frontend_origin}/settings?google=error")


@router.get("/google/status")
async def google_status(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    integration = await IntegrationRepository(db).get_for_user(current_user.id, "google")
    return {
        "connected": integration is not None,
        "account_email": integration.account_email if integration else None,
    }


@router.delete("/google", status_code=204)
async def google_disconnect(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await GoogleOAuthService(db).disconnect(current_user.id)
