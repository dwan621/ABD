# Phase 2 — AI-Powered Analytics Design

> **Status:** Approved | **Date:** 2026-05-27

## Goal

Enable non-technical users to query data using natural language, get AI-generated insights, and have multi-turn analytical conversations — all powered by LLM (DeepSeek v4-pro).

## Scope & Phasing

| Phase | Feature | Dependencies |
|-------|---------|-------------|
| 2A | Text-to-SQL | None (builds on Phase 1 spark_bridge + datasets) |
| 2B | Intelligent Insights | 2A (reuses LLM service + prompt pipeline) |
| 2C | Conversational Analysis | 2A (reuses LLM service + chat history in Redis) |

**This spec covers 2A. 2B and 2C are described at a high level and will be designed in detail after 2A ships.**

---

## Phase 2A: Text-to-SQL

### Architecture

```
User (natural language)
  → POST /api/v1/ai/text-to-sql { question }
    → Query datasets table (PostgreSQL) for registered schemas
    → Build prompt (system: schemas + rules, user: question)
    → Call DeepSeek chat completions API
    → Parse SQL from response
    → validate_sql() security check
    → execute_sql() via spark_bridge
    → Return { sql, columns, rows, row_count, execution_time_ms }
```

### Backend

**New files:**

- `backend/app/services/llm_service.py`
  - `build_schema_context(db: AsyncSession) -> str` — queries datasets table, returns formatted schema string for prompt
  - `generate_sql(question: str, schema_context: str) -> str` — calls DeepSeek API, parses SQL from response
  - Uses OpenAI-compatible client (`openai` package or raw httpx to `LLM_BASE_URL`)

- `backend/app/api/ai.py`
  - `POST /api/v1/ai/text-to-sql` — accepts `{ question: str }`, returns `{ sql: str, columns: [...], rows: [...], row_count: int, execution_time_ms: float }`
  - Reuses `validate_sql()` from `app/api/query.py`
  - Reuses `execute_sql()` from `app/services/spark_bridge.py`

**Modified files:**

- `backend/app/api/router.py` — add `ai_router` include
- `backend/requirements.txt` — add `openai>=1.0.0` (or minimalist httpx approach)

**Config (already in place):**
- `LLM_BASE_URL=https://api.deepseek.com/v1`
- `LLM_API_KEY=sk-a7f7fbbb88034c73afe81b40282b9ba3`
- `LLM_MODEL=deepseek-v4-pro`

**Prompt design:**

```
System: You are a SQL expert. Given the following table schemas,
answer the user's question with a single SQL SELECT statement.
Return ONLY the SQL, no explanation, no markdown formatting.

Available tables:
[table_name]: [schema_json formatted as col_name:type pairs]

Rules:
- Only use SELECT statements
- Use LIMIT for top-N queries
- Prefer aggregations with GROUP BY for summaries

User: [natural language question]
```

### Frontend

**New files:**

- `frontend/src/pages/AIQeryPage.tsx`
  - Natural language input (textarea or large input)
  - "Ask AI" button with loading state
  - Generated SQL display (collapsible, default visible)
  - Results: reuse `DataTable` + `ChartView` components
  - Error states: LLM error / invalid SQL / execution error
  - Fallback: user can edit the generated SQL and re-execute via existing query endpoint

**Modified files:**

- `frontend/src/App.tsx` — add route `/ai-query`
- `frontend/src/components/Layout.tsx` — add "AI Query" nav link

**States:**
- Empty: centered input with 3 example questions as placeholders
- Loading: button spinner, "Generating SQL..." text
- Success: SQL block (collapsible) + results with table/chart toggle
- Error: red banner with specific message, input preserved for retry

### Security

- `validate_sql()` applied to LLM-generated SQL before execution
- Forbidden: DROP, DELETE, TRUNCATE, ALTER, UPDATE, INSERT, MERGE, CREATE, REPLACE
- LLM prompt explicitly restricts to SELECT only
- API endpoints behind JWT auth (reuse `get_current_user` dependency)

---

## Future: Phase 2B — Intelligent Insights

High-level direction:
- `POST /api/v1/ai/insights/{dataset_id}` — one-click auto-analysis
- Backend reads schema + samples recent rows, sends to LLM with insight-generation prompt
- LLM returns structured insights (trends, anomalies, rankings) + verification SQLs
- Backend executes verification SQLs, appends data to insights
- Return: `{ insights: [{ title, description, chart_data, sql }] }`
- Frontend: new "Insights" tab on Dataset page, or a dedicated InsightsPage

## Future: Phase 2C — Conversational Analysis

High-level direction:
- `POST /api/v1/ai/chat` — multi-turn conversation endpoint
- Session-based chat history stored in Redis (keyed by session_id, TTL 1 hour)
- Each turn: LLM receives conversation history + current question, decides whether to generate SQL
- If SQL: executes and returns results + explanation
- If not: returns direct LLM response
- Frontend: new ChatPage with message bubbles, SQL results inline in conversation
- Session management: create new session, list history, resume previous

---

## Testing

- Unit: `llm_service.py` — prompt building, SQL parsing (mock LLM response)
- Unit: `ai.py` — endpoint behavior (mock llm_service)
- Manual: end-to-end with real DeepSeek API + ecommerce_orders dataset
