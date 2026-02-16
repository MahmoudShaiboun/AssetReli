from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    SERVICE_NAME: str = "mqtt-ingestion"
    HOST: str = "0.0.0.0"
    PORT: int = 8002
    
    # MQTT
    MQTT_BROKER_HOST: str = "mqtt-broker"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPICS: List[str] = ["sensors/#", "equipment/#"]
    
    # MongoDB
    MONGODB_URL: str = "http://localhost:27017"
    MONGODB_DB: str = "aastreli"

    # Services
    BACKEND_API_URL: str = "http://localhost:8008"
    ML_SERVICE_URL: str = "http://localhost:8001"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8008",
        "http://frontend:3000"
    ]
    
    class Config:
        env_file = ".env"

settings = Settings()
