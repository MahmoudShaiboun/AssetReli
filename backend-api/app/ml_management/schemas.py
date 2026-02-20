from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MLModelOut(BaseModel):
    id: UUID
    model_name: str
    model_type: str
    framework: str = "xgboost"
    description: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class MLModelVersionOut(BaseModel):
    id: UUID
    version: str
    stage: str
    accuracy: Optional[float] = None
    f1_score: Optional[float] = None
    training_date: datetime

    model_config = {"from_attributes": True}


class DeploymentOut(BaseModel):
    id: UUID
    model_name: str
    version_label: str
    is_production: bool
    deployed_at: datetime
    deployed_by: str

    model_config = {"from_attributes": True}


class FeedbackStatsOut(BaseModel):
    total_count: int
    breakdown: dict[str, int]


class RetrainRequest(BaseModel):
    selected_data_ids: Optional[list[str]] = None
    async_mode: bool = True
