from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class PredictionRequest(BaseModel):
    features: Optional[List[float]] = Field(
        None, description="Feature vector for prediction (336 features)"
    )

    timestamp: Optional[str] = Field(None, description="Timestamp of reading")
    motor_DE_vib_band_1: Optional[float] = None
    motor_DE_vib_band_2: Optional[float] = None
    motor_DE_vib_band_3: Optional[float] = None
    motor_DE_vib_band_4: Optional[float] = None
    motor_DE_ultra_db: Optional[float] = None
    motor_DE_temp_c: Optional[float] = None
    motor_NDE_vib_band_1: Optional[float] = None
    motor_NDE_vib_band_2: Optional[float] = None
    motor_NDE_vib_band_3: Optional[float] = None
    motor_NDE_vib_band_4: Optional[float] = None
    motor_NDE_ultra_db: Optional[float] = None
    motor_NDE_temp_c: Optional[float] = None
    pump_DE_vib_band_1: Optional[float] = None
    pump_DE_vib_band_2: Optional[float] = None
    pump_DE_vib_band_3: Optional[float] = None
    pump_DE_vib_band_4: Optional[float] = None
    pump_DE_ultra_db: Optional[float] = None
    pump_DE_temp_c: Optional[float] = None
    pump_NDE_vib_band_1: Optional[float] = None
    pump_NDE_vib_band_2: Optional[float] = None
    pump_NDE_vib_band_3: Optional[float] = None
    pump_NDE_vib_band_4: Optional[float] = None
    pump_NDE_ultra_db: Optional[float] = None
    pump_NDE_temp_c: Optional[float] = None

    # Multi-tenancy fields (Phase 3)
    tenant_id: Optional[str] = None
    asset_id: Optional[str] = None
    model_version_id: Optional[str] = None

    top_k: Optional[int] = Field(3, ge=1, le=10)
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TopPrediction(BaseModel):
    label: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    prediction: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    top_predictions: List[TopPrediction]
    model_version: str
    model_version_id: Optional[str] = None
    timestamp: datetime
    request_id: Optional[str] = None

    model_config = {"protected_namespaces": ()}
