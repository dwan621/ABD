import json
import logging

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

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

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


def build_schema_context(datasets: list[dict]) -> str:
    """Format registered dataset schemas into a prompt-friendly string."""
    if not datasets:
        return "(no tables available)"
    parts = []
    for ds in datasets:
        cols = []
        for col in ds.get("schema_json", []):
            cols.append(f"  {col.get('name', '?')}: {col.get('type', '?')}")
        col_str = "\n".join(cols)
        parts.append(f"Table: {ds.get('table_name', '?')}\nColumns:\n{col_str}")
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
    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty or null content")

    sql = content.strip()

    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        sql = "\n".join(lines).strip()

    if sql.upper() == "UNABLE_TO_GENERATE":
        raise ValueError("Cannot generate SQL for this question with the available tables")

    sql_stripped_upper = sql.lstrip().upper()
    if not (sql_stripped_upper.startswith("SELECT") or sql_stripped_upper.startswith("WITH")):
        raise ValueError(f"LLM generated invalid SQL: {sql}")

    return sql


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
        max_tokens=3000,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty or null content")

    content = content.strip()

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


_CHAT_PROMPT = """\
You are a helpful data analyst assistant. You can answer questions about the user's data using natural language or by generating SQL queries.

Available tables:
{schema_context}

Recent conversation history:
{history}

If the user's question can be answered with a SQL query, respond with a JSON object:
{{"answer": "your explanation of what you're about to do", "sql": "SELECT ..."}}

If the question does NOT need SQL (e.g., asking about capabilities, clarifying, general discussion, follow-up on previous results), respond with:
{{"answer": "your response", "sql": null}}

Rules:
- Only SELECT statements in SQL — no DDL, DML, or DCL
- Use the exact table and column names from the schema
- Keep answers concise and conversational (2-4 sentences in Chinese or English matching the user's language)
- Reference information from conversation history when relevant
- Use Spark SQL syntax for date functions and aggregations
- Return ONLY the JSON object, no markdown, no explanations

Example when SQL is needed:
{{"answer": "Let me find the top 5 products by sales for you.", "sql": "SELECT product_name, SUM(total_amount) AS revenue FROM ecommerce_orders GROUP BY product_name ORDER BY revenue DESC LIMIT 5"}}

Example when no SQL is needed:
{{"answer": "I can help you analyze your ecommerce data. I have access to order records with details like product categories, payment methods, customer locations, and more. What would you like to know?"}}"""


def generate_chat_response(question: str, schema_context: str, history: list[dict]) -> dict:
    """Generate a conversational response, optionally with SQL."""
    client = _get_client()
    history_str = json.dumps(history[-10:], ensure_ascii=False) if history else "[]"
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

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse chat response JSON: {content[:500]}")
        raise ValueError(f"Failed to parse chat response as JSON: {e}")

    if "answer" not in parsed:
        raise ValueError("Chat response missing 'answer' field")

    return {"answer": parsed["answer"], "sql": parsed.get("sql")}
