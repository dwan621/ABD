import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.anomaly import Anomaly
from tests.conftest import TestSession


# ── helpers ────────────────────────────────────────────────────────────────────

async def _create_dataset(client: AsyncClient, auth_headers: dict, name: str) -> str:
    resp = await client.post("/api/v1/datasets/", json={
        "name": name,
        "table_name": f"anomaly_test_{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


# ── POST /datasets/{dataset_id}/anomalies/detect ───────────────────────────────

@pytest.mark.asyncio
async def test_detect_success(client: AsyncClient, auth_headers: dict):
    """POST detect runs detection, stores results, returns counts."""
    dataset_id = await _create_dataset(client, auth_headers, "Detect Success")

    mock_anomalies = [
        {"column_name": "amount", "anomaly_type": "statistical", "severity": "high",
         "detected_value": "9999.99", "expected_range": "0.00 – 5000.00", "ai_explanation": None},
        {"column_name": "price", "anomaly_type": "iqr", "severity": "low",
         "detected_value": "-5.00", "expected_range": "10.00 – 100.00", "ai_explanation": None},
        {"column_name": "quantity", "anomaly_type": "isolation_forest", "severity": "medium",
         "detected_value": "100", "expected_range": None, "ai_explanation": None},
    ]

    with (
        patch("app.api.anomaly.detect_anomalies", return_value=mock_anomalies[:2]),
        patch("app.api.anomaly.run_isolation_forest", return_value=mock_anomalies[2:]),
    ):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/anomalies/detect",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"] == dataset_id
    assert body["total_anomalies"] == 3
    assert body["high_count"] == 1
    assert body["medium_count"] == 1
    assert body["low_count"] == 1
    assert len(body["anomalies"]) == 3


@pytest.mark.asyncio
async def test_detect_no_anomalies(client: AsyncClient, auth_headers: dict):
    """POST detect with no anomalies found returns empty result."""
    dataset_id = await _create_dataset(client, auth_headers, "Detect None")

    with (
        patch("app.api.anomaly.detect_anomalies", return_value=[]),
        patch("app.api.anomaly.run_isolation_forest", return_value=[]),
    ):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/anomalies/detect",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_anomalies"] == 0
    assert body["high_count"] == 0
    assert body["anomalies"] == []


@pytest.mark.asyncio
async def test_detect_spark_failure(client: AsyncClient, auth_headers: dict):
    """POST detect handles Spark failure gracefully with 500."""
    dataset_id = await _create_dataset(client, auth_headers, "Detect Fail")

    with patch("app.api.anomaly.detect_anomalies", side_effect=RuntimeError("Spark connection refused")):
        resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/anomalies/detect",
            headers=auth_headers,
        )

    assert resp.status_code == 500
    assert "Spark" in resp.json()["detail"]


# ── GET /datasets/{dataset_id}/anomalies ───────────────────────────────────────

@pytest.mark.asyncio
async def test_get_anomalies_empty(client: AsyncClient, auth_headers: dict):
    """GET anomalies for dataset with no anomalies returns empty list."""
    dataset_id = await _create_dataset(client, auth_headers, "Get Empty")

    resp = await client.get(
        f"/api/v1/datasets/{dataset_id}/anomalies",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_anomalies_populated(client: AsyncClient, auth_headers: dict):
    """GET anomalies returns results ordered by severity."""
    dataset_id = await _create_dataset(client, auth_headers, "Get Populated")

    async with TestSession() as db:
        low = Anomaly(
            dataset_id=uuid.UUID(dataset_id),
            column_name="qty",
            anomaly_type="iqr",
            severity="low",
            detected_value="50",
            expected_range="1 – 30",
        )
        high = Anomaly(
            dataset_id=uuid.UUID(dataset_id),
            column_name="price",
            anomaly_type="statistical",
            severity="high",
            detected_value="99999",
            expected_range="0 – 5000",
            ai_explanation="Extreme outlier, 20x above mean",
        )
        medium = Anomaly(
            dataset_id=uuid.UUID(dataset_id),
            column_name="amount",
            anomaly_type="isolation_forest",
            severity="medium",
            detected_value="500",
            expected_range=None,
        )
        db.add_all([low, high, medium])
        await db.commit()

    resp = await client.get(
        f"/api/v1/datasets/{dataset_id}/anomalies",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    # ordered by severity desc (high > medium > low)
    assert body[0]["severity"] == "high"
    assert body[1]["severity"] == "medium"
    assert body[2]["severity"] == "low"
    assert body[0]["ai_explanation"] == "Extreme outlier, 20x above mean"


@pytest.mark.asyncio
async def test_get_anomalies_404(client: AsyncClient, auth_headers: dict):
    """GET anomalies for non-existent dataset returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/datasets/{fake_id}/anomalies",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_anomalies_401(client: AsyncClient):
    """GET anomalies without auth returns 401."""
    resp = await client.get(f"/api/v1/datasets/{uuid.uuid4()}/anomalies")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_detect_404(client: AsyncClient, auth_headers: dict):
    """POST detect to non-existent dataset returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/datasets/{fake_id}/anomalies/detect",
        headers=auth_headers,
    )
    assert resp.status_code == 404
