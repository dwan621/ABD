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
            assert "missing required fields" in str(e).lower()


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


def test_insight_item_model():
    from app.api.ai import InsightItem

    item = InsightItem(title="Test", description="Desc", type="summary", sql="SELECT 1")
    assert item.title == "Test"
    assert item.type == "summary"
    assert item.sql == "SELECT 1"
    assert item.result is None


def test_insight_item_model_with_result():
    from app.api.ai import InsightItem

    result_data = {"columns": ["a"], "rows": [[1]], "row_count": 1, "execution_time_ms": 10.0}
    item = InsightItem(title="Test", description="Desc", type="trend", sql=None, result=result_data)
    assert item.result["columns"] == ["a"]
    assert item.result["row_count"] == 1


def test_insights_response_model():
    from app.api.ai import InsightItem, InsightsResponse

    insights = [
        InsightItem(title="Test", description="Desc", type="summary", sql=None),
    ]
    resp = InsightsResponse(
        dataset_id="uuid-1",
        table_name="test_table",
        row_count=100,
        insights=insights,
    )
    assert resp.dataset_id == "uuid-1"
    assert len(resp.insights) == 1
    assert resp.row_count == 100
