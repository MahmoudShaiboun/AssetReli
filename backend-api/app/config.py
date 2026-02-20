from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Resolve to repo root .env (backend-api/app/config.py -> ../../.env)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    SERVICE_NAME: str = "backend-api"
    HOST: str = "0.0.0.0"
    PORT: int = 8008

    # PostgreSQL
    POSTGRES_URL: str = "postgresql+asyncpg://aastreli:aastreli_dev@localhost:5431/aastreli"

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "aastreli"

    # Services
    ML_SERVICE_URL: str = "http://localhost:8001"
    MQTT_SERVICE_URL: str = "http://localhost:8002"

    # Service-to-service auth (mqtt-ingestion → backend-api)
    INTERNAL_API_KEY: str = "dev_key"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8008"
    ]

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"

settings = Settings()
