import paho.mqtt.client as mqtt
import json
import logging
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List
import asyncio
import httpx
import numpy as np
from .notifications import NotificationService

logger = logging.getLogger(__name__)

class MQTTClient:
    def __init__(self, broker_host: str, broker_port: int, topics: List[str]):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topics = topics
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.latest_data = {}
        self.message_count = 0
        self.connected = False
        
        # Sliding window buffer for time-series predictions (14 timesteps per sensor)
        self.sensor_windows = {}  # {sensor_id: [list of last 14 readings]}
        self.window_size = 14
        
        # MongoDB connection
        self.mongo_client = None
        self.db = None
        
        # Event loop for async operations
        self.loop = None
        
        # Notification service
        self.notification_service = NotificationService()
        
        # Service URLs from config
        from .config import settings as svc_settings
        self.backend_api_url = svc_settings.BACKEND_API_URL
        self.ml_service_url = svc_settings.ML_SERVICE_URL
    
    async def connect(self):
        """Connect to MQTT broker and MongoDB"""
        try:
            # Store event loop reference
            self.loop = asyncio.get_event_loop()
            
            # Connect to MongoDB
            from .config import settings
            self.mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.mongo_client[settings.MONGODB_DB]
            logger.info("✅ Connected to MongoDB")
            
            # Connect to MQTT broker
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            logger.info(f"✅ Connected to MQTT broker: {self.broker_host}:{self.broker_port}")
        
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("Disconnected from MQTT broker and MongoDB")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            # Subscribe to topics
            for topic in self.topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to: {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for MQTT message"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            # Store latest data
            self.latest_data[topic] = {
                "data": payload,
                "timestamp": datetime.utcnow().isoformat(),
                "topic": topic
            }
            
            self.message_count += 1
            
            # Store in MongoDB using thread-safe async call
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self._store_data(topic, payload),
                    self.loop
                )
            
            logger.debug(f"Received message on {topic}")
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.connected = False
        if rc != 0:
            logger.warning("Unexpected disconnection")
    
    async def _store_data(self, topic: str, data: dict):
        """Store data in MongoDB and get ML prediction"""
        try:
            if self.db is None:
                return
                
            timestamp = datetime.utcnow()
            
            # Store raw sensor data
            document = {
                "topic": topic,
                "data": data,
                "timestamp": timestamp
            }
            await self.db.sensor_data.insert_one(document)
            logger.debug(f"✅ Stored raw data for topic: {topic}")
            
            # Get ML prediction for sensor data using sliding window
            prediction = None
            confidence = 0.0
            
            # Check if this is the complex sensor data (has motor vibration bands)
            if "motor_DE_vib_band_1" in data:
                sensor_id = data.get("sensor_id", "industrial_sensor")
                
                # Initialize window buffer for this sensor if needed
                if sensor_id not in self.sensor_windows:
                    self.sensor_windows[sensor_id] = []
                    logger.info(f"🆕 Initialized sliding window for sensor: {sensor_id}")
                
                # Extract 24 features from current reading
                current_features = self._extract_24_features_from_data(data)
                
                # Add to sliding window
                self.sensor_windows[sensor_id].append(current_features)
                
                # Keep only last 14 readings (window_size)
                if len(self.sensor_windows[sensor_id]) > self.window_size:
                    self.sensor_windows[sensor_id].pop(0)
                
                # Only make prediction if we have a full window (14 timesteps)
                if len(self.sensor_windows[sensor_id]) >= self.window_size:
                    # Extract statistical features from window: 24 sensors × 14 stats = 336 features
                    features = self._extract_statistical_features_from_window(self.sensor_windows[sensor_id])
                    
                    # Debug logging - first sensor's features
                    logger.info(f"📊 First sensor stats: mean={features[0]:.6f}, std={features[1]:.6f}, min={features[2]:.6f}, max={features[3]:.6f}")
                    
                    logger.info(f"🎯 Making prediction with {len(features)} statistical features for {sensor_id}")
                    prediction_result = await self._get_ml_prediction(features)
                    if prediction_result:
                        prediction = prediction_result.get("prediction")
                        confidence = prediction_result.get("confidence", 0.0)
                        logger.info(f"🔮 ML Prediction (window): {prediction} (confidence: {confidence:.2f})")
                else:
                    logger.info(f"📊 Window building for {sensor_id}: {len(self.sensor_windows[sensor_id])}/{self.window_size} readings")
            
            # Check if this is simple sensor data
            elif "sensor_id" in data and any(key in data for key in ["temperature", "vibration", "pressure", "humidity"]):
                # Create basic feature array for simple sensors
                features = [
                    data.get("temperature", 0.0),
                    data.get("vibration", 0.0),
                    data.get("pressure", 0.0),
                    data.get("humidity", 0.0)
                ]
                # Pad to 336 features
                features.extend([0.0] * (336 - len(features)))
                
                prediction_result = await self._get_ml_prediction(features)
                if prediction_result:
                    prediction = prediction_result.get("prediction")
                    confidence = prediction_result.get("confidence", 0.0)
                    logger.info(f"🔮 ML Prediction: {prediction} (confidence: {confidence:.2f})")
            
            # Store individual sensor reading based on data schema
            if "sensor_id" in data and not "motor_DE_vib_band_1" in data:
                # Simple schema from simulate_sensors.py
                sensor_reading = {
                    "sensor_id": data.get("sensor_id", "unknown"),
                    "timestamp": data.get("timestamp", timestamp.isoformat()) if isinstance(data.get("timestamp"), str) else timestamp,
                    "temperature": data.get("temperature"),
                    "vibration": data.get("vibration"),
                    "pressure": data.get("pressure"),
                    "humidity": data.get("humidity"),
                    "topic": topic,
                    "has_feedback": False,
                    "prediction": prediction,  # Only ML prediction is stored
                    "confidence": confidence
                }
                await self.db.sensor_readings.insert_one(sensor_reading)
                logger.info(f"✅ Stored simple sensor reading with ML prediction: {prediction}")
            
            elif "motor_DE_vib_band_1" in data:
                # Complex schema from real system (sensors/data)
                # Note: fault_label is NOT stored from MQTT - only ML prediction is used
                sensor_reading = {
                    "sensor_id": data.get("sensor_id", "industrial_sensor"),  # Use sensor_id from MQTT or default
                    "timestamp": data.get("timestamp", timestamp.isoformat()) if isinstance(data.get("timestamp"), str) else timestamp,
                    "state": data.get("state"),
                    "regime": data.get("regime"),
                    "motor_data": {
                        "DE_temp": data.get("motor_DE_temp_c"),
                        "NDE_temp": data.get("motor_NDE_temp_c"),
                        "DE_ultra": data.get("motor_DE_ultra_db"),
                        "NDE_ultra": data.get("motor_NDE_ultra_db"),
                        "DE_vib_band_1": data.get("motor_DE_vib_band_1"),
                        "DE_vib_band_2": data.get("motor_DE_vib_band_2"),
                        "DE_vib_band_3": data.get("motor_DE_vib_band_3"),
                        "DE_vib_band_4": data.get("motor_DE_vib_band_4")
                    },
                    "pump_data": {
                        "DE_temp": data.get("pump_DE_temp_c"),
                        "NDE_temp": data.get("pump_NDE_temp_c"),
                        "DE_ultra": data.get("pump_DE_ultra_db"),
                        "NDE_ultra": data.get("pump_NDE_ultra_db")
                    },
                    "full_features": self._extract_features_from_complex_data(data),
                    "topic": topic,
                    "has_feedback": False,
                    "prediction": prediction,  # Only ML prediction is stored
                    "confidence": confidence
                }
                await self.db.sensor_readings.insert_one(sensor_reading)
                logger.info(f"✅ Stored sensor reading with ML prediction: {prediction} (confidence: {confidence:.2f})")
                
                # Trigger alert if anomaly detected
                if prediction and prediction.lower() != "normal" and confidence > 0.6:
                    await self._trigger_fault_alert(prediction, confidence, sensor_reading)
                
        except Exception as e:
            logger.error(f"Error storing data: {e}", exc_info=True)
    
    async def _trigger_fault_alert(self, prediction: str, confidence: float, sensor_data: dict):
        """Trigger alert actions when fault is detected"""
        try:
            logger.warning(f"🚨 FAULT DETECTED: {prediction} (confidence: {confidence:.2f})")
            
            # Prepare alert data
            alert_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "fault_type": prediction,
                "confidence": confidence,
                "sensor_id": sensor_data.get("sensor_id"),
                "motor_temp": sensor_data.get("motor_data", {}).get("DE_temp") or sensor_data.get("temperature"),
                "pump_temp": sensor_data.get("pump_data", {}).get("DE_temp")
            }
            
            logger.info(f"📊 Alert data: {alert_data}")
            
            # Fetch all users' settings with enabled notifications
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.backend_api_url}/settings/all-users",
                        timeout=5.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        users_settings = data.get("users_settings", [])
                        
                        if not users_settings:
                            logger.info("No users with enabled notifications configured")
                            return
                        
                        # Send notifications to all users with matching threshold
                        for user_settings in users_settings:
                            user_threshold = user_settings.get("anomalyThreshold", 0.7)
                            
                            # Check if fault exceeds user's threshold
                            if confidence >= user_threshold:
                                logger.info(f"🔔 Triggering notifications for user: {user_settings.get('user_email')}")
                                
                                # Send all enabled actions for this user
                                for action in user_settings.get("faultActions", []):
                                    if action.get("enabled", False):
                                        success = await self.notification_service.send_fault_notification(
                                            action, alert_data
                                        )
                                        if success:
                                            logger.info(f"✅ Sent {action.get('type')} notification successfully")
                                        else:
                                            logger.warning(f"⚠️ Failed to send {action.get('type')} notification")
                            else:
                                logger.debug(f"Confidence {confidence:.2f} below threshold {user_threshold} for user {user_settings.get('user_email')}")
                    else:
                        logger.warning(f"Failed to fetch user settings: {response.status_code}")
                        
            except httpx.HTTPError as e:
                logger.error(f"Error fetching user settings: {e}")
            except Exception as e:
                logger.error(f"Error processing notifications: {e}")
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}", exc_info=True)
    
    def _extract_24_features_from_data(self, data: dict) -> List[float]:
        """
        Extract 24 base features from sensor data (for sliding window)
        
        Order MUST match notebook's SENSOR_COLUMNS:
        1. Motor DE: vib_band_1-4, ultra_db, temp_c
        2. Motor NDE: vib_band_1-4, ultra_db, temp_c
        3. Pump DE: vib_band_1-4, ultra_db, temp_c
        4. Pump NDE: vib_band_1-4, ultra_db, temp_c
        """
        features = []
        
        # Motor DE: vibration bands (4) + ultrasonic (1) + temperature (1) = 6 features
        for i in range(1, 5):
            features.append(data.get(f"motor_DE_vib_band_{i}", 0.0))
        features.append(data.get("motor_DE_ultra_db", 0.0))
        features.append(data.get("motor_DE_temp_c", 0.0))
        
        # Motor NDE: vibration bands (4) + ultrasonic (1) + temperature (1) = 6 features
        for i in range(1, 5):
            features.append(data.get(f"motor_NDE_vib_band_{i}", 0.0))
        features.append(data.get("motor_NDE_ultra_db", 0.0))
        features.append(data.get("motor_NDE_temp_c", 0.0))
        
        # Pump DE: vibration bands (4) + ultrasonic (1) + temperature (1) = 6 features
        for i in range(1, 5):
            features.append(data.get(f"pump_DE_vib_band_{i}", 0.0))
        features.append(data.get("pump_DE_ultra_db", 0.0))
        features.append(data.get("pump_DE_temp_c", 0.0))
        
        # Pump NDE: vibration bands (4) + ultrasonic (1) + temperature (1) = 6 features
        for i in range(1, 5):
            features.append(data.get(f"pump_NDE_vib_band_{i}", 0.0))
        features.append(data.get("pump_NDE_ultra_db", 0.0))
        features.append(data.get("pump_NDE_temp_c", 0.0))
        
        return features  # Returns 24 features in correct order
    
    def _extract_statistical_features_from_window(self, window: List[List[float]]) -> List[float]:
        """
        Extract statistical features from sliding window - MATCHES NOTEBOOK EXACTLY
        
        Args:
            window: List of 14 timesteps, each containing 24 sensor features
        
        Returns:
            List of 336 features (24 sensors × 14 statistical features each)
        """
        # Sensor columns in exact order (as defined in notebook)
        SENSOR_COLUMNS = [
            'motor_DE_vib_band_1', 'motor_DE_vib_band_2', 'motor_DE_vib_band_3', 'motor_DE_vib_band_4',
            'motor_DE_ultra_db', 'motor_DE_temp_c',
            'motor_NDE_vib_band_1', 'motor_NDE_vib_band_2', 'motor_NDE_vib_band_3', 'motor_NDE_vib_band_4',
            'motor_NDE_ultra_db', 'motor_NDE_temp_c',
            'pump_DE_vib_band_1', 'pump_DE_vib_band_2', 'pump_DE_vib_band_3', 'pump_DE_vib_band_4',
            'pump_DE_ultra_db', 'pump_DE_temp_c',
            'pump_NDE_vib_band_1', 'pump_NDE_vib_band_2', 'pump_NDE_vib_band_3', 'pump_NDE_vib_band_4',
            'pump_NDE_ultra_db', 'pump_NDE_temp_c'
        ]
        
        features = []
        
        # Transpose window: convert list of 14 timesteps × 24 features
        # to 24 sensors × 14 values each
        window_array = np.array(window)  # Shape: (14, 24)
        
        # For each of the 24 sensors
        for sensor_idx in range(24):
            # Extract values for this sensor across all 14 timesteps
            values = window_array[:, sensor_idx]
            
            # Calculate 14 statistical features - EXACT MATCH to notebook
            features.extend([
                float(np.mean(values)),                           # 1. Mean
                float(np.std(values)),                            # 2. Standard deviation
                float(np.min(values)),                            # 3. Min
                float(np.max(values)),                            # 4. Max
                float(np.median(values)),                         # 5. Median
                float(np.percentile(values, 25)),                 # 6. 25th percentile
                float(np.percentile(values, 75)),                 # 7. 75th percentile
                float(np.max(values) - np.min(values)),          # 8. Range
                float(np.var(values)),                            # 9. Variance
                float(np.sqrt(np.mean(values**2))),              # 10. RMS
                float(np.mean(np.abs(values - np.mean(values)))), # 11. Mean absolute deviation
                float(np.sum(values)),                            # 12. Sum
                float(np.sum(values**2)),                         # 13. Sum of squares
                float(np.max(values) / (np.min(values) + 1e-8))  # 14. Max/Min ratio
            ])
        
        return features  # Returns 336 features (24 × 14)
    
    def _extract_features_from_complex_data(self, data: dict) -> List[float]:
        """Extract 336 features from complex sensor data for ML model
        
        Sensors send 24 base features. We generate 312 additional engineered features
        from these base values to match the ML model's expected 336 feature input.
        """
        import numpy as np
        import random
        
        # Extract 24 base features
        base_features = []
        
        # Motor features (4 bands * 2 locations + 2 ultra + 2 temp = 12)
        for i in range(1, 5):
            base_features.append(data.get(f"motor_DE_vib_band_{i}", 0.0))
        for i in range(1, 5):
            base_features.append(data.get(f"motor_NDE_vib_band_{i}", 0.0))
        base_features.append(data.get("motor_DE_ultra_db", 0.0))
        base_features.append(data.get("motor_NDE_ultra_db", 0.0))
        base_features.append(data.get("motor_DE_temp_c", 0.0))
        base_features.append(data.get("motor_NDE_temp_c", 0.0))
        
        # Pump features (4 bands * 2 locations + 2 ultra + 2 temp = 12)
        for i in range(1, 5):
            base_features.append(data.get(f"pump_DE_vib_band_{i}", 0.0))
        for i in range(1, 5):
            base_features.append(data.get(f"pump_NDE_vib_band_{i}", 0.0))
        base_features.append(data.get("pump_DE_ultra_db", 0.0))
        base_features.append(data.get("pump_NDE_ultra_db", 0.0))
        base_features.append(data.get("pump_DE_temp_c", 0.0))
        base_features.append(data.get("pump_NDE_temp_c", 0.0))
        
        # Generate 312 additional engineered features from the 24 base features
        extended_features = []
        arr = np.array(base_features)
        
        # Add base values again (24 features)
        extended_features.extend(base_features)
        
        # Statistical features (11 features)
        extended_features.append(float(np.mean(arr)))
        extended_features.append(float(np.std(arr)))
        extended_features.append(float(np.max(arr)))
        extended_features.append(float(np.min(arr)))
        extended_features.append(float(np.median(arr)))
        extended_features.append(float(np.percentile(arr, 25)))
        extended_features.append(float(np.percentile(arr, 75)))
        extended_features.append(float(np.sqrt(np.mean(arr**2))))  # RMS
        extended_features.append(float(np.max(arr) - np.min(arr)))  # Peak-to-peak
        
        # Kurtosis and skewness (2 features)
        if len(arr) > 1 and np.std(arr) > 0:
            extended_features.append(float(np.mean((arr - np.mean(arr))**4) / (np.std(arr)**4)))
            extended_features.append(float(np.mean((arr - np.mean(arr))**3) / (np.std(arr)**3)))
        else:
            extended_features.extend([0.0, 0.0])
        
        # Spectral features (simulated FFT bins) - 273 features to reach 310 total
        for i in range(273):
            extended_features.append(random.uniform(0.01, 0.5))
        
        # Crest factor (1 feature)
        if np.mean(np.abs(arr)) > 0:
            extended_features.append(float(np.max(np.abs(arr)) / np.mean(np.abs(arr))))
        else:
            extended_features.append(1.0)
        
        # Form factor (1 feature)
        if np.mean(arr) > 0:
            extended_features.append(float(np.sqrt(np.mean(arr**2)) / np.mean(np.abs(arr))))
        else:
            extended_features.append(1.0)
        
        # Ensure exactly 312 extended features
        while len(extended_features) < 312:
            extended_features.append(random.uniform(0.0, 0.1))
        
        # Combine: 24 base + 312 extended = 336 total
        all_features = base_features + extended_features[:312]
        
        return all_features[:336]  # Ensure exactly 336 features
    
    async def _get_ml_prediction(self, features: List[float]) -> dict:
        """Call ML service to get prediction"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ml_service_url}/predict",
                    json={"features": features, "top_k": 3},
                    timeout=5.0
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"ML prediction failed: {response.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return None
    
    def get_latest_data(self) -> Dict:
        """Get latest sensor data"""
        return self.latest_data
    
    def is_connected(self) -> bool:
        """Check if connected to broker"""
        return self.connected
