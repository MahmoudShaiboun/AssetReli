from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class FeedbackType(str, Enum):
    CORRECT = "correct"
    CORRECTION = "correction"
    NEW_FAULT = "new_fault"
    FALSE_POSITIVE = "false_positive"


class FeedbackRequest(BaseModel):
    features: List[float] = Field(..., min_length=1)
    original_prediction: str
    corrected_label: str
    feedback_type: FeedbackType
    confidence: Optional[float] = None
    notes: Optional[str] = None
    tenant_id: Optional[str] = None
    asset_id: Optional[str] = None
    sensor_id: Optional[str] = None
    prediction_id: Optional[str] = None
    model_version_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    success: bool
    feedback_id: str
    message: str
    total_feedback: int
    ready_for_retraining: bool
