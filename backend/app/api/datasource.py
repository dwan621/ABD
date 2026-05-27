from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.datasource import Datasource
from app.models.user import User
from app.schemas.datasource import DatasourceCreate, DatasourceRead

router = APIRouter(prefix="/datasources", tags=["datasources"])


@router.get("/", response_model=list[DatasourceRead])
async def list_datasources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Datasource).where(Datasource.created_by == current_user.id).order_by(Datasource.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=DatasourceRead, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    body: DatasourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    datasource = Datasource(
        name=body.name,
        type=body.type,
        config_json=body.config_json,
        created_by=current_user.id,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)
    return datasource


@router.get("/{datasource_id}", response_model=DatasourceRead)
async def get_datasource(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Datasource).where(Datasource.id == datasource_id, Datasource.created_by == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Datasource not found")
    return ds


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Datasource).where(Datasource.id == datasource_id, Datasource.created_by == current_user.id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Datasource not found")
    await db.delete(ds)
    await db.commit()
