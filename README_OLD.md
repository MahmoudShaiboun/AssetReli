# 🏗️ Aastreli - Industrial Anomaly Detection System

## 📋 System Architecture

Complete microservices architecture for real-time industrial fault detection with ML model API, MQTT data ingestion, and interactive feedback system.

## 🎯 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM ARCHITECTURE                               │
└──────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────┐
                    │   React Frontend     │
                    │   (Port 3000)        │
                    │   - Dashboard        │
                    │   - Real-time viz    │
                    │   - Feedback UI      │
                    └──────────┬───────────┘
                               │ HTTP/WebSocket
                    ┌──────────▼───────────┐
                    │   Backend API        │
                    │   (Port 8000)        │
                    │   - FastAPI          │
                    │   - REST endpoints   │
                    │   - WebSocket        │
                    └──┬────────┬─────┬────┘
                       │        │     │
       ┌───────────────┘        │     └─────────────────┐
       │                        │                        │
┌──────▼────────┐    ┌─────────▼──────────┐    ┌───────▼───────┐
│  ML Service   │    │  MQTT Ingestion    │    │   MongoDB     │
│  (Port 8001)  │    │  (Port 8002)       │    │  (Port 27017) │
│               │    │                    │    │               │
│ - Prediction  │    │ - Subscribe MQTT   │    │ - Sensor data │
│ - Retraining  │    │ - Data validation  │    │ - Predictions │
│ - Feedback    │    │ - Store to DB      │    │ - Feedback    │
│ - Versioning  │    │ - Real-time stream │    │ - Models      │
└───────────────┘    └──────────┬─────────┘    └───────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   MQTT Broker        │
                    │   (Port 1883)        │
                    │   - Mosquitto        │
                    │   - Topic routing    │
                    └──────────────────────┘
                                ▲
                                │
                    ┌───────────┴──────────┐
                    │   Industrial IoT     │
                    │   Sensors/PLCs       │
                    └──────────────────────┘
```

## 🔧 Services

### 1. ML Service (`ml-service/`)
**Purpose**: Core ML model for predictions and retraining

**Technology**: Python, FastAPI, XGBoost, Scikit-learn

**Endpoints**:
- `POST /predict` - Predict fault from sensor window
- `POST /predict-batch` - Batch predictions
- `POST /feedback` - Submit feedback for retraining
- `POST /retrain` - Trigger model retraining
- `GET /models` - List available model versions
- `GET /metrics` - Get model performance metrics

**Features**:
- Load trained XGBoost model
- Real-time predictions with confidence scores
- Feedback collection and storage
- Automatic retraining pipeline
- Model versioning and rollback
- Performance monitoring

### 2. MQTT Ingestion Service (`mqtt-ingestion/`)
**Purpose**: Ingest real-time sensor data from MQTT broker

**Technology**: Python, FastAPI, Paho-MQTT, MongoDB

**Endpoints**:
- `GET /status` - Service health check
- `GET /latest` - Get latest sensor readings
- `POST /simulate` - Simulate sensor data (testing)
- `WS /stream` - WebSocket for real-time data

**Features**:
- Subscribe to MQTT topics
- Validate and transform sensor data
- Store in MongoDB (time-series)
- Create sliding windows
- Trigger predictions via ML service
- Real-time streaming to frontend

### 3. Backend API (`backend-api/`)
**Purpose**: Main API gateway and business logic

**Technology**: Python, FastAPI, MongoDB

**Endpoints**:
- `GET /sensors` - Get sensor list and status
- `GET /predictions` - Get prediction history
- `GET /predictions/{id}` - Get specific prediction
- `POST /feedback` - Submit user feedback
- `GET /faults` - Get fault types and statistics
- `GET /dashboard` - Dashboard summary data
- `WS /realtime` - Real-time updates

**Features**:
- Centralized API gateway
- Business logic and validation
- Database queries and aggregations
- Authentication/Authorization (JWT)
- Rate limiting
- CORS handling

### 4. React Frontend (`frontend/`)
**Purpose**: Web dashboard for monitoring and feedback

**Technology**: React, TypeScript, Material-UI, Recharts

**Pages**:
- Dashboard - Real-time monitoring
- Predictions - Historical predictions
- Feedback - Submit corrections
- Analytics - Performance metrics
- Settings - System configuration

**Features**:
- Real-time sensor visualization
- Live prediction updates
- Interactive feedback forms
- Model performance charts
- Fault type management
- Responsive design

### 5. Database (`database/`)
**Purpose**: NoSQL data storage

**Technology**: MongoDB

**Collections**:
- `sensors` - Sensor metadata and config
- `sensor_data` - Time-series sensor readings
- `predictions` - Model predictions with confidence
- `feedback` - User feedback for retraining
- `models` - Model versions and metrics
- `faults` - Fault type definitions

## 📁 Project Structure

```
aastreli/
├── ml-service/                 # ML Model API
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app
│   │   ├── model.py           # Model loading/prediction
│   │   ├── retrain.py         # Retraining logic
│   │   ├── schemas.py         # Pydantic models
│   │   └── config.py          # Configuration
│   ├── models/                # Trained models
│   │   ├── current/
│   │   └── versions/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── mqtt-ingestion/            # MQTT Data Ingestion
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app
│   │   ├── mqtt_client.py    # MQTT subscriber
│   │   ├── processor.py      # Data processing
│   │   ├── schemas.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── backend-api/               # Main API Gateway
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app
│   │   ├── routes/           # API routes
│   │   │   ├── sensors.py
│   │   │   ├── predictions.py
│   │   │   └── feedback.py
│   │   ├── models/           # Database models
│   │   ├── schemas.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── frontend/                  # React Dashboard
│   ├── public/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API services
│   │   ├── hooks/           # Custom hooks
│   │   ├── types/           # TypeScript types
│   │   └── App.tsx
│   ├── package.json
│   ├── Dockerfile
│   └── README.md
│
├── database/                  # Database setup
│   ├── init/                 # Initialization scripts
│   │   └── init-mongo.js
│   └── README.md
│
├── shared/                    # Shared utilities
│   ├── schemas/              # Shared data schemas
│   └── utils/
│
├── docs/                      # Documentation
│   ├── API.md               # API documentation
│   ├── DEPLOYMENT.md        # Deployment guide
│   └── DEVELOPMENT.md       # Development guide
│
├── docker-compose.yml        # Orchestration
├── docker-compose.dev.yml    # Development setup
├── .env.example             # Environment variables
├── Makefile                 # Common commands
└── README.md                # Main documentation
```

## 🔄 Data Flow

### 1. Real-time Prediction Flow
```
Sensor → MQTT Broker → MQTT Ingestion → MongoDB → ML Service → Prediction
                            │                          │
                            ↓                          ↓
                      Frontend (WebSocket) ←─── Backend API
