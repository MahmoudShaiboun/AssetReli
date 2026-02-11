# Aastreli Industrial Anomaly Detection System - Complete Summary

## 🎯 System Overview
The Aastreli system is a complete industrial anomaly detection platform that uses Machine Learning to predict faults in real-time from sensor data received via MQTT.

## ✅ Implemented Features

### 1. **ML Prediction Engine**
- ✅ **Every reading gets ML prediction** - All sensor data is automatically analyzed
- ✅ **34 Fault Types** - The model can detect 34 different industrial fault types
- ✅ **Real-time Predictions** - Predictions generated immediately upon data receipt
- ✅ **Confidence Scores** - Each prediction includes confidence percentage (0-100%)
- ✅ **Automatic Storage** - All predictions saved to MongoDB with timestamps

### 2. **Frontend UI - 6 Pages**

#### **Dashboard** (/)
- Real-time sensor values (Motor temp, Motor vib, Pump temp, Pump ultra)
- Latest ML prediction display
- 4 Interactive graphs with live updates (5-second refresh)
- Recent predictions with anomaly highlighting (yellow borders)
- Statistics: Total predictions, Feedback collected

#### **Real-time Data** (/realtime)
- Live WebSocket streaming of sensor data
- Table view with real-time updates
- Status indicators (Normal/Anomaly)
- Sensor readings with timestamps

#### **Predictions** (/predictions)
- Complete history of all ML predictions
- Paginated table with 100 recent predictions
- Anomaly highlighting (yellow background)
- Confidence scores with color coding
- Auto-refresh every 10 seconds
- Shows: Timestamp (UTC), Sensor ID, Prediction, Confidence, Temperatures

#### **Fault Types** (/fault-types) **[NEW]**
- **Complete list of 34 fault types** the ML model can detect
- Organized display with numbered fault types
- Categorized by fault category:
  - **Mechanical Faults** (bearings, shafts, impellers, etc.)
  - **Hydraulic Faults** (cavitation, valves, seals, etc.)
  - **Electrical Faults** (rotor bars, phase unbalance, etc.)
  - **Sensor & Data Faults** (dropout, drift, scaling errors)

#### **Feedback** (/feedback)
- Review sensor readings with predictions
- Multi-row selection for batch feedback
- Anomaly highlighting (yellow rows, red chips)
- Submit corrections to improve ML model
- Statistics chips showing anomaly count

#### **Settings** (/settings)
- System configuration options

### 3. **Available Fault Types (34 Total)**
```
1.  normal
2.  pump_bearing_cage_defect
3.  hydraulic_pulsation_resonance
4.  bearing_overgrease_churn
5.  check_valve_flutter_proxy
6.  data_dropout
7.  loss_of_prime_dry_run_proxy
8.  impeller_damage
9.  belt_slip_or_drive_issue
10. suction_strainer_plugging
11. bearing_fit_tight_preload
12. rotor_bar_crack_proxy
13. internal_rub_proxy
14. seal_flush_failure_proxy
15. phase_unbalance
16. lube_contamination_water
17. stuck_sensor_flatline
18. piping_strain
19. sensor_drift_bias
20. instrument_scaling_error
21. fan_blade_damage
22. coupling_wear
23. discharge_restriction
24. power_frequency_variation
25. wear_ring_clearance
26. foundation_grout_degradation
27. shaft_bow_proxy
28. bearing_fit_loose_housing
29. loose_hub_keyway
30. air_gas_ingress
31. cooling_failure
32. blower_aero_stall_surge_proxy
33. electrical_fluting
34. seal_face_distress_proxy
```

### 4. **Backend Services**

#### **MQTT Ingestion Service** (Port 8002)
- Subscribes to `sensors/data` topic
- **Calls ML service for EVERY reading**
- Stores raw data + predictions in MongoDB
- WebSocket streaming endpoint for real-time UI
- Logs: `🔮 ML Prediction: {fault_type} (confidence: {score})`

#### **ML Service** (Port 8001)
- XGBoost model with 336 features
- `/predict` endpoint - Returns prediction + confidence
- `/feedback` endpoint - Stores feedback for retraining
- `/retrain` endpoint - Triggers model retraining
- Uses current model version for all predictions

#### **Backend API** (Port 8000)
- `/sensor-readings` - Paginated sensor data with predictions
- `/dashboard` - Summary statistics and recent readings
- `/feedback` - Submit feedback, updates readings in DB
- All responses include UTC timestamps

#### **MongoDB** (Port 27017)
- **Collections**:
  - `sensor_data` - Raw MQTT messages
  - `sensor_readings` - **With ML predictions** (prediction + confidence)
  - `feedback` - User corrections for model improvement

### 5. **Data Flow**
```
MQTT Message → MQTT Ingestion → ML Service (Prediction) → MongoDB
                     ↓                                        ↓
                WebSocket ←──────────────────────→  Backend API
                     ↓                                        ↓
                  Frontend (Real-time + Historical Display)
```

## 🔧 Technical Stack
- **Frontend**: React 18 + TypeScript + Material-UI + Recharts
- **Backend**: FastAPI (Python 3.10)
- **ML**: XGBoost + scikit-learn
- **Database**: MongoDB 6.0
- **Messaging**: MQTT (Eclipse Mosquitto 2.0)
- **Real-time**: WebSocket
- **Deployment**: Docker Compose (6 services)

## 📊 Key Metrics
- **Response Time**: ML predictions generated in <100ms
- **Update Frequency**: Dashboard updates every 5 seconds
- **Prediction Coverage**: 100% of readings get ML predictions
- **Fault Detection**: 34 different fault types
- **Data Retention**: All predictions stored with full context

## 🚀 System Status
✅ All 6 containers running
✅ ML predictions working (every reading)
✅ MongoDB storing predictions with confidence scores
✅ Frontend displaying predictions in real-time
✅ Fault Types page showing all 34 categories
✅ WebSocket streaming active
✅ MQTT ingestion operational

## 🌐 Access URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **ML Service**: http://localhost:8001
- **MQTT Ingestion**: http://localhost:8002
- **MQTT Broker**: mqtt://localhost:1883

## 📈 Recent Enhancements
1. ✅ Added Fault Types page with all 34 fault categories
2. ✅ ML predictions on every single reading (100% coverage)
3. ✅ Predictions automatically saved to MongoDB
4. ✅ Real-time display of predictions in UI
5. ✅ Improved dashboard with live prediction status
6. ✅ Enhanced Predictions page with full history
7. ✅ UTC time standardization across all services
8. ✅ Anomaly highlighting in multiple views
9. ✅ Confidence score visualization with color coding
10. ✅ Complete Docker rebuild with all changes

## 🔄 Testing
To test the complete system:
```powershell
# Start publishing test data
python continuous_mqtt_publisher.py

# Check ML predictions are being generated
docker-compose logs mqtt-ingestion --tail 20

# Access frontend
Start http://localhost:3000
```

Expected results:
- Dashboard shows latest prediction (not "Waiting...")
- Predictions page displays full history
- Fault Types page shows all 34 fault types
- MQTT logs show "🔮 ML Prediction" for each message
- MongoDB contains predictions with confidence scores

## 📝 Notes
- No fault labels sent via MQTT (removed)
- All fault detection is ML-based
- System uses UTC timestamps consistently
- Predictions update in real-time (5s refresh)
- Feedback system allows model improvement
