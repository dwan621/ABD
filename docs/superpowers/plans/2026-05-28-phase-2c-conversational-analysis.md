# Phase 2C — Conversational Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Multi-turn conversational data analysis — users chat with AI, ask follow-up questions, and get SQL-powered responses with session history in Redis.

**Architecture:** Redis-backed chat sessions with 1-hour TTL. New `chat_service.py` manages session CRUD. Extended `llm_service.py` with `generate_chat_response()` that receives conversation history and decides whether SQL is needed. New `POST /ai/chat` endpoint orchestrates history → LLM → optional SQL execution → response. New `ChatPage.tsx` with session sidebar and message bubbles.

**Tech Stack:** Python/FastAPI/Redis (backend), React/TypeScript/Tailwind (frontend), DeepSeek v4-pro (LLM).

---

### Task 1: Create Chat History Service

**Files:**
- Create: `backend/app/services/chat_service.py`
- Create: `backend/tests/test_chat_service.py`

- [ ] **Step 1: Create chat_service.py**

```python
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


async def add_message(session_id: str, role: str, content: str, sql: str | None = None, result: dict | None = None) -> None:
    r = await _get_redis()
    messages = await get_history(session_id)
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
```

- [ ] **Step 2: Run quick smoke test in container**

```bash
docker exec abd-platform-fastapi-1 python -c "import asyncio; from app.services.chat_service import create_session, add_message, get_history; sid = asyncio.run(create_session('test')); asyncio.run(add_message(sid, 'user', 'hello')); h = asyncio.run(get_history(sid)); print(h)"
```

Expected: `[{'role': 'user', 'content': 'hello'}]`

- [ ] **Step 3: Commit**

---

### Task 2: Add Chat LLM Function

**Files:**
- Modify: `backend/app/services/llm_service.py` (append after generate_insights)

- [ ] **Step 1: Add generate_chat_response()**

```python
_CHAT_PROMPT = """\
You are a helpful data analyst assistant. You can answer questions about the user's data using natural language or by generating SQL queries.

Available tables:
{schema_context}

Conversation history:
{history}

If the user's question can be answered with a SQL query, respond with a JSON object:
{{"answer": "your explanation of what you're about to do", "sql": "SELECT ..."}}

If the question does NOT need SQL (e.g., asking about capabilities, clarifying, general discussion), respond with:
{{"answer": "your response", "sql": null}}

Rules:
- Only SELECT statements
- Use the exact table and column names from the schema
- Keep answers concise and conversational
- Return ONLY the JSON object, no markdown, no explanations

Example when SQL is needed:
{{"answer": "Let me find the top 5 products by sales for you.", "sql": "SELECT product_name, SUM(total_amount) FROM orders GROUP BY product_name ORDER BY 2 DESC LIMIT 5"}}

Example when no SQL is needed:
{{"answer": "I can help you analyze your ecommerce data. I have access to orders, products, and customer information. What would you like to know?"}}"""


def generate_chat_response(question: str, schema_context: str, history: list[dict]) -> dict:
    """Generate a conversational response, optionally with SQL."""
    client = _get_client()
    history_str = json.dumps(history[-10:]) if history else "[]"
    prompt = _CHAT_PROMPT.format(schema_context=schema_context, history=history_str)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=800,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty or null content")

    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        content = "\n".join(lines).strip()

    parsed = json.loads(content)
    if "answer" not in parsed:
        raise ValueError("Chat response missing 'answer' field")

    return {"answer": parsed["answer"], "sql": parsed.get("sql")}
```

- [ ] **Step 2: Test with simple question**

```bash
docker exec abd-platform-fastapi-1 python -c "
from app.services.llm_service import generate_chat_response
result = generate_chat_response('hello', 'Table: test\n  id: int', [])
print(result)
"
```

- [ ] **Step 3: Commit**

---

### Task 3: Add Chat API Endpoints

**Files:**
- Modify: `backend/app/api/ai.py` (append after insights endpoint)

- [ ] **Step 1: Add chat models and endpoints**

```python
class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sql: str | None = None
    result: dict | None = None


@router.post("/chat/sessions")
async def create_chat_session(
    current_user: User = Depends(get_current_user),
):
    session_id = await chat_service.create_session(str(current_user.id))
    return {"session_id": session_id}


@router.get("/chat/sessions/{session_id}")
async def get_chat_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    messages = await chat_service.get_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    result = await db.execute(select(Dataset))
    datasets = result.scalars().all()
    schema_context = build_schema_context([
        {"table_name": d.table_name, "schema_json": d.schema_json}
        for d in datasets
    ])

    history = await chat_service.get_history(body.session_id)
    await chat_service.add_message(body.session_id, "user", message)

    try:
        chat_result = generate_chat_response(message, schema_context, history)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    answer = chat_result["answer"]
    sql = chat_result.get("sql")
    query_result = None

    if sql:
        try:
            validate_sql(sql)
            query_result = execute_sql(sql)
        except Exception as e:
            logger.warning(f"Chat SQL execution failed: {e}")

    await chat_service.add_message(body.session_id, "assistant", answer, sql=sql, result=query_result)

    return ChatResponse(
        session_id=body.session_id,
        answer=answer,
        sql=sql,
        result=query_result,
    )
```

And add the import at the top:
```python
from app.services import chat_service
```

- [ ] **Step 2: Test endpoint**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
SID=$(curl -s -X POST http://localhost:8000/api/v1/ai/chat/sessions -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s -X POST http://localhost:8000/api/v1/ai/chat -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"session_id\":\"$SID\",\"message\":\"how many orders are there\"}"
```

- [ ] **Step 3: Commit**

---

### Task 4: Create Frontend ChatPage

**Files:**
- Create: `frontend/src/pages/ChatPage.tsx`

Full component with:
- Session sidebar (new session button, session list)
- Message area with auto-scroll
- User messages (right-aligned, blue)
- AI messages (left-aligned, gray) with optional SQL block + table/chart
- Loading state while AI thinks
- Error handling
- Enter to send, Shift+Enter for newline

(Full code in implementation step)

- [ ] **Step 1: Create ChatPage.tsx**
- [ ] **Step 2: Verify TypeScript compiles**
- [ ] **Step 3: Commit**

---

### Task 5: Wire Up Routes

**Files:**
- Modify: `frontend/src/App.tsx` — add `/chat` route
- Modify: `frontend/src/components/Layout.tsx` — add "Chat" nav link

- [ ] **Step 1: Add route and nav link**
- [ ] **Step 2: Verify**
- [ ] **Step 3: Commit**

---

### Task 6: E2E Verification

- [ ] **Step 1: Multi-turn conversation test**
- [ ] **Step 2: Session persistence test**
