import hashlib
import json

import pytest
from httpx import AsyncClient


def _fake_embed_text(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()[:16]
    return [b / 255 for b in digest]


def _fake_chat(self, messages, tools=None, temperature=0.4, tool_choice="auto"):
    from app.services.qwen.client import ChatResult

    system_prompt = messages[0]["content"]

    if "You are the Planner" in system_prompt:
        user_content = messages[1]["content"]
        if "business plan" in user_content.lower():
            content = json.dumps(
                {
                    "steps": [{"agent": "document", "instruction": "Write a one-page business plan for a coffee shop."}],
                    "direct_reply": None,
                    "reasoning": "User wants a document.",
                }
            )
        else:
            content = json.dumps(
                {"steps": [], "direct_reply": "Hello! How can I help your business today?", "reasoning": "Small talk."}
            )
        return ChatResult(content=content)

    if "You are the Document Agent" in system_prompt:
        content = json.dumps(
            {
                "title": "Coffee Shop Business Plan",
                "doc_type": "business_plan",
                "format": "docx",
                "sections": [
                    {"heading": "Executive Summary", "body": "A cozy neighborhood coffee shop."},
                    {"heading": "Market Analysis", "body": "Local foot traffic is strong."},
                    {"heading": "Financial Projections", "body": "Break-even within 18 months."},
                ],
            }
        )
        return ChatResult(content=content)

    if "You are the Reviewer" in system_prompt:
        content = json.dumps(
            {
                "verdict": "approved",
                "retry_step": None,
                "retry_feedback": None,
                "final_reply": "I've created your business plan document.",
            }
        )
        return ChatResult(content=content)

    if "durable facts worth remembering" in system_prompt:
        return ChatResult(content="[]")

    return ChatResult(content="{}")


@pytest.fixture(autouse=True)
def _mock_qwen(monkeypatch):
    monkeypatch.setattr("app.services.qwen.client.QwenClient.chat", _fake_chat)
    monkeypatch.setattr("app.services.memory_service.embed_text", _fake_embed_text)


async def _signup_and_get_token(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "full_name": "Test User"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_simple_chat_direct_reply(client: AsyncClient) -> None:
    token = await _signup_and_get_token(client, "chatuser1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/v1/chat", json={"message": "Hi there!"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Hello! How can I help your business today?"
    assert body["documents"] == []
    assert body["conversation_id"]


@pytest.mark.asyncio
async def test_chat_generates_document(client: AsyncClient) -> None:
    token = await _signup_and_get_token(client, "chatuser2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/chat",
        json={"message": "Please write me a business plan for my coffee shop."},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "I've created your business plan document."
    assert len(body["documents"]) == 1
    document_id = body["documents"][0]["document_id"]

    docs_resp = await client.get("/api/v1/documents", headers=headers)
    assert docs_resp.status_code == 200
    assert any(d["id"] == document_id for d in docs_resp.json())

    download_resp = await client.get(f"/api/v1/documents/{document_id}/download", headers=headers)
    assert download_resp.status_code == 200
    assert len(download_resp.content) > 0


@pytest.mark.asyncio
async def test_conversation_history_persisted(client: AsyncClient) -> None:
    token = await _signup_and_get_token(client, "chatuser3@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/api/v1/chat", json={"message": "Hi there!"}, headers=headers)
    conversation_id = first.json()["conversation_id"]

    await client.post(
        "/api/v1/chat",
        json={"message": "Still there?", "conversation_id": conversation_id},
        headers=headers,
    )

    detail = await client.get(f"/api/v1/chat/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 4  # 2 user + 2 assistant
