import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.column import Column
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.column import ColumnRead, ColumnUpdate, DictionaryResponse
from app.schemas.dataset import DatasetCreate, DatasetRead
from app.services.llm_service import build_schema_context, format_sample_data, generate_column_descriptions
from app.services.spark_bridge import execute_sql

router = APIRouter(prefix="/datasets", tags=["datasets"])

logger = logging.getLogger(__name__)


@router.get("/", response_model=list[DatasetRead])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.created_by == current_user.id).order_by(Dataset.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iceberg_path = f"s3a://{settings.minio_bucket}/{body.table_name}"

    dataset = Dataset(
        name=body.name,
        table_name=body.table_name,
        iceberg_path=iceberg_path,
        source_id=body.source_id,
        created_by=current_user.id,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(
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
    return ds


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
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
    await db.delete(ds)
    await db.commit()


@router.get("/{dataset_id}/dictionary", response_model=DictionaryResponse)
async def get_dictionary(
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

    col_result = await db.execute(
        select(Column).where(Column.dataset_id == dataset_id).order_by(Column.col_name)
    )
    columns = col_result.scalars().all()

    return DictionaryResponse(
        dataset_id=ds.id,
        table_name=ds.table_name,
        row_count=ds.row_count,
        columns=[ColumnRead.model_validate(c) for c in columns],
    )


@router.post("/{dataset_id}/dictionary/regenerate", response_model=DictionaryResponse)
async def regenerate_dictionary(
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

    schema_context = build_schema_context([{
        "table_name": ds.table_name,
        "schema_json": ds.schema_json,
    }])

    try:
        sample_result = execute_sql(f"SELECT * FROM {ds.table_name} LIMIT 20")
    except Exception as e:
        logger.error(f"Failed to sample data from {ds.table_name}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to sample data: {e}")

    sample_data = format_sample_data(sample_result["columns"], sample_result["rows"])

    try:
        descriptions = generate_column_descriptions(ds.table_name, schema_context, sample_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"LLM service error during dictionary generation: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    schema_map = {col["name"]: col["type"] for col in ds.schema_json}

    for desc in descriptions:
        col_name = desc["col_name"]
        data_type = schema_map.get(col_name, "unknown")
        existing = await db.execute(
            select(Column).where(Column.dataset_id == dataset_id, Column.col_name == col_name)
        )
        col = existing.scalar_one_or_none()
        if col:
            col.ai_description = desc["description"]
            col.tags = desc["tags"]
            col.data_type = data_type
        else:
            col = Column(
                dataset_id=dataset_id,
                col_name=col_name,
                data_type=data_type,
                ai_description=desc["description"],
                tags=desc["tags"],
            )
            db.add(col)

    await db.commit()

    col_result = await db.execute(
        select(Column).where(Column.dataset_id == dataset_id).order_by(Column.col_name)
    )
    columns = col_result.scalars().all()

    return DictionaryResponse(
        dataset_id=ds.id,
        table_name=ds.table_name,
        row_count=ds.row_count,
        columns=[ColumnRead.model_validate(c) for c in columns],
    )
