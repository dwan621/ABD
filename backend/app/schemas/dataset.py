from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    table_name: str
    source_id: UUID | None = None


class DatasetRead(BaseModel):
    id: UUID
    name: str
    table_name: str
    iceberg_path: str
    schema_json: list
    row_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    sql: str
    dataset_id: str | None = None


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    execution_time_ms: float
