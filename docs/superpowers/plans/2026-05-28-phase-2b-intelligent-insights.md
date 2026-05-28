# Phase 2B — Intelligent Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-click AI-powered dataset analysis — LLM generates statistical summaries, trends, anomaly detection, and rankings with verification SQL, backend executes the SQL, and frontend displays insights as cards with charts.

**Architecture:** Extend `llm_service.py` with a `generate_insights()` function that sends schema + sample data to DeepSeek and parses structured JSON. Add `POST /ai/insights/{dataset_id}` endpoint that samples data via Spark, calls LLM for insights, executes each insight's verification SQL, and returns insights with data attached. New `InsightsPage.tsx` displays insight cards with type badges, descriptions, and chart/table toggles per insight.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind/ECharts (frontend), DeepSeek v4-pro (LLM), PySpark (data sampling & verification queries), OpenAI Python client.

---

### Task 1: Add `generate_insights()` to LLM Service

**Files:**
- Modify: `backend/app/services/llm_service.py` (append after `generate_sql`)
- Create: `backend/tests/test_insights.py`

- [ ] **Step 1: Write the failing tests for generate_insights**

Create `backend/tests/test_insights.py`:

```python
import json
from unittest.mock import MagicMock, patch

from app.services.llm_service import generate_insights, format_sample_data


def test_format_sample_data_empty():
    result = format_sample_data([], [])
    assert result == "(no sample data available)"


def test_format_sample_data_with_rows():
    columns = ["id", "name", "price"]
    rows = [[1, "Widget", 9.99], [2, "Gadget", 19.99]]
    result = format_sample_data(columns, rows)
    assert "id | name | price" in result
    assert "1 | Widget | 9.99" in result
    assert "2 | Gadget | 19.99" in result


def test_generate_insights_returns_parsed_list():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps([
            {"title": "Test Insight", "description": "A test", "type": "summary", "sql": None}
        ])))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = generate_insights("ecommerce_orders", "col: type", "sample data here")

    assert len(result) == 1
    assert result[0]["title"] == "Test Insight"
    assert result[0]["type"] == "summary"


def test_generate_insights_strips_markdown_fence():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='```json\n[{"title": "X", "description": "Y", "type": "trend", "sql": "SELECT 1"}]\n```'))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = generate_insights("t", "c", "s")

    assert len(result) == 1
    assert result[0]["title"] == "X"


def test_generate_insights_null_content_raises():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=None))]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        try:
            generate_insights("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "empty" in str(e).lower()


def test_generate_insights_invalid_json_raises():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="not json at all just some text"))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        try:
            generate_insights("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "parse" in str(e).lower()


def test_generate_insights_validates_required_fields():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps([
            {"title": "Missing fields"}
        ])))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        try:
            generate_insights("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "title, description, type" in str(e).lower()


def test_generate_insights_validates_type_enum():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps([
            {"title": "X", "description": "Y", "type": "invalid_type", "sql": None}
        ])))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        try:
            generate_insights("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "type" in str(e).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml run --rm fastapi pytest tests/test_insights.py -v`
Expected: FAIL — all tests fail with "function not defined" / "name 'generate_insights' is not defined"

- [ ] **Step 3: Implement `generate_insights()` and `format_sample_data()`**

Append to `backend/app/services/llm_service.py`:

