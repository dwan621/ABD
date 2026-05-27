import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_datasource(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/datasources/", json={
        "name": "My CSV",
        "type": "csv",
        "config_json": {"path": "/data/sales.csv"},
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "My CSV"


@pytest.mark.asyncio
async def test_list_datasources(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/datasources/", json={
        "name": "DS1", "type": "csv", "config_json": {},
    }, headers=auth_headers)
    resp = await client.get("/api/v1/datasources/", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    resp = await client.get("/api/v1/datasources/")
    assert resp.status_code == 401
