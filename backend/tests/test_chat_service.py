import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import redis.asyncio as aioredis

from app.services.chat_service import add_message, create_session, get_history


def _make_mock_redis(messages_store: dict | None = None):
    """Build a mock Redis that stores data in-memory."""
    mock = MagicMock(spec=aioredis.Redis)
    store: dict[str, str] = {}

    async def mock_setex(key, ttl, value):
        store[key] = value

    async def mock_get(key):
        return store.get(key)

    async def mock_delete(*keys):
        for k in keys:
            store.pop(k, None)

    async def mock_sadd(key, value):
        pass

    async def mock_expire(key, ttl):
        pass

    async def mock_aclose():
        pass

    mock.setex = AsyncMock(side_effect=mock_setex)
    mock.get = AsyncMock(side_effect=mock_get)
    mock.delete = AsyncMock(side_effect=mock_delete)
    mock.sadd = AsyncMock(side_effect=mock_sadd)
    mock.expire = AsyncMock(side_effect=mock_expire)
    mock.aclose = AsyncMock(side_effect=mock_aclose)

    return mock


def test_create_and_get_session():
    mock_redis = _make_mock_redis()

    async def _test():
        with patch("app.services.chat_service.aioredis.from_url", return_value=mock_redis):
            sid = await create_session("test-user")
            assert isinstance(sid, str)
            assert len(sid) == 36

            history = await get_history(sid)
            assert history == []

            await add_message(sid, "user", "hello")
            history = await get_history(sid)
            assert len(history) == 1
            assert history[0]["role"] == "user"
            assert history[0]["content"] == "hello"

            await add_message(sid, "assistant", "hi there", sql="SELECT 1")
            history = await get_history(sid)
            assert len(history) == 2
            assert history[1]["sql"] == "SELECT 1"

    asyncio.run(_test())


def test_add_message_with_result():
    mock_redis = _make_mock_redis()

    async def _test():
        with patch("app.services.chat_service.aioredis.from_url", return_value=mock_redis):
            sid = await create_session("test-user-2")
            await add_message(sid, "user", "query")
            await add_message(
                sid, "assistant", "here you go",
                sql="SELECT 1",
                result={"columns": ["a"], "rows": [[1]], "row_count": 1},
            )
            history = await get_history(sid)
            assert len(history) == 2
            assert history[1]["result"]["columns"] == ["a"]
            assert history[1]["result"]["row_count"] == 1

    asyncio.run(_test())
