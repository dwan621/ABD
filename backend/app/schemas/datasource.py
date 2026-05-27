from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasourceCreate(BaseModel):
    name: str
    type: str
    config_json: dict = {}


class DatasourceRead(BaseModel):
    id: UUID
    name: str
    type: str
    config_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}
