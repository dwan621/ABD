from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LineageEdgeRead(BaseModel):
    id: UUID
    source_dataset_id: UUID
    source_column: str
    target_dataset_id: UUID
    target_column: str
    transform_expr: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LineageResponse(BaseModel):
    dataset_id: UUID
    table_name: str
    upstream: list[LineageEdgeRead]
    downstream: list[LineageEdgeRead]


class LineageCreate(BaseModel):
    source_dataset_id: UUID
    source_column: str
    target_column: str
    transform_expr: str | None = None
