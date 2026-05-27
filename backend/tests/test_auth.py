import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    payload = {"username": "dup", "email": "dup@example.com", "password": "pass"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "username": "loginuser", "email": "login@example.com", "password": "pass123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "loginuser", "password": "pass123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_bad_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "username": "badpw", "email": "bad@example.com", "password": "correct",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "badpw", "password": "wrong",
    })
    assert resp.status_code == 401
