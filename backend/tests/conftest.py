import sys
from typing import AsyncGenerator
from unittest.mock import MagicMock

# -- Mock PySpark before ANY app module is imported ---------------------------
sys.modules["pyspark"] = MagicMock()
sys.modules["pyspark.sql"] = MagicMock()

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# -- Register ARRAY type compilation for SQLite (maps to JSON) ----------------
# SQLite does not support PostgreSQL ARRAY type. Compile ARRAY as JSON so
# the in-memory test database works. (JSON handles serialization natively,
# so no bind/result processor patches needed — just DDL compilation.)
@event.listens_for(engine.sync_engine, "connect")
def _register_array_for_sqlite(dbapi_connection, connection_record):
    """Compile ARRAY as JSON column type on SQLite."""
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

    def visit_ARRAY(self, type_, **kw):
        return "JSON"

    SQLiteTypeCompiler.visit_ARRAY = visit_ARRAY


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    await client.post("/api/v1/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