```python
import json
import logging

logger = logging.getLogger(__name__)

_INSIGHTS_PROMPT = """\
You are a senior data analyst. Given a table schema and sample rows, generate analytical insights about the data. Return ONLY a valid JSON array of insight objects — no markdown, no explanations, no surrounding text.

Table name: {table_name}

Schema:
{schema_context}

Sample rows (first 20):
{sample_data}

Each insight object must have exactly these fields:
- "title": a short, human-readable title (max 80 chars)
- "description": 2-4 sentences describing what the data shows and why it matters
- "type": one of "summary", "trend", "ranking", "anomaly"
- "sql": a valid Spark SQL SELECT query that produces the data supporting this insight, or null if the insight is purely descriptive

Insight type definitions:
- "summary": overall statistics — counts, aggregates, date ranges, data quality notes
- "trend": time-based patterns — growth, decline, seasonality (only if date columns exist)
- "ranking": top/bottom N by a metric — categories, products, segments
- "anomaly": outliers, unusual values, unexpected patterns in the sample

Rules:
1. Generate 4-6 insights covering at least 3 different types
2. Every insight must reference actual columns from the schema
3. SQL queries must use the EXACT table name provided above
4. Only SELECT statements in SQL — no DDL, DML, or DCL
5. Use Spark SQL syntax — date functions like DATE_TRUNC(), aggregation with GROUP BY
6. Return ONLY the JSON array — no markdown fences, no explanation text

Example response format:
[{{"title": "Monthly Revenue Trend", "description": "Revenue shows consistent month-over-month growth averaging 12%. The strongest month was November 2025 driven by holiday shopping.", "type": "trend", "sql": "SELECT DATE_TRUNC('MM', order_date) AS month, SUM(total_amount) AS revenue FROM ecommerce_orders GROUP BY DATE_TRUNC('MM', order_date) ORDER BY month"}}, {{"title": "Top 5 Product Categories", "description": "Electronics leads with 35% of total sales, followed by Home & Kitchen at 22%. These two categories account for over half of all revenue.", "type": "ranking", "sql": "SELECT category, SUM(total_amount) AS total_sales, COUNT(*) AS order_count FROM ecommerce_orders GROUP BY category ORDER BY total_sales DESC LIMIT 5"}}]"""

VALID_INSIGHT_TYPES = {"summary", "trend", "ranking", "anomaly"}
REQUIRED_FIELDS = {"title", "description", "type"}


def format_sample_data(columns: list[str], rows: list[list]) -> str:
    """Format Spark query results into a readable text table for the LLM prompt."""
    if not columns or not rows:
        return "(no sample data available)"

    lines = [" | ".join(columns), "-" * (len(" | ".join(columns)))]
    for row in rows:
        lines.append(" | ".join(str(cell) if cell is not None else "NULL" for cell in row))
    return "\n".join(lines)


def generate_insights(table_name: str, schema_context: str, sample_data: str) -> list[dict]:
    """Call LLM to generate analytical insights from schema and sample data."""
    client = _get_client()
    prompt = _INSIGHTS_PROMPT.format(
        table_name=table_name,
        schema_context=schema_context,
        sample_data=sample_data,
    )

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "You are a senior data analyst. Return ONLY valid JSON. No markdown, no explanations."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty or null content")

    content = content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        content = "\n".join(lines).strip()

    try:
        insights = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM insights JSON: {content[:500]}")
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    if not isinstance(insights, list):
        raise ValueError("LLM response is not a JSON array")

    for item in insights:
        missing = REQUIRED_FIELDS - set(item.keys())
        if missing:
            raise ValueError(f"Insight missing required fields: {missing}")
        if item.get("type") not in VALID_INSIGHT_TYPES:
            raise ValueError(f"Invalid insight type: {item.get('type')}. Must be one of {VALID_INSIGHT_TYPES}")

    return insights
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose -f docker/docker-compose.yml run --rm fastapi pytest tests/test_insights.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm_service.py backend/tests/test_insights.py
git commit -m "feat: add generate_insights() to LLM service for Phase 2B"
```

---

### Task 2: Add Insights API Endpoint

**Files:**
- Modify: `backend/app/api/ai.py` (append new endpoint + models)
- Modify: `backend/tests/test_insights.py` (append API tests)

- [ ] **Step 1: Write failing API test**

Append to `backend/tests/test_insights.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def insights_payload():
    return [
        {"title": "Sales Trend", "description": "Sales growing.", "type": "trend", "sql": "SELECT 1"},
        {"title": "Top Categories", "description": "Top 3 cats.", "type": "ranking", "sql": None},
    ]


@pytest.mark.asyncio
async def test_insights_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/ai/insights/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_insights_endpoint_dataset_not_found(insights_payload):
    # mock auth + db
    with patch("app.api.ai.get_current_user") as mock_auth, \
         patch("app.api.ai.get_db") as mock_db, \
         patch("app.api.ai.AsyncSession") as mock_session_class:
        mock_auth.return_value = MagicMock()
        mock_db_result = AsyncMock()
        mock_db_result.scalar_one_or_none.return_value = None
        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_db_result
        mock_db.return_value.__aenter__.return_value = mock_session

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/ai/insights/00000000-0000-0000-0000-000000000001")

    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose -f docker/docker-compose.yml run --rm fastapi pytest tests/test_insights.py::test_insights_endpoint_requires_auth tests/test_insights.py::test_insights_endpoint_dataset_not_found -v`
