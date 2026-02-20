from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class RetrainRequest(BaseModel):
    selected_data_ids: Optional[List[str]] = Field(
        None, description="Specific feedback IDs to use"
    )
    async_mode: bool = Field(False, description="Run retraining in background")
    tenant_id: Optional[str] = Field(None, description="Tenant to retrain for")
    model_id: Optional[str] = Field(None, description="Model to retrain")
    hyperparameters: Optional[Dict[str, Any]] = Field(
        None, description="Override hyperparameters"
    )


class RetrainResponse(BaseModel):
    success: bool
    message: str
    new_version: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    feedback_count: int
    async_mode: bool = False
