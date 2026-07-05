import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch):
    def fake_embed_text(text: str) -> list[float]:
        import hashlib

        digest = hashlib.sha256(text.encode()).digest()[:16]
        return [b / 255 for b in digest]

    monkeypatch.setattr("app.services.memory_service.embed_text", fake_embed_text)


@pytest.mark.asyncio
async def test_memory_crud(client: AsyncClient) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "memory1@example.com", "password": "supersecret123", "full_name": "Memory Tester"},
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    create_resp = await client.post(
        "/api/v1/memory",
        json={"content": "Prefers email replies in a formal tone.", "category": "preference"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    item = create_resp.json()
    assert item["category"] == "preference"

    list_resp = await client.get("/api/v1/memory", headers=headers)
    assert len(list_resp.json()) == 1

    delete_resp = await client.delete(f"/api/v1/memory/{item['id']}", headers=headers)
    assert delete_resp.status_code == 204

    final_list = await client.get("/api/v1/memory", headers=headers)
    assert final_list.json() == []
