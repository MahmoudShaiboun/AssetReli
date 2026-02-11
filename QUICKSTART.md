# ⚡ Aastreli - Quick Start Guide

Get your Industrial Anomaly Detection System running in **5 minutes**!

## 🎯 What You're Building

A complete microservices system with:
- ✅ Real-time MQTT sensor data ingestion
- ✅ ML-powered fault prediction API
- ✅ Interactive feedback and retraining
- ✅ React dashboard for monitoring
- ✅ NoSQL database for time-series data

## 📦 Step 1: Prerequisites (2 minutes)

### Install Docker
```bash
# Verify Docker is installed
docker --version
docker-compose --version
```

Don't have Docker? Install from: https://docs.docker.com/get-docker/

### Get Your Trained Models Ready
You need these 3 files from your notebook:
- `xgboost_anomaly_detector.json`
- `label_encoder.pkl`  
- `feature_scaler.pkl`

## 🚀 Step 2: Setup Project (1 minute)

```bash
# Navigate to your project directory
cd <your-project-directory>

# Copy environment file (if .env.example exists)
cp .env.example .env

# Initialize directories
make init
```

## 📥 Step 3: Deploy ML Models (1 minute)

```bash
# Copy your trained models to the ML service
cp /mnt/user-data/outputs/xgboost_*.json ml-service/models/current/xgboost_anomaly_detector.json
cp /mnt/user-data/outputs/label_encoder.pkl ml-service/models/current/
cp /mnt/user-data/outputs/feature_scaler.pkl ml-service/models/current/

# Verify files
ls -l ml-service/models/current/
```

You should see:
```
xgboost_anomaly_detector.json
label_encoder.pkl
feature_scaler.pkl
```

## 🏗️ Step 4: Build and Start (2 minutes)

```bash
# Build all Docker images
make build

# Start all services
make up
```

This starts:
- MongoDB (database)
- MQTT Broker (message queue)
- ML Service (model API)
- MQTT Ingestion (data collector)
- Backend API (main API)
- Frontend (React dashboard)

## ✅ Step 5: Verify Everything Works

### Check Service Health
```bash
make health
```

Expected output:
```
🏥 Health Check:
✓ Backend API: http://localhost:8000 - healthy
✓ ML Service: http://localhost:8001 - healthy
✓ MQTT Ingestion: http://localhost:8002 - healthy
```

### Access the System

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend Dashboard** | http://localhost:3000 | Main UI |
| **Backend API** | http://localhost:8000/docs | API docs |
| **ML Service** | http://localhost:8001/docs | Model API |
| **MQTT Ingestion** | http://localhost:8002 | Data service |

## 🎉 You're Running!

Open your browser to **http://localhost:3000** and you should see the dashboard!

## 🧪 Test the System

### 1. Test Prediction API
```bash
# Make a prediction
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": [1.25, 1.08, 0.85, 0.66, 34.5, 45.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
  }'
```

Response:
```json
{
  "prediction": "bearing_overgrease_churning",
  "confidence": 0.857,
  "model_version": "v1"
}
```

### 2. Submit Feedback
```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "features": [1.25, 1.08, 0.85],
    "original_prediction": "bearing_fit_loose",
    "corrected_label": "bearing_overgrease",
    "feedback_type": "correction",
    "notes": "Grease indicators elevated"
  }'
```

### 3. Simulate MQTT Sensor Data
```bash
# Send test sensor data
docker run --rm --network aastreli_aastreli-network \
  eclipse-mosquitto:2.0 \
  mosquitto_pub -h mqtt-broker -t "sensors/pump_01" \
  -m '{"sensor_id": "pump_01", "vibration": 1.25, "temp": 45.2, "pressure": 2.5}'
```

## 📊 Using the Dashboard

### Dashboard Features

1. **Real-time Monitoring**
   - Live sensor data visualization
   - Current system status
   - Prediction statistics

2. **Predictions Page**
   - Historical predictions
   - Confidence scores
   - Model versions

