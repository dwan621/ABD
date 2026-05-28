from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ColumnRead(BaseModel):
    id: UUID
    col_name: str
    data_type: str
    ai_description: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ColumnUpdate(BaseModel):
    ai_description: str | None = None
    tags: list[str] | None = None


class DictionaryResponse(BaseModel):
    dataset_id: UUID
    table_name: str
    row_count: int
    columns: list[ColumnRead]

    model_config = {"from_attributes": True}
