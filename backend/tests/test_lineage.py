import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.dataset import Dataset
from app.models.lineage import LineageEdge
from tests.conftest import TestSession


# ── GET /lineage/{dataset_id} ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_lineage_empty(client: AsyncClient, auth_headers: dict):
    """GET lineage for a dataset with no edges returns empty upstream/downstream."""
    resp = await client.post("/api/v1/datasets/", json={
        "name": "Lineage Empty",
        "table_name": f"lineage_empty_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    dataset_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/lineage/{dataset_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == dataset_id
    assert body["upstream"] == []
    assert body["downstream"] == []


@pytest.mark.asyncio
async def test_get_lineage_populated(client: AsyncClient, auth_headers: dict):
    """GET lineage for a dataset with edges returns both lists."""
    # Create two datasets
    resp_a = await client.post("/api/v1/datasets/", json={
        "name": "Lineage Source",
        "table_name": f"lineage_src_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_a.status_code == 201
    source_id = uuid.UUID(resp_a.json()["id"])

    resp_b = await client.post("/api/v1/datasets/", json={
        "name": "Lineage Target",
        "table_name": f"lineage_tgt_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_b.status_code == 201
    target_id = uuid.UUID(resp_b.json()["id"])

    # Seed edges: A → B (upstream for B) and B → A (downstream for B)
    async with TestSession() as db:
        edge_up = LineageEdge(
            source_dataset_id=source_id,
            source_column="col_a",
            target_dataset_id=target_id,
            target_column="col_b",
            transform_expr="UPPER(col_a)",
        )
        edge_down = LineageEdge(
            source_dataset_id=target_id,
            source_column="col_x",
            target_dataset_id=source_id,
            target_column="col_y",
            transform_expr=None,
        )
        db.add_all([edge_up, edge_down])
        await db.commit()

    # Check lineage for B
    resp = await client.get(f"/api/v1/lineage/{target_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == str(target_id)
    assert len(body["upstream"]) == 1
    assert body["upstream"][0]["source_column"] == "col_a"
    assert body["upstream"][0]["transform_expr"] == "UPPER(col_a)"
    assert len(body["downstream"]) == 1
    assert body["downstream"][0]["source_column"] == "col_x"
    assert body["downstream"][0]["transform_expr"] is None


@pytest.mark.asyncio
async def test_get_upstream(client: AsyncClient, auth_headers: dict):
    """GET upstream returns only upstream edges."""
    # Create two datasets
    resp_a = await client.post("/api/v1/datasets/", json={
        "name": "Upstream Source",
        "table_name": f"up_src_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_a.status_code == 201
    source_id = uuid.UUID(resp_a.json()["id"])

    resp_b = await client.post("/api/v1/datasets/", json={
        "name": "Upstream Target",
        "table_name": f"up_tgt_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_b.status_code == 201
    target_id = uuid.UUID(resp_b.json()["id"])

    # Seed edge: A → B (upstream for B)
    async with TestSession() as db:
        edge = LineageEdge(
            source_dataset_id=source_id,
            source_column="input_col",
            target_dataset_id=target_id,
            target_column="output_col",
            transform_expr="input_col * 2",
        )
        db.add(edge)
        await db.commit()

    resp = await client.get(f"/api/v1/lineage/{target_id}/upstream", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["source_dataset_id"] == str(source_id)
    assert body[0]["target_dataset_id"] == str(target_id)
    assert body[0]["source_column"] == "input_col"
    assert body[0]["target_column"] == "output_col"
    assert body[0]["transform_expr"] == "input_col * 2"


@pytest.mark.asyncio
async def test_get_downstream(client: AsyncClient, auth_headers: dict):
    """GET downstream returns only downstream edges."""
    # Create two datasets
    resp_a = await client.post("/api/v1/datasets/", json={
        "name": "Downstream Source",
        "table_name": f"down_src_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_a.status_code == 201
    source_id = uuid.UUID(resp_a.json()["id"])

    resp_b = await client.post("/api/v1/datasets/", json={
        "name": "Downstream Target",
        "table_name": f"down_tgt_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_b.status_code == 201
    target_id = uuid.UUID(resp_b.json()["id"])

    # Seed edge: A → B (downstream for A)
    async with TestSession() as db:
        edge = LineageEdge(
            source_dataset_id=source_id,
            source_column="src_col",
            target_dataset_id=target_id,
            target_column="tgt_col",
            transform_expr=None,
        )
        db.add(edge)
        await db.commit()

    resp = await client.get(f"/api/v1/lineage/{source_id}/downstream", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["source_dataset_id"] == str(source_id)
    assert body[0]["target_dataset_id"] == str(target_id)
    assert body[0]["source_column"] == "src_col"
    assert body[0]["target_column"] == "tgt_col"


@pytest.mark.asyncio
async def test_create_lineage_success(client: AsyncClient, auth_headers: dict):
    """POST lineage edges creates edges and returns 201."""
    # Create a source dataset and a target dataset
    resp_src = await client.post("/api/v1/datasets/", json={
        "name": "Create Source",
        "table_name": f"create_src_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_src.status_code == 201
    source_id = resp_src.json()["id"]

    resp_tgt = await client.post("/api/v1/datasets/", json={
        "name": "Create Target",
        "table_name": f"create_tgt_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp_tgt.status_code == 201
    target_id = resp_tgt.json()["id"]

    # POST edges: source → target
    resp = await client.post(f"/api/v1/lineage/{target_id}", json=[
        {
            "source_dataset_id": source_id,
            "source_column": "amount",
            "target_column": "total_amount",
            "transform_expr": "amount * 1.1",
        },
    ], headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert len(body) == 1
    assert body[0]["source_dataset_id"] == source_id
    assert body[0]["target_dataset_id"] == target_id
    assert body[0]["source_column"] == "amount"
    assert body[0]["target_column"] == "total_amount"
    assert body[0]["transform_expr"] == "amount * 1.1"
    assert "id" in body[0]


@pytest.mark.asyncio
async def test_get_lineage_404(client: AsyncClient, auth_headers: dict):
    """GET lineage for a non-existent dataset returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/lineage/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_lineage_401(client: AsyncClient):
    """GET lineage without auth returns 401."""
    resp = await client.get(f"/api/v1/lineage/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_lineage_404(client: AsyncClient, auth_headers: dict):
    """POST lineage edges to a non-existent dataset returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/v1/lineage/{fake_id}", json=[
        {
            "source_dataset_id": str(uuid.uuid4()),
            "source_column": "col",
            "target_column": "other_col",
        },
    ], headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
