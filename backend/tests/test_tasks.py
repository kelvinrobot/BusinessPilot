import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "supersecret123", "full_name": "Task Tester"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_task_crud_flow(client: AsyncClient) -> None:
    headers = await _auth_headers(client, "tasks1@example.com")

    create_resp = await client.post("/api/v1/tasks", json={"title": "Call supplier"}, headers=headers)
    assert create_resp.status_code == 201
    task = create_resp.json()
    assert task["status"] == "open"

    list_resp = await client.get("/api/v1/tasks", headers=headers)
    assert len(list_resp.json()) == 1

    patch_resp = await client.patch(
        f"/api/v1/tasks/{task['id']}", json={"status": "done"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "done"

    delete_resp = await client.delete(f"/api/v1/tasks/{task['id']}", headers=headers)
    assert delete_resp.status_code == 204

    final_list = await client.get("/api/v1/tasks", headers=headers)
    assert final_list.json() == []


@pytest.mark.asyncio
async def test_task_not_found_for_other_user(client: AsyncClient) -> None:
    headers_a = await _auth_headers(client, "tasks2a@example.com")
    headers_b = await _auth_headers(client, "tasks2b@example.com")

    create_resp = await client.post("/api/v1/tasks", json={"title": "Private task"}, headers=headers_a)
    task_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=headers_b)
    assert patch_resp.status_code == 404