Expected: FAIL — 404/422 (endpoint not defined yet)

- [ ] **Step 3: Implement the insights endpoint**

Append to `backend/app/api/ai.py`:

```python
from uuid import UUID

from app.api.deps import get_current_user
from app.api.query import validate_sql
from app.core.database import get_db
from app.models.dataset import Dataset
from app.models.user import User
from app.services.llm_service import build_schema_context, format_sample_data, generate_insights
from app.services.spark_bridge import execute_sql


class InsightItem(BaseModel):
    title: str
    description: str
    type: str
    sql: str | None = None
    result: dict | None = None


class InsightsResponse(BaseModel):
    dataset_id: str
    table_name: str
    row_count: int
    insights: list[InsightItem]


@router.post("/insights/{dataset_id}", response_model=InsightsResponse)
async def generate_dataset_insights(
    dataset_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch dataset
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Format schema context
    schema_context = build_schema_context([{
        "table_name": ds.table_name,
        "schema_json": ds.schema_json,
    }])

    # Sample data via Spark
    try:
        sample_result = execute_sql(f"SELECT * FROM {ds.table_name} LIMIT 20")
    except Exception as e:
        logger.error(f"Failed to sample data from {ds.table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to sample data: {e}")

    sample_data = format_sample_data(sample_result["columns"], sample_result["rows"])

    # Generate insights via LLM
    try:
        raw_insights = generate_insights(ds.table_name, schema_context, sample_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM service error during insight generation: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    # Build insight items and execute verification SQLs
    insights = []
    for raw in raw_insights:
        item = InsightItem(
            title=raw["title"],
            description=raw["description"],
            type=raw["type"],
            sql=raw.get("sql"),
        )
        if item.sql:
            try:
                validate_sql(item.sql)
                query_result = execute_sql(item.sql)
                item.result = {
                    "columns": query_result["columns"],
                    "rows": query_result["rows"],
                    "row_count": query_result["row_count"],
                    "execution_time_ms": query_result["execution_time_ms"],
                }
            except Exception as e:
                logger.warning(f"Verification SQL failed for insight '{item.title}': {e}")
                item.result = {"error": str(e)}
        insights.append(item)

    return InsightsResponse(
        dataset_id=str(dataset_id),
        table_name=ds.table_name,
        row_count=ds.row_count or sample_result.get("row_count", 0),
        insights=insights,
    )
```

- [ ] **Step 4: Run tests to verify API tests pass**

Run: `docker compose -f docker/docker-compose.yml run --rm fastapi pytest tests/test_insights.py -v`
Expected: All tests PASS (8 llm_service tests + 2 API tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/ai.py backend/tests/test_insights.py
git commit -m "feat: add POST /ai/insights/{dataset_id} endpoint for Phase 2B"
```

---

### Task 3: Create Frontend InsightsPage

**Files:**
- Create: `frontend/src/pages/InsightsPage.tsx`

- [ ] **Step 1: Create InsightsPage component**

Create `frontend/src/pages/InsightsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import api from "../api/client";
import DataTable from "../components/DataTable";
import ChartView from "../components/ChartView";

interface DatasetInfo {
  id: string;
  name: string;
  table_name: string;
  row_count: number;
  schema_json: { name: string; type: string }[];
}

interface InsightResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
  error?: string;
}

interface Insight {
  title: string;
  description: string;
  type: string;
  sql: string | null;
  result: InsightResult | null;
}

interface InsightsData {
  dataset_id: string;
  table_name: string;
  row_count: number;
  insights: Insight[];
}

const TYPE_COLORS: Record<string, string> = {
  summary: "bg-blue-900/40 text-blue-300 border-blue-800",
  trend: "bg-green-900/40 text-green-300 border-green-800",
  ranking: "bg-purple-900/40 text-purple-300 border-purple-800",
  anomaly: "bg-orange-900/40 text-orange-300 border-orange-800",
};

const TYPE_EMOJI: Record<string, string> = {
  summary: "📊",
  trend: "📈",
  ranking: "🏆",
  anomaly: "⚠️",
};

