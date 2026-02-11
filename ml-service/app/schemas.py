from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class FeedbackType(str, Enum):
    """Types of feedback"""
    CORRECT = "correct"
    CORRECTION = "correction"
    NEW_FAULT = "new_fault"
    FALSE_POSITIVE = "false_positive"


class PredictionRequest(BaseModel):
    """Request for fault prediction - accepts structured sensor data"""
    # Optional features array for backward compatibility
    features: Optional[List[float]] = Field(None, description="Feature vector for prediction (336 features)")
    
    # Structured sensor data fields
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
    
    top_k: Optional[int] = Field(3, description="Number of top predictions to return", ge=1, le=10)
    request_id: Optional[str] = Field(None, description="Optional request identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-12-31 19:14:00",
                "motor_DE_vib_band_1": 1.214455883,
                "motor_DE_vib_band_2": 1.000316203,
                "motor_DE_vib_band_3": 0.951707565,
                "motor_DE_vib_band_4": 0.633685833,
                "motor_DE_ultra_db": 34.27373445,
                "motor_DE_temp_c": 44.82613797,
                "motor_NDE_vib_band_1": 1.303139892,
                "motor_NDE_vib_band_2": 1.049893763,
                "motor_NDE_vib_band_3": 0.852789328,
                "motor_NDE_vib_band_4": 0.612093125,
                "motor_NDE_ultra_db": 33.98650489,
                "motor_NDE_temp_c": 44.93635378,
                "pump_DE_vib_band_1": 1.245676051,
                "pump_DE_vib_band_2": 1.065547248,
                "pump_DE_vib_band_3": 1.177302897,
                "pump_DE_vib_band_4": 0.955404368,
                "pump_DE_ultra_db": 43.93242271,
                "pump_DE_temp_c": 42.10419328,
                "pump_NDE_vib_band_1": 1.167457931,
                "pump_NDE_vib_band_2": 1.034660082,
                "pump_NDE_vib_band_3": 1.080542864,
                "pump_NDE_vib_band_4": 0.903014606,
                "pump_NDE_ultra_db": 43.10568606,
                "pump_NDE_temp_c": 42.03743536,
                "top_k": 3
            }
        }


class TopPrediction(BaseModel):
    """Single prediction in top-K results"""
    label: str = Field(..., description="Fault label")
    confidence: float = Field(..., description="Confidence score", ge=0.0, le=1.0)


class PredictionResponse(BaseModel):
    """Response from fault prediction"""
    prediction: str = Field(..., description="Predicted fault label")
    confidence: float = Field(..., description="Confidence score", ge=0.0, le=1.0)
    top_predictions: List[TopPrediction] = Field(..., description="Top-K predictions with confidence")
    model_version: str = Field(..., description="Model version used for prediction")
    timestamp: datetime = Field(..., description="Prediction timestamp")
    request_id: Optional[str] = Field(None, description="Request identifier")
    
    model_config = {
        "protected_namespaces": (),
        "json_schema_extra": {
            "example": {
                "prediction": "bearing_overgrease_churning",
                "confidence": 0.857,
                "top_predictions": [
                    {"label": "bearing_overgrease_churning", "confidence": 0.857},
                    {"label": "bearing_fit_loose_housing", "confidence": 0.092},
                    {"label": "normal", "confidence": 0.031}
                ],
                "model_version": "v1",
                "timestamp": "2026-01-30T10:00:05Z",
                "request_id": "pred_123"
            }
        }
    }


class FeedbackRequest(BaseModel):
    """Request to submit feedback"""
    features: List[float] = Field(..., description="Original feature vector", min_length=1)
    original_prediction: str = Field(..., description="Model's original prediction")
    corrected_label: str = Field(..., description="Correct fault label")
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    confidence: Optional[float] = Field(None, description="Original confidence score")
    notes: Optional[str] = Field(None, description="Additional notes")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "features": [1.25, 1.08, 0.85] + [1.0] * 333,
                "original_prediction": "bearing_fit_loose_housing",
                "corrected_label": "bearing_overgrease_churning",
                "feedback_type": "correction",
                "confidence": 0.78,
                "notes": "Grease indicators were elevated",
                "metadata": {"user_id": "operator_42", "sensor_id": "pump_01"}
            }
        }


class FeedbackResponse(BaseModel):
    """Response after submitting feedback"""
    success: bool = Field(..., description="Whether feedback was stored successfully")
    feedback_id: str = Field(..., description="Unique feedback identifier")
    message: str = Field(..., description="Response message")
    total_feedback: int = Field(..., description="Total feedback count")
    ready_for_retraining: bool = Field(..., description="Whether enough feedback for retraining")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "feedback_id": "fb_20260130_001",
                "message": "Feedback stored. Total: 15",
                "total_feedback": 15,
                "ready_for_retraining": True
            }
        }


class RetrainRequest(BaseModel):
    """Request to trigger model retraining"""
    selected_data_ids: Optional[List[str]] = Field(None, description="Specific feedback IDs to use")
    async_mode: bool = Field(False, description="Run retraining in background")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Override hyperparameters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "selected_data_ids": None,
                "async_mode": False,
                "hyperparameters": {"max_depth": 7, "learning_rate": 0.1}
            }
        }


class RetrainResponse(BaseModel):
    """Response after retraining request"""
    success: bool = Field(..., description="Whether retraining succeeded")
    message: str = Field(..., description="Response message")
    new_version: Optional[str] = Field(None, description="New model version")
    metrics: Optional[Dict[str, float]] = Field(None, description="Performance metrics")
    feedback_count: int = Field(..., description="Feedback samples used")
    async_mode: bool = Field(..., description="Whether running in background")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Model retrained successfully",
                "new_version": "v2",
                "metrics": {
                    "accuracy": 0.9385,
                    "balanced_accuracy": 0.8821,
                    "f1_score": 0.9289
                },
                "feedback_count": 15,
                "async_mode": False
            }
        }


class ModelInfo(BaseModel):
    """Information about a model version"""
    version: str = Field(..., description="Model version identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    num_classes: int = Field(..., description="Number of fault classes")
    metrics: Optional[Dict[str, float]] = Field(None, description="Performance metrics")
    training_samples: Optional[int] = Field(None, description="Training samples used")
    feedback_samples: Optional[int] = Field(None, description="Feedback samples used")
    is_active: bool = Field(..., description="Whether this is the active model")
    
    class Config:
        json_schema_extra = {
            "example": {
                "version": "v2",
                "created_at": "2026-01-30T15:30:00Z",
                "num_classes": 36,
                "metrics": {
                    "accuracy": 0.9385,
                    "balanced_accuracy": 0.8821,
                    "f1_score": 0.9289
                },
                "training_samples": 11519,
                "feedback_samples": 15,
                "is_active": True
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    model_version: Optional[str] = Field(None, description="Current model version")
    timestamp: datetime = Field(..., description="Response timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    
    model_config = {
        "protected_namespaces": (),
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "service": "ml-service",
                "version": "1.0.0",
                "model_version": "v1",
                "timestamp": "2026-01-30T10:00:00Z",
                "details": {
                    "model_loaded": True,
                    "num_classes": 34,
                    "feedback_count": 15
                }
            }
        }
    }
