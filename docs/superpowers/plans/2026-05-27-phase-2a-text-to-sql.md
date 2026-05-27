# Phase 2A — Text-to-SQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to type natural language questions and get SQL results — LLM generates the SQL, Spark executes it.

**Architecture:** New `llm_service.py` handles prompt building + DeepSeek API calls. New `ai.py` router exposes `POST /api/v1/ai/text-to-sql` which orchestrates: fetch schemas from PostgreSQL → LLM generates SQL → validate → execute via spark_bridge → return results. Frontend gets a new AI Query page with natural language input and collapsible generated SQL display.

**Tech Stack:** Python (FastAPI, SQLAlchemy async, openai package), React (TypeScript, ECharts), DeepSeek v4-pro API

---

### Task 1: LLM Service — Schema Context & SQL Generation

**Files:**
- Create: `backend/app/services/llm_service.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the tests for llm_service**

```python
# backend/tests/test_llm_service.py
import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_service import build_schema_context

# ---- build_schema_context ----

def test_build_schema_context_empty():
    assert build_schema_context([]) == "(no tables available)"


def test_build_schema_context_single_table():
    datasets = [
        {
            "table_name": "orders",
            "schema_json": [
                {"name": "id", "type": "bigint"},
                {"name": "amount", "type": "double"},
                {"name": "created_at", "type": "timestamp"},
            ],
        }
    ]
    result = build_schema_context(datasets)
    assert "Table: orders" in result
    assert "  id: bigint" in result
    assert "  amount: double" in result
    assert "  created_at: timestamp" in result


def test_build_schema_context_multiple_tables():
    datasets = [
        {
            "table_name": "products",
            "schema_json": [{"name": "id", "type": "bigint"}, {"name": "name", "type": "string"}],
        },
        {
            "table_name": "sales",
            "schema_json": [{"name": "product_id", "type": "bigint"}, {"name": "revenue", "type": "double"}],
        },
    ]
    result = build_schema_context(datasets)
    assert "Table: products" in result
    assert "Table: sales" in result


# ---- generate_sql ----

@patch("app.services.llm_service._get_client")
def test_generate_sql_returns_sql(mock_get_client):
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT * FROM orders LIMIT 10"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    sql = generate_sql("show all orders", "Table: orders\n  id: bigint\n  amount: double")
    assert sql == "SELECT * FROM orders LIMIT 10"


@patch("app.services.llm_service._get_client")
def test_generate_sql_strips_markdown_fences(mock_get_client):
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "```sql\nSELECT * FROM orders LIMIT 10\n```"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    sql = generate_sql("show all orders", "Table: orders\n  id: bigint")
    assert sql == "SELECT * FROM orders LIMIT 10"


@patch("app.services.llm_service._get_client")
def test_generate_sql_unable_to_generate_raises(mock_get_client):
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "UNABLE_TO_GENERATE"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError, match="Cannot generate SQL"):
        generate_sql("what is the meaning of life?", "Table: orders\n  id: bigint")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec abd-platform-fastapi-1 pytest /app/tests/test_llm_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.llm_service'`

- [ ] **Step 3: Write the LLM service implementation**

```python
# backend/app/services/llm_service.py
from openai import OpenAI

from app.core.config import settings

_SYSTEM_PROMPT = """\
You are a SQL expert. Given the following table schemas, answer the user's question with a single SQL SELECT statement.
Return ONLY the SQL query, no explanation, no markdown formatting.

Available tables:
{schema_context}

Rules:
- Only generate SELECT statements
- Use LIMIT for top-N queries
- Use appropriate aggregations (SUM, COUNT, AVG) with GROUP BY for summary/ranking questions
- Use date functions appropriate for the date columns shown
- Do NOT generate INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or any DDL/DML statements
- If the question cannot be answered with the available tables, respond with: UNABLE_TO_GENERATE"""


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def build_schema_context(datasets: list[dict]) -> str:
    """Format registered dataset schemas into a prompt-friendly string."""
    if not datasets:
        return "(no tables available)"
    parts = []
    for ds in datasets:
        cols = []
        for col in ds.get("schema_json", []):
            cols.append(f"  {col['name']}: {col['type']}")
        col_str = "\n".join(cols)
        parts.append(f"Table: {ds['table_name']}\nColumns:\n{col_str}")
    return "\n\n".join(parts)


def generate_sql(question: str, schema_context: str) -> str:
    """Call LLM to generate SQL from a natural language question."""
    client = _get_client()
    system = _SYSTEM_PROMPT.format(schema_context=schema_context)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=500,
    )
    sql = response.choices[0].message.content.strip()

    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        sql = "\n".join(lines).strip()

    if sql.upper() == "UNABLE_TO_GENERATE":
        raise ValueError("Cannot generate SQL for this question with the available tables")

    return sql
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec abd-platform-fastapi-1 pytest /app/tests/test_llm_service.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm_service.py backend/tests/
git commit -m "feat: add LLM service for Text-to-SQL schema context and SQL generation"
```