```

### 2. Feedback and Retraining Flow
```
User → Frontend → Backend API → ML Service (Feedback Storage)
                                      │
                                      ↓
                             Periodic Retraining Job
                                      │
                                      ↓
                             New Model Version → Deploy
```

### 3. Historical Query Flow
```
Frontend → Backend API → MongoDB → Response
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- MongoDB 6+

### 1. Clone and Setup
```bash
cd aastreli
cp .env.example .env
# Edit .env with your configuration
```

### 2. Start All Services
```bash
# Development mode
docker-compose -f docker-compose.dev.yml up -d

# Production mode
docker-compose up -d
```

### 3. Access Services
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **ML Service**: http://localhost:8001
- **MQTT Ingestion**: http://localhost:8002
- **MongoDB**: mongodb://localhost:27017

### 4. Initialize Database
```bash
make init-db
```

### 5. Deploy ML Model
```bash
# Copy your trained model
cp /path/to/xgboost_anomaly_detector.json ml-service/models/current/
cp /path/to/label_encoder.pkl ml-service/models/current/
cp /path/to/feature_scaler.pkl ml-service/models/current/
```

## 🔧 Development

### Run Service Locally
```bash
# ML Service
cd ml-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# MQTT Ingestion
cd mqtt-ingestion
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# Backend API
cd backend-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm start
```

## 📊 Key Features

### Real-time Monitoring
- Live sensor data visualization
- Instant fault predictions
- Real-time alerts
- WebSocket updates

### ML Model Management
- Model versioning (v1, v2, v3...)
- A/B testing support
- Rollback capabilities
- Performance tracking

### Feedback System
- Interactive feedback collection
- Automatic retraining pipeline
- Version comparison
- Audit trail

### Data Management
- Time-series sensor data
- Efficient querying
- Data retention policies
- Backup and restore

## 🔐 Security

- JWT authentication
- API rate limiting
- MQTT TLS/SSL support
- MongoDB authentication
- CORS configuration
- Environment-based secrets

## 📈 Scalability

- Horizontal scaling for ML service
- Load balancing ready
- Database replication
- Caching layer (Redis optional)
- Message queue (RabbitMQ optional)

## 🧪 Testing

```bash
# Backend tests
make test-backend

# Frontend tests
make test-frontend

# Integration tests
make test-integration
```

## 📦 Deployment

### Docker Swarm
```bash
docker stack deploy -c docker-compose.yml aastreli
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

## 🔍 Monitoring

- Prometheus metrics
- Grafana dashboards
- Health check endpoints
- Logging (ELK stack optional)

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger)
- **Development Guide**: `docs/DEVELOPMENT.md`
- **Deployment Guide**: `docs/DEPLOYMENT.md`
- **Architecture Details**: `docs/ARCHITECTURE.md`

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Write tests
4. Submit pull request

## 📄 License

MIT License

## 🆘 Support

- Documentation: `docs/`
- Issues: GitHub Issues
- Email: support@aastreli.com

---

**Built for production-ready industrial IoT anomaly detection** 🏭🤖
