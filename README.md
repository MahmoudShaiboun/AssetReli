# 🏭 Aastreli - Industrial Anomaly Detection System

**Complete microservices architecture for real-time fault detection with ML, MQTT, and interactive feedback**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688)](https://fastapi.tiangolo.com/)

## 🎯 What is Aastreli?

Aastreli is a production-ready system for industrial equipment monitoring that:

- 📡 **Ingests real-time sensor data** from MQTT streams
- 🤖 **Predicts equipment faults** using XGBoost ML models  
- 📊 **Visualizes data** through an interactive React dashboard
- 🔄 **Learns continuously** from user feedback and retrains automatically
- 💾 **Stores everything** in MongoDB for analysis and compliance

## ⚡ Quick Start (5 Minutes)

```bash
# 1. Navigate to project directory
cd <your-project-directory>

# 2. Setup (if .env.example exists, copy it)
cp .env.example .env  # Optional
make init

# 2. Deploy your ML model
cp /path/to/xgboost_anomaly_detector.json ml-service/models/current/
cp /path/to/label_encoder.pkl ml-service/models/current/
cp /path/to/feature_scaler.pkl ml-service/models/current/

# 3. Start everything
make build && make up

# 4. Access the dashboard
open http://localhost:3000
```

**See [QUICKSTART.md](QUICKSTART.md) for detailed instructions**

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    AASTRELI SYSTEM                            │
└──────────────────────────────────────────────────────────────┘

            ┌────────────────────┐
            │  React Frontend    │  
            │  localhost:3000    │
            └─────────┬──────────┘
                      │ HTTP/WebSocket
            ┌─────────▼──────────┐
            │   Backend API      │
            │  localhost:8000    │
            └┬──────┬─────┬─────┘
             │      │     │
    ┌────────┘      │     └────────┐
    │               │              │
┌───▼───┐    ┌─────▼─────┐    ┌──▼────┐
│  ML   │    │   MQTT    │    │MongoDB│
│Service│    │ Ingestion │    │  DB   │
│ :8001 │    │   :8002   │    │ :27017│
└───────┘    └─────┬─────┘    └───────┘
                   │
            ┌──────▼───────┐
            │ MQTT Broker  │
            │   :1883      │
            └──────────────┘
                   ▲
            ┌──────┴───────┐
            │   IoT        │
            │  Sensors     │
            └──────────────┘
```

## 📦 Services

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 3000 | React dashboard for monitoring |
| **Backend API** | 8000 | Main REST API gateway |
| **ML Service** | 8001 | Model predictions & retraining |
| **MQTT Ingestion** | 8002 | Real-time data collector |
| **MongoDB** | 27017 | NoSQL database |
| **MQTT Broker** | 1883 | Message queue |

## ✨ Features

### 🔮 Real-time Prediction
- Instant fault detection from sensor streams
- Confidence scoring for all predictions
- Top-K alternative predictions
- Model version tracking

### 🎯 Interactive Feedback
- **Correct misclassifications**: Submit the right label
- **Add new faults**: Discover unknown fault types
- **Mark false positives**: Reduce false alarms
- **Track improvements**: See accuracy gains over time

### 🔄 Automatic Retraining
- Collect feedback from users
- Trigger retraining with 10+ samples
- Version control for models
- A/B testing support
- Rollback capability

### 📊 Dashboard
- Real-time sensor visualization
- Prediction history
- Feedback submission form
- Model performance metrics
- System health monitoring

### 💾 Data Management
- Time-series sensor data storage
- Prediction history
- Feedback audit trail
- Model versioning

## 🚀 Usage

### Make Predictions

**Via API:**
```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [1.25, 1.08, ...]}'
```

**Via Python:**
```python
import requests

response = requests.post(
    "http://localhost:8001/predict",
    json={"features": [1.25, 1.08, 0.85, ...]}
)
print(response.json())
```

### Submit Feedback

**Via Dashboard:**
1. Go to Feedback page
2. Select feedback type
3. Enter original and corrected labels
4. Submit

**Via API:**
```bash
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "original_prediction": "bearing_fit_loose",
    "corrected_label": "bearing_overgrease",
    "feedback_type": "correction"
  }'
