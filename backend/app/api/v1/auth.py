from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.user import RefreshRequest, TokenPair, UserCreate, UserLogin, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def _decode_jti(refresh_token: str) -> tuple[str, str, datetime]:
    payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return payload["sub"], payload["jti"], exp


async def _issue_token_pair(user: User, db: AsyncSession) -> TokenPair:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _, jti, exp = _decode_jti(refresh_token)

    await RefreshTokenRepository(db).add(
        RefreshToken(user_id=user.id, jti=jti, expires_at=exp)
    )
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/signup", response_model=TokenPair, status_code=201)
@limiter.limit("5/minute")
async def signup(request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)) -> TokenPair:
    users = UserRepository(db)
    if await users.get_by_email(payload.email):
        raise ConflictError("An account with this email already exists.")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        business_name=payload.business_name,
        timezone=payload.timezone,
    )
    await users.add(user)
    return await _issue_token_pair(user, db)


@router.post("/login", response_model=TokenPair)
@limiter.limit("10/minute")
async def login(request: Request, payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenPair:
    users = UserRepository(db)
    user = await users.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    return await _issue_token_pair(user, db)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    try:
        user_id = decode_token(payload.refresh_token, expected_type="refresh")
        _, jti, _ = _decode_jti(payload.refresh_token)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    token_repo = RefreshTokenRepository(db)
    stored = await token_repo.get_by_jti(jti)
    if stored is None or stored.revoked:
        raise UnauthorizedError("Refresh token has been revoked")

    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    stored.revoked = True  # rotate: old refresh token is single-use
    await token_repo.session.flush()

    return await _issue_token_pair(user, db)


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> None:
    try:
        _, jti, _ = _decode_jti(payload.refresh_token)
    except Exception:
        return None

    token_repo = RefreshTokenRepository(db)
    stored = await token_repo.get_by_jti(jti)
    if stored is not None:
        stored.revoked = True
        await db.commit()


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
        await db.commit()
        await db.refresh(current_user)
    return current_user
