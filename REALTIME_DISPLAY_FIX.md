# Real-time Data Display - Fixed! ✅

## What Was Fixed

### Problem
The Real-time Data page showed "Unknown" sensor with all N/A values because:
1. Frontend expected simple schema (temperature, vibration, pressure, humidity)
2. Your MQTT data uses complex schema (motor/pump vibration bands, temps, ultrasonic)

### Solution
Updated `RealtimeData.tsx` to:
1. Handle BOTH simple and complex sensor data schemas
2. Map complex sensor fields to display columns:
   - **Motor Temp** ← `motor_DE_temp_c`
   - **Motor Vib** ← `motor_DE_vib_band_1` (first vibration band)
   - **Pump Ultra** ← `pump_DE_ultra_db` (ultrasonic reading)
   - **Pump Temp** ← `pump_DE_temp_c`
   - **Status** ← `fault_label` (with colored chip: green=normal, yellow=fault)

## Current System Status

### ✅ Working Features
- **MQTT Ingestion**: Receiving messages from `sensors/data` topic
- **ML Predictions**: Generated for each reading (73% confidence)
- **Database Storage**: All data saved in MongoDB
- **WebSocket Streaming**: Real-time data flowing to frontend
- **Frontend Display**: Shows motor/pump sensor values with status

### 📊 Data Flow
```
MQTT Publisher → Broker → mqtt-ingestion service
                             ↓
                    ML Service (prediction)
                             ↓
                    MongoDB (storage)
                             ↓
                    WebSocket → Frontend (display)
```

## How to Test

### 1. Start Continuous Data Stream
```bash
python continuous_mqtt_publisher.py
```
This will:
- Publish every 5 seconds
- 20% chance of anomaly injection
- Show status in console

### 2. View Real-time Data
Open: http://localhost:3000/realtime

You should see:
- Green "Connected" chip
- Table with sensor readings updating every second
- Motor temperature (42-47°C)
- Motor vibration (0.7-2.5 Hz)
- Pump ultrasonic (36-39 dB)
- Pump temperature (40-44°C)
- Status chip (green "normal" or yellow "high_vibration_anomaly")

### 3. Check Stored Data with Predictions
Open: http://localhost:3000/feedback

You'll see all historical readings with ML predictions stored in the database.

## Data Mapping Reference

### Complex Schema (sensors/data) → Display
| Display Column | Source Field | Description |
|---------------|--------------|-------------|
| Sensor ID | "Industrial Sensor" | Fixed label for complex data |
| Motor Temp | motor_DE_temp_c | Motor drive-end temperature in °C |
| Motor Vib | motor_DE_vib_band_1 | Motor vibration band 1 in Hz |
| Pump Ultra | pump_DE_ultra_db | Pump ultrasonic reading in dB |
| Pump Temp | pump_DE_temp_c | Pump drive-end temperature in °C |
| Status | fault_label | Fault classification (normal/anomaly) |

### Simple Schema (sensors/industrial/data) → Display
| Display Column | Source Field |
|---------------|--------------|
| Sensor ID | sensor_id |
| Motor Temp | temperature |
| Motor Vib | vibration |
| Pump Ultra | pressure |
| Pump Temp | humidity |

## Current Test Data

Published 3 messages including 1 anomaly:
```
✅ Message #1 | 2026-01-31 23:40:17 | normal
✅ Message #2 | 2026-01-31 23:40:22 | normal
⚠️ Message #3 | 2026-01-31 23:40:27 | high_vibration_anomaly
```

## Database Status
- Total readings stored: 9+
- All include ML predictions (e.g., "data_dropout" with 73% confidence)
- All available in Feedback page for user labeling

## Troubleshooting

### If No Data Appears
1. Refresh browser (hard refresh: Ctrl+Shift+R)
2. Check WebSocket connection status (should be green "Connected")
3. Ensure MQTT publisher is running: `python continuous_mqtt_publisher.py`
4. Check mqtt-ingestion logs: `docker-compose logs mqtt-ingestion --tail 20`

### If Data Still Shows N/A
1. Open browser developer console (F12)
2. Go to Network tab → WS filter
3. Check WebSocket messages are arriving
4. Verify data structure matches the expected schema

## Next Steps
1. Keep `continuous_mqtt_publisher.py` running for continuous data
2. Refresh http://localhost:3000/realtime to see live updates
3. Monitor anomaly detection in Status column
4. Use Feedback page to label predictions for model improvement