```

### Trigger Retraining

**Via Dashboard:**
- Settings → Trigger Model Retraining

**Via API:**
```bash
curl -X POST http://localhost:8000/retrain
```

## 🔄 Data Flow

### 1. Real-time Prediction
```
Sensor → MQTT → Ingestion → MongoDB
                    ↓
                ML Service → Prediction
                    ↓
              Backend API → Frontend
```

### 2. Feedback Loop
```
User → Frontend → Backend → ML Service
                              ↓
                     Store Feedback
                              ↓
                    Periodic Retraining
                              ↓
                      New Model Version
```

## 🛠️ Development

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- MongoDB 6+

### Local Development

**Backend Services:**
```bash
cd ml-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install
npm start
```

### Running Tests

```bash
make test
```

## 📊 API Documentation

Once running, visit:
- **Backend API**: http://localhost:8000/docs
- **ML Service**: http://localhost:8001/docs
- **MQTT Ingestion**: http://localhost:8002

Interactive Swagger documentation available for all services.

## 🔐 Security

### Development
- Open MQTT broker (no auth)
- No API authentication
- CORS enabled for localhost

### Production
Configure in `.env`:
```bash
# Enable JWT authentication
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256

# Enable MQTT authentication
MQTT_USERNAME=mqtt_user
MQTT_PASSWORD=secure_password

# MongoDB authentication
MONGODB_USERNAME=admin
MONGODB_PASSWORD=secure_password
```

## 📈 Monitoring

### Health Checks
```bash
make health
```

### View Logs
```bash
make logs              # All services
make logs-ml          # ML service only
make logs-backend     # Backend only
```

### Database Access
```bash
make shell-mongodb
```

## 🔄 Operations

### Backup Database
```bash
make backup-db
```

### Restore Database
```bash
make restore-db FILE=backup_20260130.archive
```

### Update ML Model
```bash
# Copy new model files
cp new_model.json ml-service/models/current/xgboost_anomaly_detector.json

# Restart ML service
docker-compose restart ml-service
```

## 📁 Project Structure

```
aastreli/
├── ml-service/              # ML model API
│   ├── app/
│   │   ├── main.py         # FastAPI app
│   │   ├── model.py        # Model manager
│   │   ├── retrain.py      # Retraining pipeline
│   │   └── schemas.py      # Pydantic models
│   ├── models/             # Trained models
│   └── Dockerfile
├── mqtt-ingestion/         # MQTT data collector
│   ├── app/
│   │   ├── main.py
│   │   └── mqtt_client.py
│   └── Dockerfile
├── backend-api/            # Main API gateway
│   ├── app/
│   │   ├── main.py
│   │   └── routes/
│   └── Dockerfile
├── frontend/               # React dashboard
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── Dockerfile
├── database/              # MongoDB setup
│   └── init/
├── docker-compose.yml     # Orchestration
├── Makefile              # Common commands
├── QUICKSTART.md         # Quick start guide
├── DEPLOYMENT_GUIDE.md   # Full deployment docs
└── README.md            # This file
```

## 🎓 Documentation

- **[Quick Start](QUICKSTART.md)** - Get running in 5 minutes
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment
- **[API Docs](http://localhost:8000/docs)** - Interactive API reference

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🆘 Support

- **Documentation**: Check QUICKSTART.md and DEPLOYMENT_GUIDE.md
- **API Help**: Visit http://localhost:8000/docs
- **Issues**: GitHub Issues
- **Email**: support@aastreli.com

## 🙏 Acknowledgments

Built with:
- FastAPI - Modern Python web framework
- React - Frontend framework
- XGBoost - ML library
- MongoDB - NoSQL database
- MQTT - IoT messaging protocol
- Docker - Containerization

---

**Made with ❤️ for Industrial IoT**

🚀 **Get Started**: Run `make up` and visit http://localhost:3000
📚 **Learn More**: See [QUICKSTART.md](QUICKSTART.md)
🛠️ **Deploy**: Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
