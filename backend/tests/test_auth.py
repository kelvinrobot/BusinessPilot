import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_login_me_flow(client: AsyncClient) -> None:
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "founder@example.com",
            "password": "supersecret123",
            "full_name": "Jane Founder",
            "business_name": "Acme Co",
        },
    )
    assert signup_resp.status_code == 201
    tokens = signup_resp.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    dup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "founder@example.com",
            "password": "supersecret123",
            "full_name": "Jane Founder",
        },
    )
    assert dup_resp.status_code == 409

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "founder@example.com", "password": "supersecret123"},
    )
    assert login_resp.status_code == 200
    login_tokens = login_resp.json()

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "founder@example.com"

    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "founder@example.com", "password": "wrong"},
    )
    assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient) -> None:
    signup_resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "rotate@example.com",
            "password": "supersecret123",
            "full_name": "Rotate Tester",
        },
    )
    tokens = signup_resp.json()

    refresh_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    reuse_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
