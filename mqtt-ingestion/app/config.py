from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    SERVICE_NAME: str = "mqtt-ingestion"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    
    # MQTT
    MQTT_BROKER_HOST: str = "mqtt-broker"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPICS: List[str] = ["sensors/#", "equipment/#", "+/+/sensors/#"]
    
    # MongoDB
    MONGODB_URL: str = "http://localhost:27017"
    MONGODB_DB: str = "aastreli"

    # PostgreSQL (read-only for sensor registry + model bindings)
    POSTGRES_URL: str = "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5431/aastreli"

    # JWT (shared with backend-api for WebSocket auth)
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production-use-env-variable"

    @property
    def POSTGRES_DSN(self) -> str:
        """asyncpg-compatible DSN (strips the +asyncpg scheme)."""
        # return self.POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")
        return self.POSTGRES_URL

    # Services
    BACKEND_API_URL: str = "http://localhost:8008"
    INTERNAL_API_KEY: str = "dev_key"
    ML_SERVICE_URL: str = "http://localhost:8001"

    # API key for ML service calls
    ML_API_KEY: str = "dev_key"

    # Alert threshold (replaces hardcoded 0.6)
    ALERT_CONFIDENCE_THRESHOLD: float = 0.6
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8008",
        "http://frontend:3000"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()
