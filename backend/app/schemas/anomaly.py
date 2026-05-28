from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnomalyRead(BaseModel):
    id: UUID
    dataset_id: UUID
    column_name: str
    anomaly_type: str
    severity: str
    detected_value: str | None
    expected_range: str | None
    ai_explanation: str | None
    detected_at: datetime

    model_config = {"from_attributes": True}


class AnomalyDetectResponse(BaseModel):
    dataset_id: UUID
    total_anomalies: int
    high_count: int
    medium_count: int
    low_count: int
    anomalies: list[AnomalyRead]
