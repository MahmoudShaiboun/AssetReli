# Real-time MQTT Data & Feedback System

## New Features

### 1. Real-time Data Display
- Navigate to **Real-time Data** in the menu to see live sensor data
- Data streams directly from MQTT broker via WebSocket
- Shows current values for all active sensors
- Automatically updates as new data arrives

### 2. Database Storage
- All MQTT sensor readings are automatically stored in MongoDB
- Two collections:
  - `sensor_data`: Raw MQTT messages
  - `sensor_readings`: Structured individual readings for easy querying

### 3. Feedback System with Row Selection
- Navigate to **Feedback** page
- Browse all stored sensor readings in a paginated table
- Select multiple rows (readings) using checkboxes
- Click "Submit Feedback for Selected" button
- Choose the correct label (normal, anomaly, specific fault types)
- Add optional notes
- Feedback is:
  - Sent to ML service for model improvement
  - Stored in database with reading reference
  - Marks readings as "feedback given"

## Testing the System

### 1. Start the Simulator
Run the sensor simulator to generate test data:

```powershell
# Install paho-mqtt if not already installed
pip install paho-mqtt

# Run the simulator
python simulate_sensors.py
```

The simulator will:
- Generate data for 3 sensors every 5 seconds
- Occasionally introduce anomalies (10% chance)
- Display what it's sending in the console

### 2. View Real-time Data
1. Open browser to http://localhost:3000
2. Navigate to **Real-time Data** menu
3. You should see sensor readings updating live
4. The "Connected" chip should be green

### 3. Submit Feedback
1. Navigate to **Feedback** page
2. Wait for data to load (readings from database)
3. Select one or more rows by clicking checkboxes
4. Click "Submit Feedback for Selected"
5. Choose the correct label for the selected readings
6. Add optional notes
7. Click "Submit Feedback"
8. The readings will be marked with "✓ Feedback given"

## API Endpoints

### Backend API (Port 8000)

- `GET /sensor-readings` - Get paginated sensor readings
  - Query params: `skip`, `limit`, `sensor_id`
- `POST /feedback` - Submit feedback with reading reference
  - Includes: `reading_id`, `sensor_id`, `timestamp`

### MQTT Ingestion (Port 8002)

- `GET /latest` - Get latest sensor data
- `WS /stream` - WebSocket for real-time streaming

## Database Schema

### sensor_readings Collection
```json
{
  "_id": "ObjectId",
  "sensor_id": "sensor_001",
  "timestamp": "2026-01-31T20:00:00",
  "temperature": 65.2,
  "vibration": 2.3,
  "pressure": 102.5,
  "humidity": 43.1,
  "topic": "sensors/industrial/data",
  "has_feedback": false,
  "prediction": {
    "label": "normal",
    "confidence": 0.95
  }
}
```

### feedback Collection
```json
{
  "_id": "ObjectId",
  "features": [65.2, 2.3, 102.5, 43.1],
  "original_prediction": "normal",
  "corrected_label": "bearing_fault",
  "feedback_type": "correction",
  "notes": "Noticed unusual bearing noise",
  "sensor_id": "sensor_001",
  "reading_id": "ObjectId",
  "timestamp": "2026-01-31T20:00:00",
  "feedback_id": "fb_123",
  "created_at": "2026-01-31T20:05:00"
}
```

## Architecture Flow

```
MQTT Sensors → MQTT Broker → MQTT Ingestion Service
                                     ↓
                                  MongoDB (sensor_readings)
                                     ↓
                              Frontend (WebSocket) ← Real-time Display
                                     ↓
                              Feedback Page ← User Selection
                                     ↓
                              Backend API → ML Service
                                     ↓
                              MongoDB (feedback)
                                     ↓
                              Model Retraining
```

## Troubleshooting

### No real-time data appearing?
- Check if simulator is running: `python simulate_sensors.py`
- Check MQTT broker: `docker-compose logs mqtt-broker`
- Check MQTT ingestion: `docker-compose logs mqtt-ingestion`
- Verify WebSocket connection in browser console

### No readings in Feedback page?
- Make sure simulator has run for at least 30 seconds
- Check MongoDB: `docker-compose logs mongodb`
- Check backend API: `curl http://localhost:8000/sensor-readings`

### Can't submit feedback?
- Check browser console for errors
- Verify backend API: `docker-compose logs backend-api`
- Check ML service: `docker-compose logs ml-service`
