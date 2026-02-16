from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta
import httpx
from typing import Optional, List

from config import settings
from database import get_database
from auth import (
    User, UserCreate, UserInDB, Token,
    get_password_hash, verify_password, create_access_token, verify_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Backend API...")
    try:
        app.mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        # Test the connection
        await app.mongodb_client.admin.command("ping")
        app.mongodb = app.mongodb_client[settings.MONGODB_DB]
        logger.info("✅ Connected to MongoDB")
    except Exception as e:
        logger.warning(f"⚠️ MongoDB not available: {e}")
        app.mongodb_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        app.mongodb = app.mongodb_client[settings.MONGODB_DB]
    logger.info("✅ Backend API ready!")
    yield
    app.mongodb_client.close()
    logger.info("👋 Backend API stopped")

app = FastAPI(
    title="Aastreli Backend API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "backend-api",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db=Depends(get_database)
) -> User:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    token_data = verify_token(token)
    
    if token_data is None or token_data.email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_doc = await db.users.find_one({"email": token_data.email})
    if user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return User(**user_doc)


@app.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(user_create: UserCreate, db=Depends(get_database)):
    """Register a new user"""
    # Check if user already exists
    existing_user = await db.users.find_one({"$or": [
        {"email": user_create.email},
        {"username": user_create.username}
    ]})
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    user_dict = {
        "email": user_create.email,
        "username": user_create.username,
        "full_name": user_create.full_name,
        "hashed_password": get_password_hash(user_create.password),
        "disabled": False,
        "created_at": datetime.utcnow()
    }
    
    await db.users.insert_one(user_dict)
    logger.info(f"✅ New user registered: {user_create.email}")
    
    # Return user without password
    return User(**user_dict)


@app.post("/login", response_model=Token)
async def login(email: str, password: str, db=Depends(get_database)):
    """Login and get JWT token"""
    user_doc = await db.users.find_one({"email": email})
    
    if not user_doc or not verify_password(password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user_doc.get("disabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_doc["email"]},
        expires_delta=access_token_expires
    )
    
    logger.info(f"✅ User logged in: {email}")
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user


# ============================================================================
# SETTINGS ENDPOINTS
# ============================================================================

@app.get("/settings")
async def get_settings(current_user: User = Depends(get_current_user), db=Depends(get_database)):
    """Get user settings from MongoDB"""
    settings_doc = await db.user_settings.find_one({"user_email": current_user.email})
    
    if not settings_doc:
        # Return default settings if none exist
        return {
            "autoRefresh": True,
            "refreshInterval": 5,
            "anomalyThreshold": 0.7,
            "enableNotifications": True,
            "faultActions": []
        }
    
    # Remove MongoDB _id from response
    settings_doc.pop("_id", None)
    settings_doc.pop("user_email", None)
    
    return settings_doc


@app.post("/settings")
async def save_settings(
    settings_data: dict,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database)
):
    """Save user settings to MongoDB"""
    settings_doc = {
        "user_email": current_user.email,
        "autoRefresh": settings_data.get("autoRefresh", True),
        "refreshInterval": settings_data.get("refreshInterval", 5),
        "anomalyThreshold": settings_data.get("anomalyThreshold", 0.7),
        "enableNotifications": settings_data.get("enableNotifications", True),
        "faultActions": settings_data.get("faultActions", []),
        "updated_at": datetime.utcnow()
    }
    
    # Upsert (update or insert)
    await db.user_settings.update_one(
        {"user_email": current_user.email},
        {"$set": settings_doc},
        upsert=True
    )
    
    logger.info(f"✅ Settings saved for user: {current_user.email}")
    return {"status": "success", "message": "Settings saved successfully"}


@app.get("/settings/all-users")
async def get_all_users_settings(db=Depends(get_database)):
    """Get all users' enabled fault actions (for mqtt-ingestion service)"""
    # This endpoint doesn't require auth since it's called by internal services
    # In production, you might want to add service-to-service auth
    
    all_settings = []
    async for settings_doc in db.user_settings.find({"enableNotifications": True}):
        # Only return settings with enabled notifications
        enabled_actions = [
            action for action in settings_doc.get("faultActions", [])
            if action.get("enabled", False)
        ]
        
        if enabled_actions:
            all_settings.append({
                "user_email": settings_doc.get("user_email"),
                "anomalyThreshold": settings_doc.get("anomalyThreshold", 0.7),
                "faultActions": enabled_actions
            })
    
    return {"users_settings": all_settings}

# Sensors endpoints

class SensorCreate(BaseModel):
    sensor_id: str
    name: str
    type: str
    location: Optional[str] = None
    features: Optional[List[str]] = None
    mqtt_topic: Optional[str] = None


@app.post("/sensors", status_code=status.HTTP_201_CREATED)
async def create_sensor(sensor: SensorCreate, db=Depends(get_database)):
    """Register a new sensor"""
    existing = await db.sensors.find_one({"sensor_id": sensor.sensor_id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sensor '{sensor.sensor_id}' already exists"
        )

    mqtt_topic = sensor.mqtt_topic or f"sensors/{sensor.sensor_id}"

    sensor_doc = {
        "sensor_id": sensor.sensor_id,
        "name": sensor.name,
        "type": sensor.type,
        "location": sensor.location,
        "features": sensor.features or [],
        "mqtt_topic": mqtt_topic,
        "status": "active",
        "created_at": datetime.utcnow(),
    }
    await db.sensors.insert_one(sensor_doc)
    sensor_doc["_id"] = str(sensor_doc["_id"])
    logger.info(f"Sensor registered: {sensor.sensor_id} -> {mqtt_topic}")
    return sensor_doc


@app.get("/sensors")
async def get_sensors(db=Depends(get_database)):
    sensors = await db.sensors.find().to_list(100)
    for s in sensors:
        s["_id"] = str(s["_id"])
    return {"sensors": sensors, "count": len(sensors)}

@app.get("/sensor-readings")
async def get_sensor_readings(skip: int = 0, limit: int = 100, sensor_id: str = None, db=Depends(get_database)):
    """Get all sensor readings with pagination and optional filtering"""
    query = {}
    if sensor_id:
        query["sensor_id"] = sensor_id
    
    total = await db.sensor_readings.count_documents(query)
    readings = await db.sensor_readings.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    
    # Convert ObjectId to string
    for reading in readings:
        reading["_id"] = str(reading["_id"])
    
    return {
        "readings": readings,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/sensors/{sensor_id}/data")
async def get_sensor_data(sensor_id: str, limit: int = 100, db=Depends(get_database)):
    data = await db.sensor_data.find(
        {"data.sensor_id": sensor_id}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"sensor_id": sensor_id, "data": data, "count": len(data)}

# Predictions endpoints
@app.get("/predictions")
async def get_predictions(limit: int = 100, db=Depends(get_database)):
    predictions = await db.predictions.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return {"predictions": predictions, "count": len(predictions)}

@app.post("/predictions")
async def create_prediction(features: list[float], db=Depends(get_database)):
    """Create a new prediction by calling ML service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/predict",
                json={"features": features},
                timeout=30.0
            )
            result = response.json()
        
        # Store prediction in database
        prediction_doc = {
            **result,
            "created_at": datetime.utcnow()
        }
        await db.predictions.insert_one(prediction_doc)
        
        return result
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Feedback endpoints
@app.post("/feedback")
async def submit_feedback(
    features: list[float],
    original_prediction: str,
    corrected_label: str,
    feedback_type: str,
    confidence: float = None,
    notes: str = None,
    sensor_id: str = None,
    reading_id: str = None,
    timestamp: str = None,
    db=Depends(get_database)
):
    """Submit feedback and forward to ML service"""
    try:
        # Forward to ML service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/feedback",
                json={
                    "features": features,
                    "original_prediction": original_prediction,
                    "corrected_label": corrected_label,
                    "feedback_type": feedback_type,
                    "confidence": confidence,
                    "notes": notes
                },
                timeout=30.0
            )
            result = response.json()
        
        # Store in database
        feedback_doc = {
            "features": features,
            "original_prediction": original_prediction,
            "corrected_label": corrected_label,
            "feedback_type": feedback_type,
            "confidence": confidence,
            "notes": notes,
            "sensor_id": sensor_id,
            "reading_id": reading_id,
            "timestamp": timestamp,
            "feedback_id": result.get("feedback_id"),
            "created_at": datetime.utcnow()
        }
        await db.feedback.insert_one(feedback_doc)
        
        # Update the sensor reading to mark it has feedback
        if reading_id:
            from bson import ObjectId
            try:
                await db.sensor_readings.update_one(
                    {"_id": ObjectId(reading_id)},
                    {"$set": {"has_feedback": True, "feedback_label": corrected_label}}
                )
            except Exception as e:
                logger.warning(f"Could not update reading: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/retrain")
async def trigger_retrain(selected_data_ids: list[str] = None):
    """Trigger model retraining"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.ML_SERVICE_URL}/retrain",
                json={"selected_data_ids": selected_data_ids, "async_mode": True},
                timeout=60.0
            )
            return response.json()
    except Exception as e:
        logger.error(f"Retrain error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-notification")
async def test_notification(data: dict):
    """Test notification endpoint for fault actions"""
    action_type = data.get("type")
    config = data.get("config", {})
    message = data.get("message", "Test notification")
    
    logger.info(f"📬 Testing {action_type} notification")
    logger.info(f"Config: {config}")
    logger.info(f"Message: {message}")
    
    # Simulate sending notification
    if action_type == "email":
        logger.info(f"📧 Would send email to: {config.get('email')}")
        return {"status": "success", "message": f"Test email notification logged to {config.get('email')}"}
    
    elif action_type == "webhook":
        logger.info(f"🔗 Would send webhook to: {config.get('url')}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.get('url'),
                    json={"message": message, "test": True},
                    timeout=5.0
                )
                return {"status": "success", "message": f"Webhook sent successfully, status: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Webhook failed: {str(e)}"}
    
    elif action_type == "sms":
        logger.info(f"📱 Would send SMS to: {config.get('phone')}")
        return {"status": "success", "message": f"Test SMS notification logged to {config.get('phone')}"}
    
    elif action_type == "slack":
        logger.info(f"💬 Would send Slack message to: {config.get('channel')}")
        return {"status": "success", "message": f"Test Slack notification logged to {config.get('channel')}"}
    
    return {"status": "error", "message": "Unknown notification type"}

@app.get("/dashboard")
async def get_dashboard(db=Depends(get_database)):
    """Get dashboard summary with recent ML predictions"""
    # Count total sensor readings with predictions
    total_predictions = await db.sensor_readings.count_documents({"prediction": {"$exists": True}})
    total_feedback = await db.feedback.count_documents({})
    
    # Get latest 20 sensor readings with predictions for dashboard
    latest_readings = await db.sensor_readings.find(
        {"prediction": {"$exists": True}}
    ).sort("timestamp", -1).limit(20).to_list(20)
    
    # Convert ObjectId to string
    for reading in latest_readings:
        reading["_id"] = str(reading["_id"])
    
    # Count anomalies in latest readings
    anomaly_count = sum(1 for r in latest_readings if r.get("prediction") and r["prediction"].lower() != "normal")
    
    return {
        "total_predictions": total_predictions,
        "total_feedback": total_feedback,
        "latest_readings": latest_readings,
        "recent_anomalies": anomaly_count,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
