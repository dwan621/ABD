import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.dataset import Dataset
from app.models.lineage import LineageEdge
from app.models.user import User
from app.schemas.lineage import LineageCreate, LineageEdgeRead, LineageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lineage", tags=["lineage"])


@router.get("/{dataset_id}", response_model=LineageResponse)
async def get_lineage(
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

    upstream_result = await db.execute(
        select(LineageEdge).where(LineageEdge.target_dataset_id == dataset_id)
    )
    upstream = [LineageEdgeRead.model_validate(e) for e in upstream_result.scalars().all()]

    downstream_result = await db.execute(
        select(LineageEdge).where(LineageEdge.source_dataset_id == dataset_id)
    )
    downstream = [LineageEdgeRead.model_validate(e) for e in downstream_result.scalars().all()]

    return LineageResponse(
        dataset_id=ds.id,
        table_name=ds.table_name,
        upstream=upstream,
        downstream=downstream,
    )


@router.get("/{dataset_id}/upstream", response_model=list[LineageEdgeRead])
async def get_upstream_lineage(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    edges_result = await db.execute(
        select(LineageEdge).where(LineageEdge.target_dataset_id == dataset_id)
    )
    return [LineageEdgeRead.model_validate(e) for e in edges_result.scalars().all()]


@router.get("/{dataset_id}/downstream", response_model=list[LineageEdgeRead])
async def get_downstream_lineage(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    edges_result = await db.execute(
        select(LineageEdge).where(LineageEdge.source_dataset_id == dataset_id)
    )
    return [LineageEdgeRead.model_validate(e) for e in edges_result.scalars().all()]


@router.post("/{dataset_id}", response_model=list[LineageEdgeRead], status_code=status.HTTP_201_CREATED)
async def create_lineage_edges(
    dataset_id: UUID,
    body: list[LineageCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.created_by == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    created = []
    for edge in body:
        lineage = LineageEdge(
            source_dataset_id=edge.source_dataset_id,
            source_column=edge.source_column,
            target_dataset_id=dataset_id,
            target_column=edge.target_column,
            transform_expr=edge.transform_expr,
        )
        db.add(lineage)
        created.append(lineage)

    await db.commit()
    for edge in created:
        await db.refresh(edge)

    return [LineageEdgeRead.model_validate(e) for e in created]