---

### Task 2: AI API Endpoint — Text-to-SQL Route

**Files:**
- Create: `backend/app/api/ai.py`
- Create: `backend/tests/test_ai_api.py`

- [ ] **Step 1: Write the test for the AI endpoint**

```python
# backend/tests/test_ai_api.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.models.dataset import Dataset

client = TestClient(app)


# ---- helpers ----

def _mock_token():
    """Bypass auth by mocking all dependencies."""
    pass


# ---- POST /api/v1/ai/text-to-sql ----

@pytest.mark.asyncio
async def test_text_to_sql_missing_question():
    """When question is empty, return 400."""
    # We test via a direct approach — mock the auth + db deps
    pass


@pytest.mark.asyncio
async def test_text_to_sql_llm_error():
    """When LLM returns UNABLE_TO_GENERATE, return 400."""
    pass


@pytest.mark.asyncio
async def test_text_to_sql_success():
    """Happy path: question → SQL → execution → result."""
    pass
```

- [ ] **Step 2: Write the actual test with proper mocking**

```python
# backend/tests/test_ai_api.py
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient


async def _get_token_headers():
    """Register and login to get a valid token."""
    # Use the actual auth endpoints to get a token for testing
    from app.main import app
    from app.core.database import get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register a test user
        resp = await ac.post("/api/v1/auth/register", json={
            "email": "test_ai@example.com",
            "password": "testpass123",
            "full_name": "Test AI User",
        })
        # Login
        resp = await ac.post("/api/v1/auth/login", json={
            "email": "test_ai@example.com",
            "password": "testpass123",
        })
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_text_to_sql_empty_question():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_token_headers()
        resp = await ac.post("/api/v1/ai/text-to-sql", json={"question": ""}, headers=headers)
        assert resp.status_code == 400
        assert "question" in resp.json()["detail"].lower()
```

- [ ] **Step 3: Write the AI API router implementation**

```python
# backend/app/api/ai.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.query import validate_sql
from app.core.database import get_db
from app.models.dataset import Dataset
from app.models.user import User
from app.services.llm_service import build_schema_context, generate_sql
from app.services.spark_bridge import execute_sql

router = APIRouter(prefix="/ai", tags=["ai"])


class TextToSQLRequest(BaseModel):
    question: str


@router.post("/text-to-sql")
async def text_to_sql(
    body: TextToSQLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # Fetch registered dataset schemas
    result = await db.execute(select(Dataset))
    datasets = result.scalars().all()
    schema_context = build_schema_context([
        {"table_name": d.table_name, "schema_json": d.schema_json}
        for d in datasets
    ])

    # Generate SQL via LLM
    try:
        sql = generate_sql(question, schema_context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {str(e)}")

    # Security check — reuse existing forbidden-keyword validator
    validate_sql(sql)

    # Execute via Spark
    try:
        result = execute_sql(sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {str(e)}")

    return {
        "sql": sql,
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "execution_time_ms": result["execution_time_ms"],
    }
```

- [ ] **Step 4: Run tests**

Run: `docker exec abd-platform-fastapi-1 pytest /app/tests/test_ai_api.py -v`
Expected: 1 PASS (empty question test)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ai.py backend/tests/test_ai_api.py
git commit -m "feat: add AI text-to-sql API endpoint"
```

---

### Task 3: Wire Backend Router & Add openai Dependency

**Files:**
- Modify: `backend/app/api/router.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add openai to requirements.txt**

