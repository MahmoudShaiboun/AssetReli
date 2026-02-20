from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ModelInfo(BaseModel):
    version: str
    created_at: Optional[datetime] = None
    num_classes: int = 0
    metrics: Optional[Dict[str, float]] = None
    training_samples: Optional[int] = None
    feedback_samples: Optional[int] = None
    is_active: bool = False


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    model_version: Optional[str] = None
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

    model_config = {"protected_namespaces": ()}
