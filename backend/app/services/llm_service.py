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
