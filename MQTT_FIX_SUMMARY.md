# MQTT System Fix Summary

## Issues Identified and Fixed

### 1. ❌ **Event Loop Bug** - Data NOT Being Stored
**Problem:** `asyncio.create_task()` called from synchronous MQTT callback without event loop
**Error:** `"no running event loop"`
**Fix:** Changed to `asyncio.run_coroutine_threadsafe(coro, loop)` with stored loop reference

### 2. ❌ **Database Check Bug** - MongoDB Write Failure  
**Problem:** `if not self.db:` raised `NotImplementedError` with motor database objects
**Error:** `"Database objects do not implement truth value testing"`
**Fix:** Changed to `if self.db is None:`

### 3. ❌ **Missing ML Predictions** - No Anomaly Detection
**Problem:** Incoming sensor data wasn't sent to ML service for prediction
**Fix:** Added `_get_ml_prediction()` method that calls ML service HTTP endpoint
**Result:** Every sensor reading now gets anomaly prediction with confidence score

### 4. ❌ **Schema Mismatch** - Only Handled Simple Sensor Data
**Problem:** Code only handled simple 4-field schema (temp, vib, press, humid)
**Real Data:** Complex 24-field schema (motor/pump vibration bands, temps, ultrasonic)
**Fix:** Added dual schema support:
  - Simple schema: `sensors/industrial/data` (from simulator)
  - Complex schema: `sensors/data` (from your real system)

## Code Changes Summary

### Modified Files:
1. **mqtt-ingestion/app/mqtt_client.py**
   - Added `httpx` import for ML service calls
   - Added `self.loop` to store event loop reference
   - Fixed `_on_message()` to use `run_coroutine_threadsafe()`
   - Rewrote `_store_data()` to handle both schemas and call ML service
   - Added `_extract_features_from_complex_data()` for 336-feature extraction
   - Added `_get_ml_prediction()` for ML service HTTP calls

2. **mqtt-ingestion/requirements.txt**
   - Added `httpx==0.26.0` dependency

## How It Works Now

```
MQTT Message Arrives
      ↓
Stored in latest_data (WebSocket broadcasting)
      ↓
asyncio.run_coroutine_threadsafe() schedules async task
      ↓
_store_data() runs in event loop:
  1. Store raw data → sensor_data collection
  2. Extract 336 features (if complex schema)
  3. Call ML service → Get prediction + confidence
  4. Store structured reading → sensor_readings collection
      ↓
Data Available:
  - MongoDB: Both collections populated
  - WebSocket: Real-time streaming to frontend
  - Feedback: Readings available for user labeling
```

## Database Schema

### sensor_data (Raw MQTT)
```json
{
  "topic": "sensors/data",
  "data": { /* full MQTT payload */ },
  "timestamp": "2026-01-31T21:30:37.148269"
}
```

### sensor_readings (Structured with Predictions)
```json
{
  "sensor_id": "industrial_sensor",
  "timestamp": "2026-01-31 23:30:37",
  "state": "fault_injections",
  "regime": "nominal",
  "fault_label": "normal",
  "motor_data": {
    "DE_temp": 44.6,
    "NDE_temp": 44.4,
    "DE_ultra": 35.53,
    "NDE_ultra": 34.12
  },
  "pump_data": {
    "DE_temp": 42.12,
    "NDE_temp": 42.20,
    "DE_ultra": 37.4,
    "NDE_ultra": 38.33
  },
  "full_features": [/* 336 float values */],
  "topic": "sensors/data",
  "has_feedback": false,
  "prediction": "data_dropout",
  "confidence": 0.7315
}
```

## Testing

### Test Single Message
```bash
python test_mqtt_publish.py
```

### Test Continuous Stream (Recommended)
```bash
python continuous_mqtt_publisher.py
```
- Publishes every 5 seconds
- 20% chance of injecting anomalies
- Shows real-time status in console

### Verify Data Flow
```bash
# Check logs
docker-compose logs mqtt-ingestion --tail 50

# Count documents
docker exec aastreli-mongodb mongosh aastreli --quiet --eval 'db.sensor_readings.countDocuments({})'

# View latest with prediction
docker exec aastreli-mongodb mongosh aastreli --quiet --eval 'db.sensor_readings.find().sort({timestamp:-1}).limit(1).pretty()'
```

### Frontend Testing
1. Open http://localhost:3000/realtime
   - Should see live data updating every second
   - Connection status: green "Connected"
   
2. Open http://localhost:3000/feedback
   - Browse stored sensor readings with predictions
   - Select rows and submit feedback
   - Readings marked with ✓ after feedback

## ML Predictions

The ML service analyzes the 336-feature vector and returns:
- **Prediction:** Fault class (e.g., "data_dropout", "normal", "high_vibration")
- **Confidence:** Score 0.0-1.0 (e.g., 0.73 = 73% confident)
- **Top-K Predictions:** Top 3 most likely fault classes

Example from logs:
```
INFO:app.mqtt_client:🔮 Prediction: data_dropout (confidence: 0.73)
```

## Why Your Data Wasn't Showing Before

1. **No MQTT Publisher Running** - No messages being sent to broker
2. **Event Loop Bug** - Messages received but storage failed silently
3. **Database Check Bug** - Storage code crashed before writing
4. **No Predictions** - ML service never called
5. **WebSocket** - Frontend couldn't display data that wasn't stored

## Current Status: ✅ ALL FIXED

- ✅ MQTT messages received and processed
- ✅ Data stored in both MongoDB collections  
- ✅ ML predictions generated with confidence scores
- ✅ WebSocket streaming to frontend
- ✅ Feedback system can query stored readings
- ✅ Dual schema support (simple + complex sensor data)

## Next Steps

1. **Start continuous publisher:**
   ```bash
   python continuous_mqtt_publisher.py
   ```

2. **Open frontend dashboards:**
   - Real-time data: http://localhost:3000/realtime
   - Feedback system: http://localhost:3000/feedback

3. **Monitor your real sensor data:**
   - If you have a hardware sensor or data replay system
   - Make sure it publishes to `sensors/data` topic
   - The system will automatically detect the schema and process it

## File Reference

| File | Purpose |
|------|---------|
| `test_mqtt_publish.py` | Single test message |
| `continuous_mqtt_publisher.py` | Continuous data stream with anomalies |
| `simulate_sensors.py` | Simple 4-field simulator (sensors/industrial/data) |
| `mqtt-ingestion/app/mqtt_client.py` | Fixed MQTT client with ML integration |
