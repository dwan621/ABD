import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.anomaly import Anomaly
from app.models.column import Column
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.anomaly import AnomalyDetectResponse, AnomalyRead
from app.services.anomaly_service import detect_anomalies, run_isolation_forest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["anomalies"])


@router.get("/datasets/{dataset_id}/anomalies", response_model=list[AnomalyRead])
async def get_anomalies(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    anomalies_result = await db.execute(
        select(Anomaly)
        .where(Anomaly.dataset_id == dataset_id)
        .order_by(
            case(
                (Anomaly.severity == "high", 1),
                (Anomaly.severity == "medium", 2),
                (Anomaly.severity == "low", 3),
                else_=4,
            ),
            Anomaly.detected_at.desc(),
        )
    )
    return [AnomalyRead.model_validate(a) for a in anomalies_result.scalars().all()]


@router.post("/datasets/{dataset_id}/anomalies/detect", response_model=AnomalyDetectResponse)
async def detect_anomalies_endpoint(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    columns_result = await db.execute(
        select(Column).where(Column.dataset_id == dataset_id)
    )
    columns = columns_result.scalars().all()

    schema_json = [
        {"name": col.col_name, "type": col.data_type}
        for col in columns
    ]

    try:
        anomalies_raw = detect_anomalies(ds.table_name, schema_json)
        numeric_cols = [
            c["name"] for c in schema_json
            if c["type"] in ("double", "float", "int", "bigint", "decimal", "integer")
        ]
        if_anomalies = run_isolation_forest(ds.table_name, numeric_cols)
        anomalies_raw.extend(if_anomalies)
    except Exception as e:
        logger.exception(f"Anomaly detection failed for dataset {dataset_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {e}",
        )

    # Delete existing anomalies for this dataset
    existing = await db.execute(
        select(Anomaly).where(Anomaly.dataset_id == dataset_id)
    )
    for a in existing.scalars().all():
        await db.delete(a)

    created = []
    for a in anomalies_raw:
        anomaly = Anomaly(
            dataset_id=dataset_id,
            column_name=a["column_name"],
            anomaly_type=a["anomaly_type"],
            severity=a["severity"],
            detected_value=a.get("detected_value"),
            expected_range=a.get("expected_range"),
            ai_explanation=a.get("ai_explanation"),
        )
        db.add(anomaly)
        created.append(anomaly)

    await db.commit()
    for a in created:
        await db.refresh(a)

    high_count = sum(1 for a in created if a.severity == "high")
    medium_count = sum(1 for a in created if a.severity == "medium")
    low_count = sum(1 for a in created if a.severity == "low")

    return AnomalyDetectResponse(
        dataset_id=dataset_id,
        total_anomalies=len(created),
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        anomalies=[AnomalyRead.model_validate(a) for a in created],
    )
