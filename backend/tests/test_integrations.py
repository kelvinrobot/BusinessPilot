import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "full_name": "Integration Tester"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_google_status_disconnected_by_default(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "integ1@example.com")
    resp = await client.get("/api/v1/integrations/google/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "account_email": None}


@pytest.mark.asyncio
async def test_google_connect_fails_clearly_without_credentials(client: AsyncClient, monkeypatch) -> None:
    # Temporarily clear OAuth credentials to verify the 502 guard is in place.
    monkeypatch.setattr("app.core.config.settings.google_client_id", "")
    monkeypatch.setattr("app.core.config.settings.google_client_secret", "")
    headers = await _auth_headers(client, "integ2@example.com")
    resp = await client.get("/api/v1/integrations/google/connect", headers=headers)
    assert resp.status_code == 502
    assert "not configured" in resp.json()["detail"].lower()
