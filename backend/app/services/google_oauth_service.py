"""Google OAuth2 flow for Gmail + Calendar (one consent grant covers both). Tokens are
encrypted at rest; refreshing happens transparently when building credentials."""

from __future__ import annotations

import os

# Google often returns granted scopes in a different order/casing than requested
# (e.g. adds "openid" implicitly). oauthlib treats that as a hard error unless relaxed.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from datetime import datetime, timezone

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import IntegrationError, NotFoundError
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository

logger = get_logger(__name__)


def _describe_oauth_exception(exc: Exception) -> dict:
    """Pull out whatever diagnostic detail is available from an oauthlib/requests
    exception so the failure is traceable instead of just 'something went wrong'."""
    detail: dict = {"exception_type": type(exc).__name__, "exception_message": str(exc)}
    # oauthlib.oauth2.rfc6749.errors.OAuth2Error subclasses
    for attr in ("error", "description", "uri", "status_code"):
        value = getattr(exc, attr, None)
        if value is not None:
            detail[f"oauth_{attr}"] = value
    # requests.exceptions.HTTPError / anything carrying a `.response`
    response = getattr(exc, "response", None)
    if response is not None:
        detail["http_status_code"] = getattr(response, "status_code", None)
        try:
            detail["http_response_body"] = response.text
        except Exception:
            pass
    return detail

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def build_authorization_url(state: str) -> str:
    if not settings.google_client_id or not settings.google_client_secret:
        raise IntegrationError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET."
        )

    flow = Flow.from_client_config(
        _client_config(), scopes=GOOGLE_SCOPES, redirect_uri=settings.google_redirect_uri
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent", state=state
    )
    return auth_url


class GoogleOAuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = IntegrationRepository(session)

    async def handle_callback(self, user_id: str, code: str) -> Integration:
        logger.info("oauth_callback_authorization_code_received", user_id=user_id, code_length=len(code))

        flow = Flow.from_client_config(
            _client_config(), scopes=GOOGLE_SCOPES, redirect_uri=settings.google_redirect_uri
        )

        logger.info("oauth_callback_token_exchange_started", user_id=user_id)
        try:
            flow.fetch_token(code=code)
        except Exception as exc:
            logger.error(
                "oauth_callback_token_exchange_failed",
                user_id=user_id,
                exc_info=True,
                **_describe_oauth_exception(exc),
            )
            raise IntegrationError(f"Google OAuth token exchange failed: {exc}") from exc

        creds = flow.credentials
        logger.info(
            "oauth_callback_token_exchange_succeeded",
            user_id=user_id,
            granted_scopes=creds.scopes,
            has_refresh_token=bool(creds.refresh_token),
            token_expiry=creds.expiry.isoformat() if creds.expiry else None,
        )

        account_email = None
        if creds.id_token:
            # creds.id_token is the RAW encoded JWT string from Google's token
            # response, not a decoded claims dict — must verify/decode it first.
            try:
                claims = google_id_token.verify_oauth2_token(
                    creds.id_token, GoogleAuthRequest(), settings.google_client_id
                )
                account_email = claims.get("email")
                logger.info("oauth_callback_id_token_decoded", user_id=user_id, account_email=account_email)
            except Exception as exc:
                # Email is only used for display in Settings ("Connected as ...");
                # losing it shouldn't block the connection from completing.
                logger.error(
                    "oauth_callback_id_token_decode_failed",
                    user_id=user_id,
                    exc_info=True,
                    **_describe_oauth_exception(exc),
                )

        logger.info("oauth_callback_persisting_tokens_started", user_id=user_id)
        try:
            existing = await self.repo.get_for_user(user_id, "google")
            if existing:
                existing.encrypted_access_token = encrypt_secret(creds.token)
                existing.encrypted_refresh_token = encrypt_secret(creds.refresh_token or "")
                existing.scopes = " ".join(creds.scopes or GOOGLE_SCOPES)
                existing.token_expiry = creds.expiry
                existing.account_email = account_email
                await self.session.flush()
                await self.session.commit()
                logger.info("oauth_callback_tokens_persisted", user_id=user_id, integration_id=existing.id)
                return existing

            integration = Integration(
                user_id=user_id,
                provider="google",
                encrypted_access_token=encrypt_secret(creds.token),
                encrypted_refresh_token=encrypt_secret(creds.refresh_token or ""),
                scopes=" ".join(creds.scopes or GOOGLE_SCOPES),
                token_expiry=creds.expiry,
                account_email=account_email,
            )
            await self.repo.add(integration)
            await self.session.commit()
            logger.info("oauth_callback_tokens_persisted", user_id=user_id, integration_id=integration.id)
            return integration
        except Exception as exc:
            logger.error("oauth_callback_token_persistence_failed", user_id=user_id, exc_info=True, error=str(exc))
            raise

    async def get_credentials(self, user_id: str) -> Credentials:
        integration = await self.repo.get_for_user(user_id, "google")
        if integration is None:
            raise NotFoundError("Google account is not connected. Connect it in Settings first.")

        creds = Credentials(
            token=decrypt_secret(integration.encrypted_access_token),
            refresh_token=decrypt_secret(integration.encrypted_refresh_token) or None,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=integration.scopes.split(),
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
            integration.encrypted_access_token = encrypt_secret(creds.token)
            integration.token_expiry = creds.expiry
            await self.session.flush()
            await self.session.commit()

        return creds

    async def is_connected(self, user_id: str) -> bool:
        return await self.repo.get_for_user(user_id, "google") is not None

    async def disconnect(self, user_id: str) -> None:
        integration = await self.repo.get_for_user(user_id, "google")
        if integration:
            await self.repo.delete(integration)
            await self.session.commit()
