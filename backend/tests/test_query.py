import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_query_rejects_destructive_sql(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/query/", json={
        "sql": "DROP TABLE users",
    }, headers=auth_headers)
    assert resp.status_code == 400
    assert "FORBIDDEN" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_query_rejects_delete(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/query/", json={
        "sql": "DELETE FROM orders WHERE id = 1",
    }, headers=auth_headers)
    assert resp.status_code == 400