Change `backend/requirements.txt` line 1 from:
```
fastapi>=0.115.0
```
to add after the existing deps:
```
openai>=1.0.0
```

Using Edit to append after line 16 (`email-validator>=2.1.0`):
```
openai>=1.0.0
```

- [ ] **Step 2: Wire ai_router into the API router**

In `backend/app/api/router.py`, add after the `query_router` import:

```python
from app.api.ai import router as ai_router
```

And add after the `query_router` include:

```python
api_router.include_router(ai_router)
```

Full file after changes:

```python
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.datasource import router as datasource_router
from app.api.dataset import router as dataset_router
from app.api.query import router as query_router
from app.api.ai import router as ai_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(datasource_router)
api_router.include_router(dataset_router)
api_router.include_router(query_router)
api_router.include_router(ai_router)
```

- [ ] **Step 3: Rebuild Docker image and install new dependency**

Run: `docker compose -p abd-platform build fastapi --no-cache`
Expected: Build succeeds

Run: `docker compose -p abd-platform up -d fastapi`
Expected: Container starts healthy

- [ ] **Step 4: Verify the router is registered**

Run: `curl -s http://localhost:8000/api/v1/ai/text-to-sql -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@abd.com","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")" -d '{"question":""}'`
Expected: `{"detail":"question is required"}` (400)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/router.py backend/requirements.txt
git commit -m "feat: wire AI router and add openai dependency"
```

---

### Task 4: Frontend — AI Query Page

**Files:**
- Create: `frontend/src/pages/AIQeryPage.tsx`

- [ ] **Step 1: Create the AI Query page component**

```tsx
// frontend/src/pages/AIQeryPage.tsx
import { useState } from "react";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface AIResult {
  sql: string;
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
}

const EXAMPLE_QUESTIONS = [
  "Top 5 product categories by total sales",
  "Monthly revenue trend in 2025",
  "Average order value by province",
];

