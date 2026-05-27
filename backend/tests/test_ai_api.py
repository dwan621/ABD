# backend/tests/test_ai_api.py
import pytest


def test_text_to_sql_request_model():
    """Verify the request model validates correctly."""
    from app.api.ai import TextToSQLRequest

    # Valid request
    req = TextToSQLRequest(question="top 5 products by sales")
    assert req.question == "top 5 products by sales"

    # Empty question is allowed at model level (route handles validation)
    req = TextToSQLRequest(question="")
    assert req.question == ""


def test_router_exists():
    """Verify the ai router is importable and has correct prefix."""
    from app.api.ai import router

    assert router.prefix == "/ai"
    assert "ai" in router.tags