3. **Feedback Page**
   - Submit corrections
   - Report new faults
   - Mark false positives

4. **Settings Page**
   - Trigger retraining
   - System configuration

## 🔄 Common Operations

### View Logs
```bash
# All services
make logs

# Specific service
make logs-ml       # ML service
make logs-backend  # Backend API
make logs-mqtt     # MQTT ingestion
```

### Stop Services
```bash
make down
```

### Restart Services
```bash
make restart
```

### Check Status
```bash
make ps
```

## 🎓 Next Steps

### 1. Connect Your Real Sensors

Edit MQTT topics in `mqtt-ingestion/app/config.py`:
```python
MQTT_TOPICS = [
    "sensors/pump_01",
    "sensors/motor_01",
    "equipment/#"
]
```

### 2. Configure Your Equipment

Add sensors in MongoDB:
```javascript
db.sensors.insert({
  sensor_id: "your_pump_id",
  name: "Production Pump 1",
  type: "pump",
  location: "Building A"
})
```

### 3. Collect Feedback

Use the dashboard or API to submit corrections:
- Wrong predictions → Corrections
- New fault types → New fault discovery
- False alarms → False positive marking

### 4. Retrain Model

After collecting 10+ feedbacks:
```bash
# Via API
curl -X POST http://localhost:8000/retrain

# Via Dashboard
Settings → Trigger Model Retraining
```

## 🛠️ Troubleshooting

### Services Won't Start?
```bash
# Check Docker is running
docker ps

# Check port conflicts
sudo lsof -i :3000  # Frontend
sudo lsof -i :8000  # Backend
sudo lsof -i :8001  # ML Service
sudo lsof -i :1883  # MQTT
```

### ML Service Error?
```bash
# Check model files exist
ls ml-service/models/current/

# Check logs
docker-compose logs ml-service
```

### Can't Access Dashboard?
```bash
# Check frontend is running
docker-compose ps frontend

# Check frontend logs
docker-compose logs frontend
```

### MQTT Not Working?
```bash
# Test MQTT broker
docker run --rm --network aastreli_aastreli-network \
  eclipse-mosquitto:2.0 \
  mosquitto_sub -h mqtt-broker -t "#" -v
```

## 📚 Documentation

- **Full Deployment Guide**: `DEPLOYMENT_GUIDE.md`
- **Architecture Details**: `README.md`
- **API Documentation**: http://localhost:8000/docs

## 🆘 Need Help?

### Quick Fixes

**"Port already in use"**
```bash
# Kill process using the port
sudo kill $(sudo lsof -t -i:8000)
```

**"Model not loading"**
```bash
# Verify model files
ls -lh ml-service/models/current/
# Should show 3 files with reasonable sizes
```

**"MongoDB connection error"**
```bash
# Restart MongoDB
docker-compose restart mongodb
```

**"Frontend shows connection error"**
```bash
# Rebuild frontend with correct API URL
docker-compose up -d --build frontend
```

### Still Stuck?

1. Check logs: `make logs`
2. Check health: `make health`
3. Restart everything: `make restart`
4. Clean start: `make clean && make up`

## 🎉 Success Checklist

- [ ] All services running (`make ps`)
- [ ] Health checks pass (`make health`)
- [ ] Dashboard accessible (http://localhost:3000)
- [ ] Prediction API works (test curl command)
- [ ] MQTT data flowing (test mosquitto_pub)
- [ ] Feedback submission works

**All checked?** You're ready to go! 🚀

## ⚡ Quick Reference

```bash
# Start system
make up

# Stop system
make down

# View logs
make logs

# Check health
make health

# Backup database
make backup-db

# Access MongoDB
make shell-mongodb

# Retrain model
curl -X POST http://localhost:8000/retrain
```

---

**🎓 Pro Tip**: Bookmark http://localhost:8000/docs for quick API reference!

**💡 Remember**: The system learns from your feedback. The more you use it, the better it gets!