export default function AIQeryPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AIResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sqlVisible, setSqlVisible] = useState(true);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");
  const [stage, setStage] = useState(""); // "" | "generating" | "executing"

  const handleSubmit = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    setSqlVisible(true);
    try {
      setStage("generating");
      const res = await api.post("/ai/text-to-sql", { question: question.trim() });
      setResult(res.data);
      setStage("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "AI query failed");
      setStage("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-xl font-bold mb-4">AI Query</h2>
      <p className="text-gray-400 mb-6">Ask questions in natural language — AI generates the SQL for you.</p>

      {/* Input area */}
      <div className="flex gap-3 mb-2">
        <textarea
          className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 resize-none"
          rows={2}
          placeholder="e.g. 'top 5 products by sales last month'"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={loading || !question.trim()}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg self-end font-medium"
        >
          {loading ? "Thinking..." : "Ask AI"}
        </button>
      </div>

      {/* Example prompts — only show in empty state */}
      {!result && !loading && !error && (
        <div className="flex gap-2 mb-6 flex-wrap">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => setQuestion(q)}
              className="px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-full text-gray-400 hover:text-gray-200 hover:border-gray-600"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center gap-3 py-8 text-gray-400">
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          <span>{stage === "generating" ? "Generating SQL..." : "Executing query..."}</span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Results area */}
      {result && (
        <div>
          {/* Generated SQL — collapsible */}
          <div className="mb-4">
            <button
              onClick={() => setSqlVisible(!sqlVisible)}
              className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 mb-2"
            >
              <span className={`transform transition-transform ${sqlVisible ? "rotate-90" : ""}`}>&#9654;</span>
              Generated SQL
            </button>
            {sqlVisible && (
              <pre className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-sm text-gray-300 overflow-x-auto">
                {result.sql}
              </pre>
            )}
          </div>

          {/* Stats bar */}
          <div className="flex justify-between items-center mb-3">
            <p className="text-sm text-gray-400">
              {result.row_count} rows in {result.execution_time_ms}ms
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setViewMode("table")}
                className={`px-3 py-1 rounded text-sm ${viewMode === "table" ? "bg-blue-600" : "bg-gray-700"}`}
              >
                Table
              </button>
              <button
                onClick={() => setViewMode("chart")}
                className={`px-3 py-1 rounded text-sm ${viewMode === "chart" ? "bg-blue-600" : "bg-gray-700"}`}
              >
                Chart
              </button>
            </div>
          </div>

          {/* Data display */}
          {viewMode === "table" ? (
            <DataTable columns={result.columns} rows={result.rows} />
          ) : (
            <ChartView columns={result.columns} rows={result.rows} />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the file has no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors related to AIQeryPage.tsx

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AIQeryPage.tsx
git commit -m "feat: add AI Query page with natural language input"
```

---

### Task 5: Wire Frontend — Routes & Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Add AI Query route to App.tsx**

In `frontend/src/App.tsx`, add the import:
```tsx
import AIQeryPage from "./pages/AIQeryPage";
```

And add the route inside the Layout route group, before the closing `</Route>`:
```tsx
<Route path="/ai-query" element={<AIQeryPage />} />
```

Full file after changes:
```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DatasourcePage from "./pages/DatasourcePage";
import DatasetPage from "./pages/DatasetPage";
import QueryPage from "./pages/QueryPage";
import AIQeryPage from "./pages/AIQeryPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route path="/datasources" element={<DatasourcePage />} />
          <Route path="/datasets" element={<DatasetPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/ai-query" element={<AIQeryPage />} />
          <Route path="/" element={<QueryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Add nav link to Layout.tsx**

In `frontend/src/components/Layout.tsx`, add before the "Query" link:
```tsx
<Link to="/ai-query" className="px-3 py-2 rounded hover:bg-gray-800">AI Query</Link>
```

Full `<nav>` after change:
```tsx
<nav className="flex flex-col gap-2 flex-1">
  <Link to="/datasources" className="px-3 py-2 rounded hover:bg-gray-800">Data Sources</Link>
  <Link to="/datasets" className="px-3 py-2 rounded hover:bg-gray-800">Datasets</Link>
  <Link to="/query" className="px-3 py-2 rounded hover:bg-gray-800">Query</Link>
  <Link to="/ai-query" className="px-3 py-2 rounded hover:bg-gray-800">AI Query</Link>
</nav>
```

- [ ] **Step 3: Verify the build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat: add AI Query route and navigation link"
```

---

### Task 6: End-to-End Verification

- [ ] **Step 1: Update .env with DeepSeek config**

Verify `.env` contains:
```
LLM_API_KEY=sk-a7f7fbbb88034c73afe81b40282b9ba3
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-pro
```

If not, update with Edit.

- [ ] **Step 2: Restart all services**

Run:
```bash
docker compose -p abd-platform down
docker compose -p abd-platform up -d --build
```
Expected: 5 services healthy

- [ ] **Step 3: Verify seed data is available**

Run: `docker exec abd-platform-fastapi-1 python //scripts/register_dataset.py`
Expected: "Dataset 'ecommerce_orders' registered successfully" (or "already exists")

- [ ] **Step 4: Test Text-to-SQL end-to-end with real LLM**

```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@abd.com","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Test a natural language query
curl -s -X POST http://localhost:8000/api/v1/ai/text-to-sql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"what are the top 3 product categories by total revenue"}' | python -m json.tool
```

Expected: Returns JSON with `sql`, `columns`, `rows`, `row_count`, `execution_time_ms`. The `rows` should contain 3 entries sorted by revenue descending.

- [ ] **Step 5: Test more queries**

```bash
# Query 2: Monthly trend
curl -s ... -d '{"question":"monthly sales trend in 2025"}'

# Query 3: Province ranking
curl -s ... -d '{"question":"rank provinces by total orders"}'

# Query 4: Filter + aggregate
curl -s ... -d '{"question":"total revenue of electronics category in 2024"}'
```

Expected: All return valid SQL and correct results.

- [ ] **Step 6: Verify frontend**

Open `http://localhost:5173/ai-query`, type a question, click "Ask AI".
Expected: Generated SQL appears, results display in table, chart toggle works, SQL block collapses/expands.

- [ ] **Step 7: Commit any final adjustments**

```bash
git add -A
git commit -m "feat: complete Phase 2A Text-to-SQL end-to-end integration"
```
