import json
import uuid
from datetime import timedelta

import redis.asyncio as aioredis

from app.core.config import settings

CHAT_TTL = int(timedelta(hours=1).total_seconds())


async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    r = await _get_redis()
    await r.setex(f"chat:{session_id}:user", CHAT_TTL, user_id)
    await r.setex(f"chat:{session_id}:messages", CHAT_TTL, json.dumps([]))
    await r.sadd(f"chat:user:{user_id}:sessions", session_id)
    await r.expire(f"chat:user:{user_id}:sessions", CHAT_TTL)
    await r.aclose()
    return session_id


async def get_history(session_id: str) -> list[dict]:
    r = await _get_redis()
    data = await r.get(f"chat:{session_id}:messages")
    await r.aclose()
    if data is None:
        return []
    return json.loads(data)


async def add_message(
    session_id: str,
    role: str,
    content: str,
    sql: str | None = None,
    result: dict | None = None,
) -> None:
    r = await _get_redis()
    data = await r.get(f"chat:{session_id}:messages")
    messages = json.loads(data) if data else []
    msg = {"role": role, "content": content}
    if sql:
        msg["sql"] = sql
    if result:
        msg["result"] = result
    messages.append(msg)
    await r.setex(f"chat:{session_id}:messages", CHAT_TTL, json.dumps(messages))
    await r.expire(f"chat:{session_id}:user", CHAT_TTL)
    await r.aclose()


async def get_user_sessions(user_id: str) -> list[str]:
    r = await _get_redis()
    members = await r.smembers(f"chat:user:{user_id}:sessions")
    await r.aclose()
    return sorted(members, reverse=True)


async def delete_session(session_id: str) -> None:
    r = await _get_redis()
    await r.delete(f"chat:{session_id}:messages", f"chat:{session_id}:user")
    await r.aclose()
