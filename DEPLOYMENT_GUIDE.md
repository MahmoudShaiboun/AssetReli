# 🚀 Aastreli Deployment Guide

Complete guide to deploy the Aastreli Industrial Anomaly Detection System.

## 📋 Prerequisites

### Required Software
- Docker 20.10+ and Docker Compose 2.0+
- Python 3.10+ (for local development)
- Node.js 18+ (for frontend development)
- Git

### Required Models
You need trained ML models from your notebook:
- `xgboost_anomaly_detector.json`
- `label_encoder.pkl`
- `feature_scaler.pkl`

## 🎯 Quick Start (5 minutes)

### 1. Navigate to Project and Setup
```bash
# Navigate to your project directory
cd <your-project-directory>

# Copy environment file (if .env.example exists)
cp .env.example .env  # Optional

make init
```

### 2. Deploy ML Models
```bash
# Copy your trained models
cp /path/to/xgboost_anomaly_detector.json ml-service/models/current/
cp /path/to/label_encoder.pkl ml-service/models/current/
cp /path/to/feature_scaler.pkl ml-service/models/current/
```

### 3. Start All Services
```bash
make build
make up
```

### 4. Verify Deployment
```bash
make health
```

Expected output:
```
🏥 Health Check:
✓ Backend API: healthy
✓ ML Service: healthy  
✓ MQTT Ingestion: healthy
```

### 5. Access Services
- **Frontend Dashboard**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **ML Service Docs**: http://localhost:8001/docs
- **MQTT Ingestion**: http://localhost:8002

## 🔧 Detailed Setup

### Environment Configuration

Edit `.env` file:
```bash
# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=aastreli

# MQTT Broker
MQTT_BROKER_HOST=mqtt-broker
MQTT_BROKER_PORT=1883

# ML Service
MIN_FEEDBACK_FOR_RETRAIN=10
AUTO_RETRAIN_ENABLED=false

# Frontend
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8002
```

### Service Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React)                         Port 3000         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Backend API (FastAPI)                    Port 8000         │
└───┬─────────────┬─────────────┬───────────────────────────┘
    │             │             │
┌───▼──────┐  ┌──▼────────┐  ┌─▼──────────┐
│ML Service│  │MQTT Ingest│  │  MongoDB   │
│Port 8001 │  │Port 8002  │  │ Port 27017 │
└──────────┘  └─────┬─────┘  └────────────┘
                    │
              ┌─────▼─────┐
              │MQTT Broker│
              │Port 1883  │
              └───────────┘
```

## 📊 Testing the System

### 1. Test ML Service
```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [1.25, 1.08, 0.85'$(python3 -c "print(',1.0'*333)")']}'
```

Expected response:
```json
{
  "prediction": "bearing_overgrease_churning",
  "confidence": 0.857,
  "top_predictions": [...]
}
```

### 2. Submit Feedback
```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "features": [1.25, 1.08'$(python3 -c "print(',1.0'*334)")'],
    "original_prediction": "bearing_fit_loose_housing",
    "corrected_label": "bearing_overgrease_churning",
    "feedback_type": "correction",
    "confidence": 0.78,
    "notes": "Grease indicators elevated"
  }'
```

### 3. Trigger Retraining
```bash
curl -X POST http://localhost:8000/retrain
```

### 4. Test MQTT (Simulated Sensor Data)
```bash
# Publish test data to MQTT broker
docker run --rm --network aastreli_aastreli-network \
  eclipse-mosquitto:2.0 \
  mosquitto_pub -h mqtt-broker -t "sensors/pump_01" \
  -m '{"sensor_id": "pump_01", "vibration": 1.25, "temperature": 45.2}'
```

## 🔄 Operations

### View Logs
```bash
# All services
make logs

# Specific service
make logs-ml
make logs-backend
make logs-mqtt
```

### Database Operations
```bash
# Backup database
make backup-db

# Restore database
make restore-db FILE=backup_20260130_120000.archive

