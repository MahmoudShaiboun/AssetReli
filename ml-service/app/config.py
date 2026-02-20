from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """ML Service configuration"""
    
    # Service
    SERVICE_NAME: str = "ml-service"
    SERVICE_VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Model paths
    MODEL_DIR: str = "/app/models"
    CURRENT_MODEL_DIR: str = "/app/models/current"
    FEEDBACK_DIR: str = "/app/feedback_data"
    
    # Retraining
    MIN_FEEDBACK_FOR_RETRAIN: int = 10
    AUTO_RETRAIN_ENABLED: bool = False
    AUTO_RETRAIN_THRESHOLD: int = 50
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:3000"
    ]
    
    # PostgreSQL
    POSTGRES_URL: str = "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5432/aastreli"

    # MongoDB
    MONGODB_URL: str = "mongodb://mongodb:27017"
    MONGODB_DB: str = "aastreli"

    # API key for inbound request authentication (legacy)
    API_KEY: str = "dev_key"

    # Internal service-to-service API key
    INTERNAL_API_KEY: str = ""

    # Artifact storage
    ARTIFACT_STORE_TYPE: str = "local"  # "local" or "s3" (future)
    ARTIFACT_STORE_PATH: str = "/app/models"
    MAX_LOADED_MODELS: int = 10

    # Retraining enhancements
    INCLUDE_ORIGINAL_DATA_ON_RETRAIN: bool = True
    FEEDBACK_WEIGHT_MULTIPLIER: float = 3.0
    
    # XGBoost parameters
    XGBOOST_MAX_DEPTH: int = 8
    XGBOOST_LEARNING_RATE: float = 0.1
    XGBOOST_N_ESTIMATORS: int = 300
    XGBOOST_SUBSAMPLE: float = 0.8
    XGBOOST_COLSAMPLE_BYTREE: float = 0.8
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