export default function InsightsPage() {
  const { id } = useParams<{ id: string }>();
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [data, setData] = useState<InsightsData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [datasetLoading, setDatasetLoading] = useState(true);
  const [expandedInsight, setExpandedInsight] = useState<number | null>(null);
  const [viewModes, setViewModes] = useState<Record<number, "table" | "chart">>({});

  useEffect(() => {
    api
      .get(`/datasets/${id}`)
      .then((res) => setDataset(res.data))
      .catch(() => setError("Failed to load dataset"))
      .finally(() => setDatasetLoading(false));
  }, [id]);

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setData(null);
    try {
      const res = await api.post(`/ai/insights/${id}`);
      setData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to generate insights");
    } finally {
      setLoading(false);
    }
  };

  if (datasetLoading) {
    return (
      <div className="flex items-center gap-3 py-8 text-gray-400">
        <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        Loading dataset...
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3">
        <p className="text-red-400">{error || "Dataset not found"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold">{dataset.name}</h2>
          <p className="text-sm text-gray-400 mt-1">
            Table: {dataset.table_name} | {dataset.row_count.toLocaleString()} rows |{" "}
            {dataset.schema_json?.length || 0} columns
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:opacity-50 rounded-lg font-medium text-sm flex items-center gap-2"
        >
          {loading ? (
            <>
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              Analyzing...
            </>
          ) : data ? (
            "Regenerate Insights"
          ) : (
            "Generate Insights"
          )}
        </button>
      </div>

      {/* Empty state */}
      {!data && !loading && !error && (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-xl">
          <p className="text-5xl mb-4">🔍</p>
          <p className="text-gray-400 mb-2">Click "Generate Insights" to analyze this dataset with AI</p>
          <p className="text-sm text-gray-500">The AI will examine schema and sample data to produce trends, rankings, and anomaly detection</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex flex-col items-center gap-4 py-16">
          <div className="animate-spin h-8 w-8 border-3 border-blue-500 border-t-transparent rounded-full" />
          <p className="text-gray-400">AI is analyzing {dataset.table_name}...</p>
          <p className="text-sm text-gray-500">This may take 10-20 seconds</p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg px-4 py-3 mb-4">
          <p className="text-red-400 text-sm">{error}</p>
          <p className="text-red-500 text-xs mt-1">You can try again — the input is preserved</p>
        </div>
      )}

      {/* Insights cards */}
      {data && (
        <div className="space-y-4">
          {data.insights.map((insight, idx) => (
            <div key={idx} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              {/* Card header */}
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{TYPE_EMOJI[insight.type] || "💡"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <h3 className="font-semibold text-gray-100">{insight.title}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs border ${TYPE_COLORS[insight.type]}`}>
                        {insight.type}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 leading-relaxed">{insight.description}</p>
                  </div>
                </div>

                {/* SQL toggle + data */}
                {insight.sql && (
                  <div className="mt-3 ml-9">
                    <button
                      onClick={() => {
                        setExpandedInsight(expandedInsight === idx ? null : idx);
                        if (!(idx in viewModes)) {
                          setViewModes((prev) => ({ ...prev, [idx]: "table" }));
                        }
                      }}
                      className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300"
                    >
                      <span className={`transform transition-transform ${expandedInsight === idx ? "rotate-90" : ""}`}>
                        &#9654;
                      </span>
                      Show Query & Data
                    </button>

                    {expandedInsight === idx && insight.result && (
                      <div className="mt-2 space-y-3">
                        <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-gray-300 overflow-x-auto">
                          {insight.sql}
                        </pre>

                        {insight.result.error ? (
                          <p className="text-red-400 text-sm">Query failed: {insight.result.error}</p>
                        ) : (
                          <>
                            <div className="flex items-center justify-between">
                              <p className="text-xs text-gray-500">
                                {insight.result.row_count} rows in {insight.result.execution_time_ms}ms
                              </p>
                              <div className="flex gap-1">
                                <button
                                  onClick={() => setViewModes((prev) => ({ ...prev, [idx]: "table" }))}
                                  className={`px-2 py-0.5 rounded text-xs ${viewModes[idx] === "table" ? "bg-blue-600" : "bg-gray-700"}`}
                                >
                                  Table
                                </button>
                                <button
                                  onClick={() => setViewModes((prev) => ({ ...prev, [idx]: "chart" }))}
                                  className={`px-2 py-0.5 rounded text-xs ${viewModes[idx] === "chart" ? "bg-blue-600" : "bg-gray-700"}`}
                                >
                                  Chart
                                </button>
                              </div>
                            </div>

                            {viewModes[idx] === "table" ? (
                              <DataTable columns={insight.result.columns} rows={insight.result.rows} />
                            ) : (
                              <ChartView columns={insight.result.columns} rows={insight.result.rows} />
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `docker compose -f docker/docker-compose.yml run --rm -w /app/frontend -u root fastapi npx tsc --noEmit --strict false 2>&1 | head -20`
Expected: No errors related to InsightsPage (pre-existing errors in other files may exist)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/InsightsPage.tsx
git commit -m "feat: add InsightsPage with AI-powered dataset analysis UI"
```

---

### Task 4: Wire Up Routes and Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/DatasetPage.tsx`

- [ ] **Step 1: Add route in App.tsx**

Replace the imports section and add the InsightsPage route.

In `frontend/src/App.tsx`, add the import line:

```tsx
import InsightsPage from "./pages/InsightsPage";
```

And add the route inside `<Route element={<Layout />}>`:

```tsx
<Route path="/datasets/:id/insights" element={<InsightsPage />} />
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
import InsightsPage from "./pages/InsightsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Layout />}>
          <Route path="/datasources" element={<DatasourcePage />} />
          <Route path="/datasets" element={<DatasetPage />} />
          <Route path="/datasets/:id/insights" element={<InsightsPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/ai-query" element={<AIQeryPage />} />
          <Route path="/" element={<QueryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Add Insights button to DatasetPage**

In `frontend/src/pages/DatasetPage.tsx`, add `useNavigate` import and modify each dataset card to include an "Insights" button:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

interface Dataset {
  id: string;
  name: string;
  table_name: string;
  row_count: number;
  created_at: string;
}

export default function DatasetPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/datasets/").then((res) => setDatasets(res.data));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Datasets</h2>
      <div className="space-y-2">
        {datasets.map((ds) => (
          <div key={ds.id} className="bg-gray-900 p-4 rounded border border-gray-800 flex items-center justify-between">
            <div>
              <p className="font-medium">{ds.name}</p>
              <p className="text-sm text-gray-400">
                Table: {ds.table_name} | Rows: {ds.row_count.toLocaleString()} |{" "}
                {new Date(ds.created_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={() => navigate(`/datasets/${ds.id}/insights`)}
              className="px-4 py-1.5 text-sm bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-lg"
            >
              Insights
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify frontend compiles**

Run: `docker compose -f docker/docker-compose.yml run --rm -w /app/frontend -u root fastapi npx tsc --noEmit --strict false 2>&1 | head -20`
Expected: No new TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/DatasetPage.tsx
git commit -m "feat: wire up insights route and navigation for Phase 2B"
```

---

### Task 5: E2E Verification

- [ ] **Step 1: Verify backend endpoint responds correctly**

First check services are up:

```bash
docker compose -f docker/docker-compose.yml ps
```

Run a test request against the insights endpoint (get a dataset ID from the database first, then test):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
DATASET_ID=$(curl -s http://localhost:8000/api/v1/datasets/ -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST "http://localhost:8000/api/v1/ai/insights/$DATASET_ID" -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Dataset: {data[\"table_name\"]} ({data[\"row_count\"]} rows)')
print(f'Insights: {len(data[\"insights\"])}')
for i, ins in enumerate(data['insights']):
    has_data = ins.get('result') and 'rows' in (ins['result'] or {})
    print(f'  {i+1}. [{ins[\"type\"]}] {ins[\"title\"]} - SQL: {ins[\"sql\"] is not None}, Data: {has_data}')
"
```

Expected: Returns insights array with 4-6 items, each with title/description/type, most with SQL + result data.

- [ ] **Step 2: Verify frontend loads and renders**

Navigate to `http://localhost:5173/datasets` and confirm:
- Each dataset card shows an "Insights" button
- Clicking it navigates to `/datasets/:id/insights`
- The page shows dataset info (name, table, row count, column count)
- Clicking "Generate Insights" triggers the AI pipeline
- Loading spinner shows during generation
- Insights render as cards with type badges
- Expanding "Show Query & Data" shows SQL + table/chart toggle

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: E2E verification fixes for Phase 2B"
```
