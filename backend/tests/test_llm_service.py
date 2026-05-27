import pytest
from unittest.mock import MagicMock, patch

from app.services.llm_service import build_schema_context


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


@patch("app.services.llm_service._get_client")
def test_generate_sql_null_content_raises(mock_get_client):
    """Response content is None → ValueError."""
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = None
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError, match="empty or null"):
        generate_sql("show all orders", "Table: orders\n  id: bigint")


@patch("app.services.llm_service._get_client")
def test_generate_sql_non_select_raises(mock_get_client):
    """Non-SELECT SQL (e.g. INSERT) → ValueError."""
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "INSERT INTO orders (id) VALUES (1)"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    with pytest.raises(ValueError, match="LLM generated invalid SQL"):
        generate_sql("insert a row", "Table: orders\n  id: bigint")


@patch("app.services.llm_service._get_client")
def test_generate_sql_accepts_cte(mock_get_client):
    from app.services.llm_service import generate_sql

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "WITH top AS (SELECT * FROM orders) SELECT * FROM top"
    mock_client.chat.completions.create.return_value = mock_response
    mock_get_client.return_value = mock_client

    sql = generate_sql("complex query", "Table: orders\n  id: bigint")
    assert sql.startswith("WITH")
