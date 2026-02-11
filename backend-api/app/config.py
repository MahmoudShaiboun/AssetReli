from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    SERVICE_NAME: str = "backend-api"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # MongoDB
    MONGODB_URL: str = "mongodb://mongodb:27017"
    MONGODB_DB: str = "aastreli"
    
    # Services
    ML_SERVICE_URL: str = "http://ml-service:8001"
    MQTT_SERVICE_URL: str = "http://mqtt-ingestion:8002"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://frontend:3000"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()