# Access MongoDB shell
make shell-mongodb
```

### Service Management
```bash
# Restart all services
make restart

# Stop services
make down

# Clean everything (⚠️ deletes data)
make clean
```

## 🏭 Production Deployment

### Security Hardening

1. **Enable Authentication**
```bash
# Edit .env
JWT_SECRET=your-super-secret-key-change-this
```

2. **MQTT Authentication**
```bash
# Create password file
docker-compose exec mqtt-broker mosquitto_passwd -c /mosquitto/config/passwd username

# Edit mqtt-broker/config/mosquitto.conf
allow_anonymous false
password_file /mosquitto/config/passwd
```

3. **MongoDB Authentication**
```yaml
# docker-compose.yml
services:
  mongodb:
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: secure_password
```

### Scaling

#### Horizontal Scaling
```bash
# Scale ML service
docker-compose up -d --scale ml-service=3

# Add load balancer (nginx)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

#### Resource Limits
```yaml
# docker-compose.yml
services:
  ml-service:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Monitoring

#### Health Checks
```yaml
# docker-compose.yml
services:
  backend-api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Prometheus Metrics (Optional)
```bash
# Add Prometheus + Grafana
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

## 🐛 Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
sudo lsof -i :8000

# Kill the process or change port in docker-compose.yml
```

#### ML Service Can't Load Model
```bash
# Check models directory
ls -la ml-service/models/current/

# Verify files exist:
# - xgboost_anomaly_detector.json
# - label_encoder.pkl
# - feature_scaler.pkl

# Check logs
docker-compose logs ml-service
```

#### MongoDB Connection Failed
```bash
# Check MongoDB is running
docker-compose ps mongodb

# Check logs
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb
```

#### MQTT Connection Issues
```bash
# Test MQTT connection
docker run --rm --network aastreli_aastreli-network \
  eclipse-mosquitto:2.0 \
  mosquitto_sub -h mqtt-broker -t "#" -v

# Check broker logs
docker-compose logs mqtt-broker
```

#### Frontend Can't Connect to API
```bash
# Check CORS settings in backend-api/app/config.py
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://frontend:3000"
]

# Rebuild backend
docker-compose up -d --build backend-api
```

## 📈 Performance Tuning

### Database Optimization
```javascript
// MongoDB indexes
db.sensor_data.createIndex({ "timestamp": -1 })
db.sensor_data.createIndex({ "data.sensor_id": 1, "timestamp": -1 })
db.predictions.createIndex({ "timestamp": -1 })
```

### ML Service Optimization
```python
# app/config.py
XGBOOST_N_ESTIMATORS = 300  # Reduce for faster predictions
XGBOOST_MAX_DEPTH = 7       # Reduce model complexity
```

### MQTT Optimization
```
# mqtt-broker/config/mosquitto.conf
max_queued_messages 10000
max_inflight_messages 100
```

## 🔄 Updating the System

### Update ML Model
```bash
# Copy new model files
cp new_model.json ml-service/models/current/xgboost_anomaly_detector.json

# Restart ML service
docker-compose restart ml-service
```

### Update Code
```bash
# Pull latest changes
git pull

# Rebuild and restart
make build
make restart
```

### Database Migration
```bash
# Create backup first
make backup-db

# Run migration scripts
docker-compose exec mongodb mongosh aastreli < migrations/001_add_indexes.js
```

## 🎓 Next Steps

1. **Configure MQTT Topics**: Edit `mqtt-ingestion/app/config.py`
2. **Customize Frontend**: Modify `frontend/src/` components
3. **Add Authentication**: Implement JWT in backend API
4. **Set Up Monitoring**: Deploy Prometheus + Grafana
5. **Configure Alerts**: Set up email/SMS notifications
6. **Scale Services**: Add load balancers and replicas

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Architecture Diagram**: See `README.md`
- **Development Guide**: See `DEVELOPMENT.md`
- **Support**: GitHub Issues

---

**Need help?** Check the troubleshooting section or open an issue on GitHub.
