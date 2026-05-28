import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.column import Column
from app.models.user import User
from app.schemas.column import ColumnRead, ColumnUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/columns", tags=["columns"])


@router.patch("/{column_id}", response_model=ColumnRead)
async def update_column(
    column_id: UUID,
    body: ColumnUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Column).where(Column.id == column_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")

    if body.ai_description is not None:
        col.ai_description = body.ai_description
    if body.tags is not None:
        col.tags = body.tags

    await db.commit()
    await db.refresh(col)
    return col
