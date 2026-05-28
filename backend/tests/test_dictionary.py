import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.column import Column
from app.models.dataset import Dataset
from tests.conftest import TestSession


# ── GET /datasets/{dataset_id}/dictionary ─────────────────────────────────

@pytest.mark.asyncio
async def test_get_dictionary_success(client: AsyncClient, auth_headers: dict):
    """GET dictionary returns dataset metadata + column list."""
    # Create a dataset via API
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Dict Test",
        "table_name": f"dict_test_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    # Seed columns directly in the test DB
    async with TestSession() as db:
        for name, dtype in [("id", "bigint"), ("name", "string"), ("amount", "double")]:
            db.add(Column(
                dataset_id=uuid.UUID(dataset_id),
                col_name=name,
                data_type=dtype,
            ))
        await db.commit()

    # GET the dictionary
    resp = await client.get(f"/api/v1/datasets/{dataset_id}/dictionary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == dataset_id
    assert body["table_name"] == resp.json()["table_name"]
    assert len(body["columns"]) == 3
    col_names = [c["col_name"] for c in body["columns"]]
    assert col_names == ["amount", "id", "name"]  # alphabetical order


@pytest.mark.asyncio
async def test_get_dictionary_dataset_not_found(client: AsyncClient, auth_headers: dict):
    """GET dictionary for a non-existent dataset returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/datasets/{fake_id}/dictionary", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_dictionary_empty_columns(client: AsyncClient, auth_headers: dict):
    """GET dictionary for a dataset with no columns returns empty list."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Empty Cols",
        "table_name": f"empty_cols_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/datasets/{dataset_id}/dictionary", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == dataset_id
    assert body["columns"] == []


@pytest.mark.asyncio
async def test_get_dictionary_unauthorized(client: AsyncClient):
    """GET dictionary without auth returns 401."""
    resp = await client.get(f"/api/v1/datasets/{uuid.uuid4()}/dictionary")
    assert resp.status_code == 401


# ── PATCH /columns/{column_id} ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_column_success(client: AsyncClient, auth_headers: dict):
    """PATCH column updates both ai_description and tags."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Update Col Test",
        "table_name": f"update_col_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = uuid.UUID(resp.json()["id"])

    async with TestSession() as db:
        col = Column(
            dataset_id=dataset_id,
            col_name="price",
            data_type="double",
            ai_description="Old desc",
            tags=["old"],
        )
        db.add(col)
        await db.commit()
        await db.refresh(col)
        col_id = str(col.id)

    resp = await client.patch(f"/api/v1/columns/{col_id}", json={
        "ai_description": "Updated price description",
        "tags": ["metric", "revenue"],
    }, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_description"] == "Updated price description"
    assert body["tags"] == ["metric", "revenue"]


@pytest.mark.asyncio
async def test_update_column_partial(client: AsyncClient, auth_headers: dict):
    """PATCH column with only tags leaves ai_description unchanged."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Partial Update",
        "table_name": f"partial_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = uuid.UUID(resp.json()["id"])

    async with TestSession() as db:
        col = Column(
            dataset_id=dataset_id,
            col_name="category",
            data_type="string",
            ai_description="Original description",
            tags=["old"],
        )
        db.add(col)
        await db.commit()
        await db.refresh(col)
        col_id = str(col.id)

    resp = await client.patch(f"/api/v1/columns/{col_id}", json={
        "tags": ["categorical", "dimension"],
    }, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_description"] == "Original description"  # unchanged
    assert body["tags"] == ["categorical", "dimension"]


@pytest.mark.asyncio
async def test_update_column_not_found(client: AsyncClient, auth_headers: dict):
    """PATCH non-existent column returns 404."""
    resp = await client.patch(f"/api/v1/columns/{uuid.uuid4()}", json={
        "ai_description": "nope",
    }, headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_column_unauthorized(client: AsyncClient):
    """PATCH column without auth returns 401."""
    resp = await client.patch(f"/api/v1/columns/{uuid.uuid4()}", json={
        "ai_description": "nope",
    })
    assert resp.status_code == 401


# ── POST /datasets/{dataset_id}/dictionary/regenerate ─────────────────────

@pytest.mark.asyncio
async def test_regenerate_success(client: AsyncClient, auth_headers: dict):
    """POST regenerate triggers LLM and persists column descriptions."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Regen Test",
        "table_name": f"regen_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    # Update the dataset's schema_json so build_schema_context works
    async with TestSession() as db:
        ds = await db.get(Dataset, uuid.UUID(dataset_id))
        ds.schema_json = [
            {"name": "id", "type": "bigint"},
            {"name": "name", "type": "string"},
        ]
        await db.commit()

    mock_sample = {"columns": ["id", "name"], "rows": [[1, "Alice"], [2, "Bob"]]}
    mock_descriptions = [
        {"col_name": "id", "description": "Unique identifier", "tags": ["id", "primary"]},
        {"col_name": "name", "description": "Customer name", "tags": ["text", "customer"]},
    ]

    with patch("app.api.dataset.execute_sql", return_value=mock_sample), \
         patch("app.api.dataset.generate_column_descriptions", return_value=mock_descriptions):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/dictionary/regenerate",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == dataset_id
    assert len(body["columns"]) == 2
    col_names = {c["col_name"] for c in body["columns"]}
    assert col_names == {"id", "name"}

    # Verify columns persisted in DB
    async with TestSession() as db:
        from sqlalchemy import select
        cols = (await db.execute(
            select(Column).where(Column.dataset_id == uuid.UUID(dataset_id))
        )).scalars().all()
        assert len(cols) == 2


@pytest.mark.asyncio
async def test_regenerate_sample_fails(client: AsyncClient, auth_headers: dict):
    """POST regenerate with Spark error returns 400."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Spark Fail",
        "table_name": f"spark_fail_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    with patch("app.api.dataset.execute_sql", side_effect=RuntimeError("Spark cluster unreachable")):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/dictionary/regenerate",
            headers=auth_headers,
        )

    assert resp.status_code == 400
    assert "Spark cluster unreachable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_regenerate_llm_fails(client: AsyncClient, auth_headers: dict):
    """POST regenerate with LLM error returns 502."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "LLM Fail",
        "table_name": f"llm_fail_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    async with TestSession() as db:
        ds = await db.get(Dataset, uuid.UUID(dataset_id))
        ds.schema_json = [{"name": "x", "type": "int"}]
        await db.commit()

    mock_sample = {"columns": ["x"], "rows": [[1]]}

    with patch("app.api.dataset.execute_sql", return_value=mock_sample), \
         patch("app.api.dataset.generate_column_descriptions", side_effect=RuntimeError("API timeout")):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/dictionary/regenerate",
            headers=auth_headers,
        )

    assert resp.status_code == 502
    assert "LLM service unavailable" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_regenerate_llm_value_error(client: AsyncClient, auth_headers: dict):
    """POST regenerate with ValueError from LLM returns 400."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "LLM ValueError",
        "table_name": f"llm_valerr_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    async with TestSession() as db:
        ds = await db.get(Dataset, uuid.UUID(dataset_id))
        ds.schema_json = [{"name": "x", "type": "int"}]
        await db.commit()

    mock_sample = {"columns": ["x"], "rows": [[1]]}

    with patch("app.api.dataset.execute_sql", return_value=mock_sample), \
         patch("app.api.dataset.generate_column_descriptions", side_effect=ValueError("empty content")):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/dictionary/regenerate",
            headers=auth_headers,
        )

    assert resp.status_code == 400
    assert "empty content" in resp.json()["detail"]


# ── generate_column_descriptions unit tests ──────────────────────────────

def test_generate_column_descriptions_returns_parsed_list():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps([
            {"col_name": "id", "description": "Primary key", "tags": ["id", "key"]},
            {"col_name": "name", "description": "User name", "tags": ["text"]},
        ])))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import generate_column_descriptions
        result = generate_column_descriptions("users", "id: bigint\nname: string", "sample")

    assert len(result) == 2
    assert result[0]["col_name"] == "id"
    assert result[0]["description"] == "Primary key"
    assert result[0]["tags"] == ["id", "key"]


def test_generate_column_descriptions_strips_markdown_fence():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='```json\n[{"col_name": "id", "description": "PK", "tags": ["key"]}]\n```'))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import generate_column_descriptions
        result = generate_column_descriptions("t", "c", "s")

    assert len(result) == 1
    assert result[0]["col_name"] == "id"


def test_generate_column_descriptions_null_content_raises():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=None))]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import generate_column_descriptions
        try:
            generate_column_descriptions("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "empty" in str(e).lower()


def test_generate_column_descriptions_invalid_json_raises():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="not json at all just some text"))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import generate_column_descriptions
        try:
            generate_column_descriptions("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "parse" in str(e).lower()


def test_generate_column_descriptions_validates_required_fields():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps([
            {"col_name": "id"}   # missing description + tags
        ])))
    ]

    with patch("app.services.llm_service._get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        from app.services.llm_service import generate_column_descriptions
        try:
            generate_column_descriptions("t", "c", "s")
            assert False, "should have raised"
        except ValueError as e:
            assert "missing required fields" in str(e).lower()
