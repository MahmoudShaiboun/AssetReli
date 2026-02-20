# Aastreli - Architecture Review & Refactoring Plan

> **Author:** Claude (AI-assisted review)
> **Date:** 2026-02-16
> **Status:** Proposal — awaiting team decision
> **Reference:** [`docs/reference_erd.md`](./reference_erd.md)

---

## Table of Contents

1. [Part 1: Current System Flow Review](#part-1-current-system-flow-review)
2. [Part 2: Identified Issues & Pain Points](#part-2-identified-issues--pain-points)
3. [Part 3: Recommended Refactored Architecture](#part-3-recommended-refactored-architecture)
4. [Part 4: Implementation Roadmap](#part-4-implementation-roadmap)

---

## Part 1: Current System Flow Review

### 1.1 End-to-End Data Flow (Happy Path)

```
┌──────────────┐    MQTT     ┌───────────────┐   HTTP POST   ┌────────────────┐
│  IoT Sensors │───────────→ │ Mosquitto     │               │                │
│  (simulate_  │  topics:    │ Broker :1883  │               │  ML Service    │
│   sensors.py)│  sensors/#  └───────┬───────┘               │  :8001         │
└──────────────┘  equipment/#        │                        │                │
                                     │ paho-mqtt subscribe    │  XGBoost model │
                                     ▼                        │  (336 features)│
                           ┌─────────────────┐                └───────┬────────┘
                           │ MQTT Ingestion   │   POST /predict       │
                           │ Service :8002    │──────────────────────→ │
                           │                  │←──────────────────────-│
                           │ • _store_data()  │  {prediction,         │
                           │ • sliding window │   confidence,         │
                           │ • 14-sample buf  │   top_predictions}    │
                           └────────┬─────────┘                       │
                                    │                                  │
                          ┌─────────▼─────────┐                       │
                          │    MongoDB :27017  │                       │
                          │                    │                       │
                          │ sensor_data (raw)  │                       │
                          │ sensor_readings    │                       │
                          │   (+ prediction +  │                       │
                          │    confidence)     │                       │
                          │ users              │                       │
                          │ user_settings      │                       │
                          │ feedback           │                       │
                          │ predictions        │                       │
                          └─────────▲─────────┘                       │
                                    │                                  │
                           ┌────────┴────────┐                        │
                           │  Backend API    │    POST /feedback       │
                           │  :8000          │───────────────────────→ │
                           │                 │    POST /retrain        │
                           │ • Auth (JWT)    │───────────────────────→ │
                           │ • CRUD sensors  │                        │
                           │ • Dashboard     │                        │
                           │ • Proxy predict │                        │
                           │ • Proxy feedbk  │                        │
                           └────────▲────────┘
                                    │ Axios + JWT
                           ┌────────┴────────┐
                           │  React Frontend │
                           │  :3000          │
                           │                 │
                           │ + WebSocket ────────→  mqtt-ingestion /stream
                           └─────────────────┘
```

### 1.2 Detailed Step-by-Step Flow

#### Step 1 — Sensor publishes data via MQTT

A sensor (or `simulate_sensors.py`) publishes a JSON payload to a topic like `sensors/data` or `sensors/pump_01`. The payload contains 24 sensor channels (motor/pump vibration bands, ultrasonic, temperature).

#### Step 2 — MQTT Ingestion receives the message

`MQTTClient._on_message()` (`mqtt-ingestion/app/mqtt_client.py:89`) fires on the paho-mqtt callback thread. It:
1. Parses JSON payload
2. Stores in `self.latest_data` (in-memory cache for WebSocket streaming)
3. Schedules `_store_data()` as an async coroutine on the FastAPI event loop via `asyncio.run_coroutine_threadsafe()`

#### Step 3 — Raw data stored in MongoDB

`_store_data()` (`mqtt_client.py:122`) inserts the raw message into the `sensor_data` collection:
```python
document = {"topic": topic, "data": data, "timestamp": timestamp}
await self.db.sensor_data.insert_one(document)
```

#### Step 4 — Sliding window feature engineering

For complex sensor data (detected by presence of `motor_DE_vib_band_1` key):
1. Extracts 24 features from the current reading (`_extract_24_features_from_data()`, line 319)
2. Appends to a per-sensor sliding window buffer (`self.sensor_windows[sensor_id]`)
3. Maintains a window of 14 timesteps (FIFO eviction)
4. Once the window is full (14 samples), computes **336 statistical features** (24 sensors x 14 statistics each): mean, std, min, max, median, Q25, Q75, range, variance, RMS, MAD, sum, sum-of-squares, max/min ratio

For simple sensor data (temperature/vibration/pressure/humidity):
- Creates a 4-feature vector and zero-pads to 336

#### Step 5 — ML prediction via HTTP

`_get_ml_prediction()` (`mqtt_client.py:492`) sends a POST to `ml-service:8001/predict`:
```json
{"features": [336 floats], "top_k": 3}
```

The ML service (`ml-service/app/main.py:173`):
1. Receives the 336-feature vector
2. Scales features via `StandardScaler` (`model.py:95`)
3. Runs `XGBClassifier.predict()` and `.predict_proba()` (`model.py:98-99`)
4. Returns the top label, confidence, and top-K predictions with the active model version

#### Step 6 — Sensor reading + prediction stored in MongoDB

Back in `_store_data()`, the structured sensor reading (with nested `motor_data`, `pump_data`) is written to the `sensor_readings` collection, **including the ML prediction label and confidence** (`mqtt_client.py:209-246`).

The prediction is **not** stored in a separate `predictions` collection by the ingestion service — it is embedded in the `sensor_readings` document.

#### Step 7 — Alert triggered if anomaly detected

If `prediction != "normal"` AND `confidence > 0.6`, `_trigger_fault_alert()` fires (`mqtt_client.py:249`):
1. Calls `backend-api /settings/all-users` to fetch every user's notification settings
2. For each user whose `anomalyThreshold <= confidence`, iterates their enabled `faultActions`
3. Dispatches via `NotificationService` (email/SMS/webhook/Slack)

#### Step 8 — Frontend reads data

- **Dashboard**: `GET /dashboard` on backend-api queries latest 20 `sensor_readings` with predictions
- **Real-time**: WebSocket to `mqtt-ingestion:8002/stream` pushes `latest_data` every 1 second
- **Predictions page**: `GET /predictions` on backend-api (note: this collection is populated only by the `/predictions` POST endpoint, NOT by the ingestion flow)

#### Step 9 — Feedback loop

1. User submits feedback via frontend → `POST /feedback` on backend-api
2. Backend-api stores in MongoDB `feedback` collection **and** forwards to `ml-service /feedback`
3. ML service stores in local pickle file (`feedback_data.pkl`) via `RetrainingPipeline`
4. When feedback count >= `MIN_FEEDBACK_FOR_RETRAIN` (default 10), user can trigger `POST /retrain`
5. ML service retrains XGBoost on feedback data, saves new version under `models/versions/vN/`
6. User can activate any version via `POST /models/{version}/activate`

---

### 1.3 MongoDB Collections (Current State)

| Collection | Written by | Read by | Purpose |
|---|---|---|---|
| `sensor_data` | mqtt-ingestion | backend-api | Raw MQTT payloads (append-only) |
| `sensor_readings` | mqtt-ingestion | backend-api, frontend | Structured readings + ML prediction |
| `predictions` | backend-api (manual POST) | backend-api | On-demand predictions (rarely used) |
| `feedback` | backend-api | — | User feedback records |
| `users` | backend-api | backend-api | User accounts (hashed passwords) |
| `user_settings` | backend-api | backend-api, mqtt-ingestion | Per-user notification settings |
| `sensors` | backend-api | backend-api | Sensor registry |
| `faults` | init script | — | Fault type catalog (seed data) |
| `models` | init script | — | Created but not used in code |

---

## Part 2: Identified Issues & Pain Points

### 2.1 Architectural Issues

| # | Issue | Severity | Location |
|---|---|---|---|
| A1 | **Monolithic main.py in backend-api** — Auth, settings, sensors, predictions, feedback, dashboard, notifications all in one 500-line file | High | `backend-api/app/main.py` |
| A2 | **No separation between business data and streaming data** — Users, settings, sensors, and feedback share the same MongoDB as high-throughput sensor readings | High | All services |
| A3 | **mqtt-ingestion directly calls backend-api for notification settings** — Tight coupling between ingestion and API layer; if API is down, alerts fail silently | Medium | `mqtt_client.py:273` |
| A4 | **Dual storage of feedback** — Feedback is stored in both MongoDB (by backend-api) and a local pickle file (by ml-service); they can drift apart | Medium | `backend-api/main.py:384`, `ml-service/retrain.py:92` |
| A5 | **No tenant/organization model** — Users exist but have no tenant isolation; all data is global | High | Entire system |
| A6 | **`predictions` collection is orphaned from the ingestion flow** — The ingestion service writes predictions inline in `sensor_readings`, while `POST /predictions` writes to a separate `predictions` collection that nobody reads in the main flow | Low | `backend-api/main.py:323` |
| A7 | **`_extract_features_from_complex_data()` uses `random.uniform()`** — The full_features field stored in sensor_readings contains random padding, making it non-deterministic and useless for later analysis | High | `mqtt_client.py:468-469` |
| A8 | **No Site/Gateway/Asset hierarchy** — The reference ERD defines Tenant → Site → Gateway → Asset → Sensor. The current system has only a flat sensor list with no asset or site grouping | High | Entire system |
| A9 | **No ML model lifecycle** — Reference ERD defines MLModel → MLModelVersion → MLModelDeployment → AssetModelVersion (per-asset model binding). Current system tracks only a version string on the filesystem | High | `ml-service/` |
| A10 | **No alarm rules engine** — Reference ERD defines AlarmRule (threshold-based rules per sensor/asset). Current system hardcodes `confidence > 0.6` in mqtt-ingestion | Medium | `mqtt_client.py:249` |
| A11 | **No maintenance work orders** — Reference ERD includes MaintenanceWorkOrder tied to AlarmEvent. Current system has no concept of follow-up actions | Medium | — |

### 2.2 mqtt-ingestion — Deep Review

The ingestion service is the **hottest path** in the system (every sensor message flows through it), yet it has zero awareness of tenants, assets, or model routing. This section catalogues every gap.

#### 2.2.1 Current File Structure

```
mqtt-ingestion/app/
├── __init__.py
├── config.py           # Settings: broker, topics, mongo, service URLs
├── main.py             # FastAPI app, lifespan, WebSocket /stream, /health, /latest
├── mqtt_client.py      # MQTTClient class: subscribe, store, predict, alert (517 lines)
└── notifications.py    # NotificationService: email, SMS, webhook, Slack
```

Everything lives in one `MQTTClient` class — topic parsing, feature engineering, MongoDB writes, ML calls, alert dispatch.

#### 2.2.2 Multi-Tenancy Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| I1 | **MQTT topics have no tenant prefix** — subscribes to `sensors/#` and `equipment/#` globally. No way to tell which tenant a message belongs to. | All data is mixed; impossible to isolate tenants | `config.py:12`, `mqtt_client.py:83-85` |
| I2 | **`sensor_windows` keyed by flat `sensor_id`** — e.g. `"pump_01"`. Two tenants with the same sensor ID will share the same sliding window, cross-contaminating predictions | Data corruption between tenants | `mqtt_client.py:30`, `mqtt_client.py:148-160` |
| I3 | **`latest_data` is a global dict keyed by topic** — WebSocket `/stream` broadcasts every tenant's data to every connected client | Tenant data leak | `mqtt_client.py:25`, `main.py:87-88` |
| I4 | **MongoDB documents have no `tenant_id`** — `sensor_data` and `sensor_readings` inserts include only `topic`, `data`, `sensor_id`. No tenant/site/asset context | Can't query by tenant; can't enforce isolation | `mqtt_client.py:131-136`, `mqtt_client.py:200-246` |
| I5 | **No topic→tenant resolution** — there's no lookup from the MQTT topic or payload to a (tenant_id, site_id, asset_id, sensor_id) tuple. The service doesn't read the sensor registry from PostgreSQL (or MongoDB) | Every downstream operation is tenant-blind | Entire `mqtt_client.py` |

#### 2.2.3 ML-Management Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| I6 | **Single global ML endpoint** — `_get_ml_prediction()` calls `ml-service:8001/predict` with only `{features, top_k}`. No tenant_id, no asset_id, no model_version_id | Can't route to per-asset or per-tenant model versions (AssetModelVersion in ERD) | `mqtt_client.py:492-508` |
| I7 | **`model_version_id` not stored in predictions** — the ML service returns `model_version` in the response, but mqtt-ingestion ignores it and never writes it to MongoDB | Can't trace which model version made a prediction; breaks the ERD's Prediction.ModelVersionId FK | `mqtt_client.py:172-175` |
| I8 | **No asset-model binding awareness** — the reference ERD has `AssetModelVersion` that binds a specific model version to an asset. mqtt-ingestion should look up which model version is deployed for this asset before calling the ML service | All assets use the same model; no staged rollout or A/B testing possible | — (missing entirely) |
| I9 | **`_extract_features_from_complex_data()` uses `random.uniform()`** — 273 out of 336 features are random noise, stored in `full_features` field | Stored features are non-deterministic; useless for retraining, replay, or audit | `mqtt_client.py:468-469` |

#### 2.2.4 Auth & Security Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| I10 | **No auth on any HTTP endpoint** — `/latest`, `/health`, `/stream` are all open | Anyone can read live sensor data | `main.py:53-93` |
| I11 | **No API key for outbound calls** — calls to `ml-service /predict` and `backend-api /settings/all-users` have zero authentication | Unauthenticated inter-service communication; any network participant can impersonate | `mqtt_client.py:274-276`, `mqtt_client.py:495-499` |
| I12 | **WebSocket `/stream` has no auth and no tenant scoping** — accepts any connection, sends all data | Must require JWT, then filter stream to the user's tenant only | `main.py:77-93` |

#### 2.2.5 Operational Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| I13 | **`httpx.AsyncClient()` created per request** — `async with httpx.AsyncClient()` on every ML prediction creates/destroys TCP connections | High latency, connection exhaustion under load | `mqtt_client.py:495` |
| I14 | **No circuit breaker** — if ml-service is slow or down, every MQTT message blocks on a 5-second HTTP timeout | Backpressure cascades; message processing stalls | `mqtt_client.py:499` |
| I15 | **`_trigger_fault_alert()` directly calls backend-api** — tight coupling; if API is down, alert is lost silently. Also no tenant context in the alert | Lost alerts; alert goes to ALL tenants' users, not just the sensor's tenant | `mqtt_client.py:255-317` |
| I16 | **Alert threshold hardcoded** — `confidence > 0.6` is baked into code instead of coming from `AlarmRule` in PG (per tenant/asset/sensor) | Can't customize alert sensitivity per asset or tenant | `mqtt_client.py:249` |
| I17 | **No PostgreSQL connection** — mqtt-ingestion only connects to MongoDB. It can't look up the sensor registry, alarm rules, or asset-model bindings | Must add PG read-only connection for context resolution | `config.py` (no `POSTGRES_URL`) |

### 2.3 ml-service — Deep Review

The ML service is the **prediction engine** of the system — every sensor reading ultimately flows through it. Yet it operates as a singleton with no awareness of tenants, assets, or model lifecycle management. This section catalogues every gap.

#### 2.3.1 Current File Structure

```
ml-service/app/
├── __init__.py
├── config.py           # Settings: model paths, XGBoost hyperparams, retraining thresholds
├── main.py             # FastAPI app, feature conversion, all endpoints (460 lines)
├── model.py            # ModelManager: load, predict, version management (258 lines)
├── retrain.py          # RetrainingPipeline: feedback storage + XGBoost retrain (239 lines)
└── schemas.py          # Pydantic models: PredictionRequest (24 sensor fields), FeedbackRequest, etc.

ml-service/models/
├── current/            # Active model files (loaded at startup)
│   ├── xgboost_anomaly_detector.json   (7.2 MB)
│   ├── label_encoder.pkl               (4.9 KB)
│   ├── feature_scaler.pkl              (5.7 KB)
│   ├── anomaly_detection_artifacts.pkl (8.5 MB)
│   └── fault_definitions.json          (3.1 KB)
└── versions/           # Saved model versions (currently empty)

ml-service/feedback_data/
├── feedback_data.pkl   # Pickled feedback samples (29 entries, 81 KB)
└── feedback_log.json   # Summary: total, corrections, new_faults, false_positives, retraining_history
```

Everything runs as a single-model singleton: one `ModelManager` instance loads one set of artifacts from disk and serves all requests.

#### 2.3.2 Multi-Tenancy Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| M1 | **No `tenant_id` in any request or response** — `/predict`, `/feedback`, `/retrain` are all tenant-blind. A prediction for Tenant A and Tenant B uses the same model and the same feedback pool | Can't serve tenant-specific models; all feedback is mixed | `main.py:173`, `schemas.py:15-49` |
| M2 | **Single global model in memory** — `ModelManager` loads exactly one XGBoost model at startup. No ability to load different models for different tenants or assets | All tenants/assets share one model; can't deploy per-asset model versions (reference ERD: `AssetModelVersion`) | `model.py:26-68`, `main.py:98-101` |
| M3 | **Feedback stored in a single pickle file** — All feedback regardless of tenant/model/asset goes into one `feedback_data.pkl`. No tenant isolation, no FK to model version or user | Cross-tenant feedback contamination; can't query feedback per tenant; no audit trail | `retrain.py:24-25`, `retrain.py:61-99` |
| M4 | **Retraining is global** — `retrain_model()` uses ALL accumulated feedback. No filtering by tenant, model, or asset. The retrained model replaces the global singleton | Retrain with Tenant A's data affects Tenant B's predictions; no scoped retraining | `retrain.py:115-238` |
| M5 | **Model versions are simple strings ("v1", "v2")** — No semantic versioning, no tenant namespace, no mapping to the ERD's `MLModel → MLModelVersion` hierarchy. Version number is just `len(retraining_history) + 2` | Can't track which tenant owns which model; breaks ERD FK requirements; no rollback tracking | `retrain.py:196-197`, `model.py:61-63` |

#### 2.3.3 Architecture Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| M6 | **Monolithic `main.py` (460 lines)** — Feature conversion, all 11 endpoints, global state management, startup logic, all in one file | Hard to test individual concerns; routing changes affect prediction logic | `main.py` |
| M7 | **`convert_structured_to_features()` duplicates 24 features × 14** — When structured sensor fields are provided (not a pre-built features array), it copies the same 24 values 14 times to reach 336 features. This is meant to simulate a 14-sample window but produces identical repeated values | Predictions from structured input are fundamentally different from sliding-window predictions; model sees no temporal variation | `main.py:30-87` (line 85: `features = features * 14`) |
| M8 | **Global mutable state** — `model_manager` and `retraining_pipeline` are module-level `None` variables set during lifespan. Async endpoints mutate shared state during retrain | Thread-safety risk during concurrent retrain + predict; no dependency injection | `main.py:27-28`, `main.py:97-115` |
| M9 | **`predict_batch` doesn't call `convert_structured_to_features()`** — Uses `req.features` directly, bypassing the structured-to-array conversion | Batch predictions with structured input will fail or produce wrong results | `main.py:229` |
| M10 | **No auth on any endpoint** — Anyone can call `/predict`, `/retrain`, `/models/{v}/activate`, `/feedback` | Unauthenticated model manipulation; anyone can retrain or swap the active model | All endpoints |
| M11 | **No circuit breaker or rate limiting** — Retraining is CPU-intensive (XGBoost fit) and can be triggered repeatedly via API while predictions are being served | Retrain blocks prediction latency; multiple concurrent retrains crash the service | `main.py:287-343` |
| M12 | **No database connection** — ML service reads/writes only local filesystem. No PostgreSQL connection for model version metadata, no MongoDB for reading feedback | Can't participate in the ERD's model lifecycle; feedback is isolated in pickle files | `config.py` (no `POSTGRES_URL`) |

#### 2.3.4 ML Pipeline Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| M13 | **Retraining uses only feedback data — catastrophic forgetting** — `retrain_model()` trains exclusively on the feedback dataset (currently 29 samples). The original training data (thousands of samples) is never loaded | New model overfits to 29 correction samples; forgets all other fault classes | `retrain.py:124-126` (comment: "For now, we'll just use feedback data") |
| M14 | **Scaler reused from old model during retrain** — After retraining, the old `feature_scaler.pkl` is saved with the new model. If the feedback data has different feature distributions, the stale scaler produces incorrect normalization | Feature scaling mismatch between training and inference on new model version | `retrain.py:200-204` |
| M15 | **No model artifact storage abstraction** — Model files are read/written to local disk paths. No abstraction layer for S3/MinIO/remote storage | Can't scale to cloud; model files are lost if container is recreated without volume mount | `model.py:30-54`, `model.py:226-257` |
| M16 | **Model activation copies files during live serving** — `activate_version()` uses `shutil.copy()` to overwrite files in `models/current/` while predictions are being served. No locking, no atomic swap | Brief window where model files are inconsistent; concurrent predict may load partial artifacts | `model.py:168-202` |
| M17 | **Feedback stats tracked in JSON log file, not queryable** — `feedback_log.json` has flat counters (total, corrections, new_faults, false_positives). No per-tenant, per-model, per-asset breakdown. No timestamps on individual feedback entries beyond the pickle | Can't answer "how many corrections were submitted for Model v2 on Asset pump_01 last week?" | `retrain.py:49-59`, `retrain.py:82-96` |

### 2.4 Operational Issues

| # | Issue | Severity | Location |
|---|---|---|---|
| O1 | **No service-to-service authentication** — mqtt-ingestion calls ml-service and backend-api without any auth; `/settings/all-users` is completely open | High | All inter-service calls |
| O2 | **No circuit breaker or retry for ML predictions** — If ml-service is slow, mqtt-ingestion blocks per-message | Medium | `mqtt_client.py:492` |
| O3 | **httpx client created per-request** — `async with httpx.AsyncClient()` on every ML prediction creates/destroys TCP connections | Medium | `mqtt_client.py:495` |
| O4 | **WebSocket /stream has no authentication** — Anyone can connect and receive all sensor data | Medium | `mqtt-ingestion/main.py:78` |
| O5 | **No TTL/retention on sensor_data or sensor_readings** — Unbounded growth in MongoDB | High | `init-mongo.js` |
| O6 | **ML retrain uses only feedback data, not original training data** — Catastrophic forgetting: the retrained model has seen only the small feedback set | High | `retrain.py:124-126` |

### 2.5 Frontend — Deep Review

The React frontend is the primary user interface for operators, engineers, and administrators. It currently operates as a flat, single-tenant dashboard with no awareness of the organizational hierarchy, no internationalization, and no pages for key ERD domains.

#### 2.5.1 Current File Structure

```
frontend/src/
├── App.tsx                        # Router: 9 routes, MUI ThemeProvider (light only)
├── index.tsx                      # ReactDOM entry
├── components/
│   ├── Layout.tsx                 # AppBar + permanent Drawer with 7 menu items + user menu
│   ├── ProtectedRoute.tsx         # Simple auth gate (checks localStorage token)
│   ├── PredictionCard.tsx         # Card component for single prediction
│   └── SensorCard.tsx             # Card component for single sensor
├── pages/
│   ├── Login.tsx                  # Email/password login form
│   ├── Register.tsx               # User registration form
│   ├── Dashboard.tsx              # Stats cards + 4 charts + recent predictions (455 lines)
│   ├── Sensors.tsx                # Flat sensor list + Add Sensor dialog
│   ├── RealtimeData.tsx           # WebSocket-driven live sensor table
│   ├── Predictions.tsx            # Historical ML predictions table
│   ├── FaultTypes.tsx             # Static 34-fault reference grid
│   ├── Feedback.tsx               # Select readings → submit correction feedback (479 lines)
│   └── Settings.tsx               # General settings + notification actions + retrain trigger (420 lines)
└── services/
    ├── api.ts                     # Axios instance + API functions + WebSocket helper
    └── auth.ts                    # AuthService class: login, register, token management
```

**Tech stack:** React 18 + TypeScript + MUI 5 + Recharts + Axios + React Router v6. No state management library, no i18n framework.

#### 2.5.2 Multi-Tenancy Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| F1 | **No tenant context anywhere** — JWT token has no `tenant_id` claim. No tenant-aware React context. Every API call is global | Users see all tenants' data; can't isolate views | Entire frontend |
| F2 | **All API calls are global** — `/dashboard`, `/sensor-readings`, `/predictions`, `/sensors` return data across all tenants. No `tenant_id` query parameter or header | Cross-tenant data leakage in the UI | `api.ts`, all pages |
| F3 | **No tenant/site selector** — No way for a user to select which tenant or site they're viewing. No breadcrumb showing Tenant → Site → Asset hierarchy | Users can't scope their view; admins managing multiple tenants are lost | `Layout.tsx` |
| F4 | **WebSocket has no auth and no tenant filter** — `connectWebSocket()` opens `ws://localhost:8002/stream` with no JWT token, receives all tenants' data | Any browser tab can listen to all sensor data; data leak | `api.ts:70-95`, `Dashboard.tsx:127`, `RealtimeData.tsx:63` |
| F5 | **No site/asset hierarchy in UI** — Sensors are a flat list with no grouping by site or asset. Dashboard charts show all sensors mixed together | Can't answer "show me all sensors on Asset X in Site Y" | `Sensors.tsx`, `Dashboard.tsx` |

#### 2.5.3 Multi-Language (i18n) Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| F6 | **All UI text is hardcoded English** — Every label, heading, button, tooltip, error message, and placeholder is inline English string | Can't localize to any other language without modifying every file | All `.tsx` files |
| F7 | **No i18n framework installed** — No `react-i18next`, `react-intl`, `formatjs`, or any localization library | No infrastructure to add translations; would require a full retrofit | `package.json` |
| F8 | **Fault type labels are hardcoded snake_case** — Both `FaultTypes.tsx` and `Feedback.tsx` define fault names as raw strings (`'bearing_overgrease_churn'`). Display is done with `.replace(/_/g, ' ').toUpperCase()` | Not translatable; display labels are derived from code identifiers | `FaultTypes.tsx:11-46`, `Feedback.tsx:47-82` |
| F9 | **Date/time uses browser default locale** — `toLocaleString()` and `toLocaleTimeString()` without explicit locale. No user-selectable date format (ISO, US, EU) | Inconsistent formatting across users; not controllable | `Dashboard.tsx:84`, `Feedback.tsx:255`, `RealtimeData.tsx:99` |
| F10 | **No RTL support** — MUI supports RTL but it's not configured. No `direction: 'rtl'` in theme for Arabic/Hebrew locales | Can't serve RTL-language users | `App.tsx:20-27` |

#### 2.5.4 Architecture Gaps

| # | Issue | Impact | Location |
|---|---|---|---|
| F11 | **No shared state management** — Each page fetches data independently with `useState`/`useEffect`. No React Context, Redux, or Zustand for shared state (current user, tenant, settings) | Redundant API calls; state lost on navigation; no cache | All pages |
| F12 | **Hardcoded API URL in `auth.ts`** — `const API_URL = 'http://localhost:8008'` instead of using `process.env.REACT_APP_API_URL`. Other pages also bypass the `api` service and use raw `axios` | Breaks in Docker/production; inconsistent request handling | `auth.ts:3`, `Feedback.tsx:105`, `Predictions.tsx:35` |
| F13 | **Mixed API patterns** — Some pages use `api.ts` functions (`getDashboard`, `getSensors`), others use raw `axios.get('http://localhost:8008/...')`. No consistent error handling | Duplicated code; JWT interceptor bypassed on raw axios calls | `Feedback.tsx:105-110`, `Predictions.tsx:35-37` |
| F14 | **No error boundary** — No `ErrorBoundary` component. An uncaught error in any component crashes the entire app with a white screen | Poor user experience on error | `App.tsx` |
| F15 | **No TypeScript interfaces shared across pages** — `SensorReading` is defined differently in `Feedback.tsx`, `Predictions.tsx`, and `Dashboard.tsx`. No shared `types/` directory | Type drift; fields may be missing or misnamed | Multiple pages |
| F16 | **Token stored in localStorage with no expiry check** — `ProtectedRoute` checks `isAuthenticated()` which only verifies token existence, not expiry. Expired JWTs get 401 on API call but user sees a broken UI, not a redirect | Silent auth failures; confusing UX | `auth.ts:68-70`, `ProtectedRoute.tsx:9` |
| F17 | **Flat folder structure** — All 9 pages in one folder, all 4 components in another. No feature-based grouping. Will become unwieldy as pages grow | Hard to maintain; no module boundaries | `src/pages/`, `src/components/` |

#### 2.5.5 Missing Pages (per Reference ERD and Plan)

| # | Missing Page/Feature | ERD Entities | Current Status |
|---|---|---|---|
| F18 | **Site/Asset Management** — CRUD for sites, gateways, assets. Asset hierarchy tree view (Tenant → Site → Gateway → Asset → Sensor) | Site, Gateway, Asset | Completely missing; only flat `Sensors` page exists |
| F19 | **Asset Health Dashboard** — Per-asset health score, trend, status indicators. Drill-down from site overview to individual asset health | AssetHealth | Completely missing |
| F20 | **ML Management** — View models, versions, deployments, per-asset model bindings. Deploy/rollback versions. View training metrics and version comparison | MLModel, MLModelVersion, MLModelDeployment, AssetModelVersion | Only a "Trigger Retrain" button in Settings; no version list, no deployment management |
| F21 | **Alert Management** — View/create alarm rules, view alarm events, acknowledge/resolve events, notification log history, maintenance work orders | AlarmRule, AlarmEvent, NotificationLog, MaintenanceWorkOrder | Completely missing; only notification action config in Settings |
| F22 | **Tenant Admin** — Tenant profile, user management, role assignment (RBAC Phase 2) | Tenant, User (with roles) | No tenant page; only Register/Login |
| F23 | **Work Order Management** — Create, assign, track, complete work orders linked to alarm events | MaintenanceWorkOrder | Completely missing |
| F24 | **Dashboard doesn't reflect asset hierarchy** — Shows global stats (total predictions, total feedback). Should show per-site or per-asset breakdown with drill-down | — | `Dashboard.tsx` shows flat global numbers |

### 2.6 Data Model Issues

| # | Issue | Severity |
|---|---|---|
| D1 | No schema enforcement on MongoDB collections (schemaless inserts from multiple paths) | Medium |
| D2 | Users/settings stored in MongoDB but would benefit from relational integrity (FK, unique constraints, transactions) | High |
| D3 | ML model versions tracked only on filesystem (`models/versions/`), not in a database | Medium |
| D4 | Alert history is not persisted — alerts fire and forget | Medium |
| D5 | No soft-delete pattern — reference ERD requires `IsDeleted`, `DeleteAt`, `DeleteBy` on all entities | Medium |
| D6 | No asset health tracking — reference ERD has `AssetHealth` with calculated health scores | Medium |

---

## Part 3: Recommended Refactored Architecture

### 3.1 Core Principle: Split Databases by Concern

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PostgreSQL (Core Business)                         │
│                                                                          │
│  ┌─ Site Setup ──────────────────────────────────────────────────────┐   │
│  │  tenants, users, roles*, permissions*, sites, gateways,          │   │
│  │  assets, sensors, asset_health                                   │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│  ┌─ ML Management ──────────────────────────────────────────────────┐   │
│  │  ml_models, ml_model_versions, ml_model_deployments,             │   │
│  │  asset_model_versions                                            │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│  ┌─ Prediction & Feedback ──────────────────────────────────────────┐   │
│  │  feedback                                                        │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│  ┌─ Alert Management ───────────────────────────────────────────────┐   │
│  │  notification_types, alarm_rules, alarm_notification_types,      │   │
│  │  alarm_events, notification_logs, maintenance_work_orders        │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│  ┌─ Chatbot (future) ──────────────────────────────────────────────-┐   │
│  │  knowledge_base, knowledge_embeddings, conversations, messages   │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│  ┌─ System ────────────────────────────────────────────────────────-┐   │
│  │  api_keys (service-to-service auth)                              │   │
│  └──────────────────────────────────────────────────────────────────-┘   │
│                                                                          │
│  * roles/permissions tables added when RBAC is implemented               │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                     MongoDB (Time-Series / Streaming)                     │
│                                                                          │
│  telemetry_raw    — Raw MQTT payloads (TTL: 30 days)                     │
│  predictions      — Every prediction with features (TTL: 90 days)        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                     Object Storage (ML Artifacts)                         │
│                     (S3 / MinIO / local volume)                           │
│                                                                          │
│  models/fault_classifier/1.0.3/xgboost_anomaly_detector.json             │
│  models/fault_classifier/1.0.3/label_encoder.pkl                         │
│  models/fault_classifier/1.0.3/feature_scaler.pkl                        │
│  models/fault_classifier/1.0.3/metadata.json                             │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Why This Split?

| Data | Why PostgreSQL | Why MongoDB |
|---|---|---|
| **Tenants, Sites, Gateways, Assets, Sensors** | Deep relational hierarchy with FK constraints, UNIQUE per tenant, JOIN queries, audit columns | — |
| **Users, Roles, Permissions** | ACID auth transactions, UNIQUE constraints, FK to tenant, future RBAC JOINs | — |
| **ML Models/Versions/Deployments** | Exactly-one-active constraint, per-asset deployment tracking, metrics comparison queries | — |
| **Alarm Rules, Events, Work Orders** | Complex relationships (rule → event → notification → work order), status workflows, FK integrity | — |
| **Feedback** | FK to user + sensor + model_version, used in retraining queries, audit trail | — |
| **Telemetry Raw** | — | Append-heavy, flexible payload schema, TTL expiry, time-series queries |
| **Predictions (streaming)** | — | High write throughput per sensor reading, embedded features array, TTL expiry |

### 3.3 Refactored Service Architecture

```
                                    ┌─────────────────────────┐
                                    │       API Gateway        │
                                    │   (nginx / traefik)      │
                                    │   - rate limiting         │
                                    │   - JWT validation        │
                                    │   - route to services     │
                                    └────────────┬────────────┘
                                                 │
                    ┌────────────────────────────-┼───────────────────────────┐
                    │                             │                           │
         ┌──────────▼──────────┐    ┌─────────────▼───────────┐   ┌─────────────▼─────────────┐
         │  Core API Service   │    │  Ingestion Service      │   │  ML Service               │
         │  (backend-api)      │    │  (mqtt-ingestion)       │   │  (ml-service)             │
         │                     │    │                         │   │                           │
         │  Domain Modules:    │    │  • MQTT subscriber      │   │  Domain Modules:          │
         │  ├─ auth/           │    │  • Sliding window       │   │  ├─ prediction/           │
         │  ├─ site_setup/     │    │  • Store → MongoDB      │   │  ├─ models/               │
         │  ├─ predictions/    │    │  • Call ML → predict    │   │  │  (ModelRegistry LRU)    │
         │  ├─ ml_management/  │    │  • Publish alerts →     │   │  ├─ feedback/             │
         │  ├─ alerts/         │    │    backend-api (HTTP)   │   │  ├─ retraining/           │
         │  └─ dashboard/      │    │  • WebSocket /stream    │   │  └─ artifacts/            │
         │                     │    │                         │   │                           │
         │  DB: PostgreSQL     │    │  Reads: PostgreSQL      │   │  Reads: PostgreSQL        │
         │  (primary)          │    │  (sensor registry,      │   │  (model versions,         │
         │  + MongoDB (reads   │    │   alarm rules)          │   │   deployments, feedback)  │
         │    for dashboard)   │    │  Writes: MongoDB        │   │  Writes: PostgreSQL       │
         └─────────────────────┘    │  (telemetry_raw,        │   │  (model versions,feedback)│
                                    │   predictions)          │   │  Writes: ArtifactStore    │
                                    └─────────────────────────┘   │  (local/S3 model files)   │
                                                                  └───────────────────────────┘

Note: Alert processing is handled by the `alerts/` module inside backend-api
(POST /alerts/evaluate). Notification dispatch runs as a background task
(asyncio.create_task) to avoid blocking the caller. No separate alert service.
```

### 3.4 mqtt-ingestion — Refactored Architecture

#### 3.4.0 Design Principles

1. **Tenant-first**: Every MQTT message is resolved to a `(tenant_id, site_id, asset_id, sensor_id)` context before any processing.
2. **Model-aware**: Before calling the ML service, look up the active `AssetModelVersion` for this asset to route to the correct model/version.
3. **Auth on all boundaries**: API key for outbound service calls; JWT for WebSocket.
4. **Decouple alerts**: HTTP call to backend-api `POST /alerts/evaluate`. Backend-api evaluates rules synchronously and dispatches notifications asynchronously (background task).
5. **Separate concerns**: Break the 517-line `MQTTClient` into focused modules.

#### 3.4.1 MQTT Topic Convention (Multi-Tenant)

**Current:** `sensors/{sensor_id}` — flat, global, no tenant context.

**Proposed:** `{tenant_code}/{site_code}/sensors/{sensor_code}`

```
Examples:
  acme/plant_a/sensors/pump_01
  acme/plant_a/sensors/motor_01
  globex/factory_1/sensors/vib_sensor_03

Subscribe pattern per tenant: {tenant_code}/+/sensors/#
Global subscribe (ingestion):  +/+/sensors/#
```

**Alternative (if topic change is not possible):** The sensor payload itself must contain a `sensor_code` field. On startup, mqtt-ingestion loads a lookup table from PostgreSQL (`sensors` JOIN `assets` JOIN `sites` JOIN `tenants`) mapping `sensor_code → full context`. Messages with unknown `sensor_code` are logged and dropped.

#### 3.4.2 Startup Context Cache (PostgreSQL Read)

On startup (and periodically refreshed), mqtt-ingestion loads two caches from PostgreSQL:

**Cache 1 — Sensor Registry** (`sensor_registry_cache`):
```python
# Key: sensor_code (or mqtt_topic)
# Value: SensorContext
@dataclass
class SensorContext:
    tenant_id:   UUID
    site_id:     UUID
    asset_id:    UUID
    sensor_id:   UUID    # PG sensors.id
    sensor_code: str
    asset_code:  str
    sensor_type: str     # vibration, temperature, ...
    mount_location: str  # motor_DE, motor_NDE, ...
```

**Cache 2 — Asset Model Bindings** (`model_binding_cache`):
```python
# Key: asset_id
# Value: ModelBinding
@dataclass
class ModelBinding:
    model_id:         UUID
    model_version_id: UUID
    version_label:    str    # e.g. "fault_classifier:1.0.3"
    stage:            str    # production | staging
    artifact_path:    str
```

Loaded via:
```sql
SELECT s.sensor_code, s.mqtt_topic, s.id AS sensor_id,
       a.id AS asset_id, a.asset_code,
       si.id AS site_id, si.site_code,
       t.id AS tenant_id, t.tenant_code,
       s.sensor_type, s.mount_location
FROM sensors s
JOIN assets a ON s.asset_id = a.id
JOIN sites si ON a.site_id = si.id
JOIN tenants t ON si.tenant_id = t.id
WHERE s.is_active = true AND s.is_deleted = false;

SELECT amv.asset_id, amv.model_id, amv.model_version_id,
       mv.full_version_label, mv.stage, mv.model_artifact_path
FROM asset_model_versions amv
JOIN ml_model_versions mv ON amv.model_version_id = mv.id
WHERE amv.is_active = true AND mv.stage = 'production';
```

Cache is refreshed every 60 seconds (configurable). Config changes (sensor/model CRUD) propagate within one refresh cycle — acceptable for operations that happen infrequently (minutes/hours, not seconds).

#### 3.4.3 Message Processing Flow (Multi-Tenant)

```
MQTT message arrives on topic: acme/plant_a/sensors/pump_01
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 1. Resolve Context     │
                    │                        │
                    │ Parse topic or payload  │
                    │ → sensor_code = pump_01 │
                    │ Lookup sensor_registry  │
                    │ → SensorContext {       │
                    │     tenant_id,          │
                    │     site_id,            │
                    │     asset_id,           │
                    │     sensor_id }         │
                    │                        │
                    │ If not found → log +   │
                    │   drop message          │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 2. Store Telemetry     │
                    │                        │
                    │ MongoDB telemetry_raw  │
                    │ with tenant_id,        │
                    │ site_id, asset_id,     │
                    │ sensor_id              │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 3. Feature Engineering │
                    │                        │
                    │ Sliding window keyed   │
                    │ by (tenant_id,         │
                    │     asset_id,          │
                    │     sensor_id)         │
                    │                        │
                    │ 24 sensors × 14 stats  │
                    │ = 336 features         │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 4. Resolve Model       │
                    │                        │
                    │ Lookup model_binding   │
                    │ by asset_id            │
                    │ → ModelBinding {       │
                    │     model_version_id,  │
                    │     version_label }    │
                    │                        │
                    │ If no binding → use    │
                    │   tenant default model │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 5. Call ML Service      │
                    │                        │
                    │ POST /predict {        │
                    │   features: [336],     │
                    │   tenant_id,           │
                    │   asset_id,            │
                    │   model_version_id,    │
                    │   top_k: 3             │
                    │ }                      │
                    │ Headers: X-API-Key     │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 6. Store Prediction     │
                    │                        │
                    │ MongoDB predictions    │
                    │ with tenant_id,        │
                    │ site_id, asset_id,     │
                    │ sensor_id,             │
                    │ model_version_id,      │
                    │ telemetry_raw_id (ref) │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ 7. Evaluate Alerts      │
                    │   (optional fast-path)  │
                    │                        │
                    │ If prediction != normal │
                    │ → HTTP POST to         │
                    │   backend-api:         │
                    │   /alerts/evaluate {   │
                    │     tenant_id,         │
                    │     site_id,           │
                    │     asset_id,          │
                    │     sensor_id,         │
                    │     prediction_label,  │
                    │     probability,       │
                    │     model_version_id,  │
                    │     prediction_id,     │
                    │     timestamp }        │
                    │                        │
                    │ Backend-api evaluates  │
                    │ AlarmRules, dispatches │
                    │ notifications (async)  │
                    └───────────────────────┘
```

#### 3.4.4 Refactored Folder Structure

```
mqtt-ingestion/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, lifespan, health endpoint
│   ├── config.py                  # Settings: broker, PG, Mongo, ML URL, backend-api URL, API key
│   │
│   ├── context/                   # --- Tenant/Asset context resolution ---
│   │   ├── __init__.py
│   │   ├── registry.py            # SensorRegistryCache: loads sensors+assets+sites+tenants from PG
│   │   ├── model_bindings.py      # ModelBindingCache: loads asset_model_versions from PG
│   │   └── schemas.py             # SensorContext, ModelBinding dataclasses
│   │
│   ├── ingestion/                 # --- MQTT message handling ---
│   │   ├── __init__.py
│   │   ├── mqtt_client.py         # MQTTClient: connect, subscribe, _on_message dispatches
│   │   ├── message_handler.py     # MessageHandler: resolve context → store → predict → alert
│   │   └── topic_parser.py        # parse_topic(topic) → (tenant_code, site_code, sensor_code)
│   │
│   ├── features/                  # --- Feature engineering ---
│   │   ├── __init__.py
│   │   ├── sliding_window.py      # SlidingWindowManager: per-(tenant,asset,sensor) window buffers
│   │   ├── extractors.py          # extract_24_features(), extract_statistical_features()
│   │   └── validators.py          # validate_payload_schema(), normalize_payload()
│   │
│   ├── prediction/                # --- ML service client ---
│   │   ├── __init__.py
│   │   └── ml_client.py           # MLClient: singleton httpx, predict(features, context, binding)
│   │
│   ├── storage/                   # --- MongoDB writers ---
│   │   ├── __init__.py
│   │   ├── telemetry_writer.py    # write_telemetry_raw(context, payload)
│   │   └── prediction_writer.py   # write_prediction(context, prediction, telemetry_id)
│   │
│   ├── alerts/                    # --- Alert event publishing ---
│   │   ├── __init__.py
│   │   └── publisher.py           # AlertPublisher: HTTP POST to backend-api /alerts/evaluate
│   │
│   └── streaming/                 # --- WebSocket streaming ---
│       ├── __init__.py
│       └── websocket.py           # Authenticated WebSocket, tenant-scoped data
│
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test_topic_parser.py
    ├── test_sliding_window.py
    ├── test_message_handler.py
    └── ...
```

#### 3.4.5 Key Implementation Details

**Sliding Window — Tenant-Scoped Keys:**
```python
# Current (BROKEN for multi-tenant):
self.sensor_windows[sensor_id]              # "pump_01" — collision across tenants

# Refactored:
window_key = (context.tenant_id, context.asset_id, context.sensor_id)
self.sensor_windows[window_key]             # (uuid, uuid, uuid) — globally unique
```

**ML Client — Model-Version-Aware:**
```python
class MLClient:
    def __init__(self, base_url: str, api_key: str):
        self.client = httpx.AsyncClient(base_url=base_url, timeout=5.0)  # singleton
        self.api_key = api_key

    async def predict(self, features: List[float], context: SensorContext,
                      binding: ModelBinding) -> PredictionResult:
        response = await self.client.post(
            "/predict",
            json={
                "features": features,
                "tenant_id": str(context.tenant_id),
                "asset_id": str(context.asset_id),
                "model_version_id": str(binding.model_version_id),
                "top_k": 3
            },
            headers={"X-API-Key": self.api_key}
        )
        ...
```

**WebSocket — JWT Auth + Tenant Scoping:**
```python
@app.websocket("/stream")
async def websocket_stream(websocket: WebSocket, token: str = Query(...)):
    # 1. Validate JWT → extract tenant_id
    user = verify_jwt(token)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    tenant_id = user.tenant_id

    while True:
        # 2. Only send data belonging to this tenant
        data = latest_data_store.get_by_tenant(tenant_id)
        await websocket.send_json(data)
        await asyncio.sleep(1)
```

**Config — New Settings:**
```python
class Settings(BaseSettings):
    # ... existing ...
    POSTGRES_URL: str = "postgresql+asyncpg://..."   # NEW: read-only PG for context
    API_KEY: str = ""                                 # NEW: for ML service calls
    BACKEND_API_URL: str = "http://backend-api:8000"     # For alert event delivery (POST /alerts/evaluate)
    REGISTRY_REFRESH_INTERVAL_SEC: int = 60           # NEW: cache refresh period
    MQTT_TOPIC_PATTERN: str = "{tenant}/{site}/sensors/{sensor}"  # NEW
```

### 3.5 Backend API — Domain Module Structure

Each domain is a **self-contained folder** with its own router, service, ORM models, and Pydantic schemas. No cross-imports between domain service layers — shared data is accessed through the `common/` layer.

```
backend-api/
├── app/
│   ├── main.py                        # FastAPI app: lifespan, include_router() for all domains
│   ├── config.py                      # pydantic-settings: PG, Mongo, JWT, service URLs
│   │
│   ├── common/                        # Shared infrastructure (imported by all domains)
│   │   ├── __init__.py
│   │   ├── database.py                # get_pg_session(), get_mongo_db() dependencies
│   │   ├── base_model.py             # SQLAlchemy BaseModel mixin (see 3.4.1)
│   │   ├── dependencies.py           # get_current_user(), get_current_tenant()
│   │   ├── exceptions.py             # App-level HTTP exceptions
│   │   └── pagination.py             # PaginationParams, paginated_response()
│   │
│   ├── auth/                          # --- Authentication & future RBAC ---
│   │   ├── __init__.py
│   │   ├── router.py                  # POST /auth/register
│   │   │                              # POST /auth/login
│   │   │                              # GET  /auth/me
│   │   │                              # POST /auth/refresh  (future)
│   │   ├── service.py                 # create_user(), authenticate(), create_token()
│   │   ├── models.py                  # User (SQLAlchemy ORM)
│   │   ├── schemas.py                 # UserCreate, UserResponse, Token, TokenData
│   │   ├── security.py                # hash_password(), verify_password(), create_jwt(), decode_jwt()
│   │   └── README.md                  # Auth module scope & future RBAC notes (see 3.4.2)
│   │
│   ├── site_setup/                    # --- Tenant / Site / Gateway / Asset / Sensor / Health ---
│   │   ├── __init__.py
│   │   ├── router.py                  # Mounted at /site-setup
│   │   │                              #   POST/GET         /tenants
│   │   │                              #   POST/GET         /sites
│   │   │                              #   POST/GET         /gateways
│   │   │                              #   POST/GET/PATCH   /assets
│   │   │                              #   POST/GET/PATCH   /sensors
│   │   │                              #   GET              /assets/{id}/health
│   │   │                              #   GET              /sensors/{id}/settings  (user_settings)
│   │   │                              #   POST             /sensors/{id}/settings
│   │   ├── service.py                 # CRUD logic, tenant-scoped queries
│   │   ├── models.py                  # Tenant, Site, Gateway, Asset, Sensor, AssetHealth,
│   │   │                              #   UserSetting, FaultAction (all SQLAlchemy ORM)
│   │   └── schemas.py                 # Pydantic request/response per entity
│   │
│   ├── predictions/                   # --- Telemetry, Predictions, Feedback ---
│   │   ├── __init__.py
│   │   ├── router.py                  # Mounted at /predictions
│   │   │                              #   GET  /telemetry          (→ MongoDB telemetry_raw)
│   │   │                              #   GET  /                   (→ MongoDB predictions)
│   │   │                              #   POST /                   (manual predict via ML proxy)
│   │   │                              #   POST /feedback
│   │   │                              #   GET  /feedback
│   │   ├── service.py                 # MongoDB reads for telemetry/predictions
│   │   │                              # PostgreSQL writes for feedback
│   │   │                              # Forward feedback to ML service
│   │   ├── models.py                  # Feedback (SQLAlchemy ORM)
│   │   └── schemas.py                 # TelemetryResponse, PredictionResponse,
│   │                                  #   FeedbackCreate, FeedbackResponse
│   │
│   ├── ml_management/                 # --- ML Models, Versions, Deployments ---
│   │   ├── __init__.py
│   │   ├── router.py                  # Mounted at /ml
│   │   │                              #   GET  /models
│   │   │                              #   POST /models
│   │   │                              #   GET  /models/{id}/versions
│   │   │                              #   POST /models/{id}/versions/{v}/deploy
│   │   │                              #   GET  /deployments
│   │   │                              #   POST /assets/{id}/model-binding
│   │   │                              #   POST /retrain
│   │   ├── service.py                 # Proxy to ML service + PG metadata management
│   │   ├── models.py                  # MLModel, MLModelVersion, MLModelDeployment,
│   │   │                              #   AssetModelVersion (all SQLAlchemy ORM)
│   │   └── schemas.py
│   │
│   ├── alerts/                        # --- Alarm Rules, Events, Notifications, Work Orders ---
│   │   ├── __init__.py
│   │   ├── router.py                  # Mounted at /alerts
│   │   │                              #   CRUD /rules
│   │   │                              #   CRUD /notification-types
│   │   │                              #   GET  /events
│   │   │                              #   PATCH /events/{id}/acknowledge
│   │   │                              #   PATCH /events/{id}/resolve
│   │   │                              #   GET  /notification-log
│   │   │                              #   CRUD /work-orders
│   │   ├── service.py
│   │   ├── models.py                  # NotificationType, AlarmRule, AlarmNotificationType,
│   │   │                              #   AlarmEvent, NotificationLog, MaintenanceWorkOrder
│   │   └── schemas.py
│   │
│   ├── dashboard/                     # --- Aggregated views ---
│   │   ├── __init__.py
│   │   ├── router.py                  # GET /dashboard  (aggregates PG + MongoDB)
│   │   └── service.py
│   │
│   └── db/                            # --- Database infrastructure ---
│       ├── __init__.py
│       ├── postgres.py                # async engine (asyncpg), sessionmaker
│       ├── mongodb.py                 # Motor client singleton
│       └── migrations/                # Alembic
│           ├── env.py
│           └── versions/
│
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── tests/
    ├── conftest.py
    ├── auth/
    │   └── test_auth.py
    ├── site_setup/
    │   └── test_sensors.py
    ├── predictions/
    │   └── test_feedback.py
    └── ...
```

#### 3.5.1 BaseModel Mixin (Matches Reference ERD)

Every PostgreSQL entity inherits audit fields from the reference ERD's `BaseModel`:

```python
# backend-api/app/common/base_model.py
from sqlalchemy import Column, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

class AuditMixin:
    """
    Maps to reference ERD BaseModel:
    TenantId, CreateAt, CreateBy, UpdateAt, UpdateBy, DeleteAt, DeleteBy, IsActive, IsDeleted
    """
    tenant_id   = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    is_active   = Column(Boolean, nullable=False, default=True)
    is_deleted  = Column(Boolean, nullable=False, default=False, index=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at  = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    updated_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at  = Column(DateTime(timezone=True), nullable=True)
    deleted_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
```

All queries automatically filter `WHERE is_deleted = false` via a default query scope or explicit service-layer logic.

#### 3.5.2 Auth Module — Designed for Future RBAC Scale-Up

The `auth/` module starts simple (JWT + user table) but is **structured to absorb RBAC later** without restructuring other modules.

**Phase 1 (now): Simple role column**
```
users.role = 'admin' | 'engineer' | 'operator'
```
The `get_current_user()` dependency returns the user with their role. Routers check `if user.role != 'admin': raise 403`.

**Phase 2 (future): Full RBAC with permissions**

When RBAC is needed, add these tables inside the `auth/` module:

```
auth/
├── models.py          # User + Role + Permission + UserRole + RolePermission
├── rbac.py            # require_permission("sensors:write") dependency
└── ...
```

```sql
-- Future tables (added via Alembic migration when ready)
CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    name        VARCHAR(100) NOT NULL,   -- 'Site Admin', 'ML Engineer', 'Operator', ...
    description TEXT,
    is_system   BOOLEAN DEFAULT false,   -- system roles can't be deleted
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource    VARCHAR(100) NOT NULL,   -- 'sensors', 'models', 'alerts', 'work_orders'
    action      VARCHAR(50) NOT NULL,    -- 'read', 'write', 'delete', 'deploy', 'retrain'
    description TEXT,
    UNIQUE (resource, action)
);

CREATE TABLE role_permissions (
    role_id       UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id),   -- NULL = tenant-wide, non-NULL = scoped to site
    PRIMARY KEY (user_id, role_id, COALESCE(site_id, '00000000-0000-0000-0000-000000000000'))
);
```

**Transition path:** When RBAC is implemented, the existing `user.role` column becomes a convenience field that mirrors the primary role from `user_roles`. Existing role-check code (`if user.role != 'admin'`) is replaced with a `require_permission("resource:action")` FastAPI dependency that queries the RBAC tables. Other domain modules **do not change** — they only see the dependency signature.

```python
# Before RBAC (Phase 1):
@router.post("/sensors")
async def create_sensor(
    data: SensorCreate,
    user: User = Depends(get_current_user),    # simple role check inside
):
    ...

# After RBAC (Phase 2) — same signature, different implementation:
@router.post("/sensors")
async def create_sensor(
    data: SensorCreate,
    user: User = Depends(get_current_user),
    _: None = Depends(require_permission("sensors:write")),
):
    ...
```

#### 3.5.3 PostgreSQL Schema (Aligned to Reference ERD)

> This schema is shared across all services — backend-api (primary owner), ml-service (reads/writes model versions and feedback), and mqtt-ingestion (reads sensor registry and model bindings).

```sql
-- ============================================================
-- TENANTS (ref: Tenant)
-- ============================================================
CREATE TABLE tenants (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_code  VARCHAR(50)  NOT NULL UNIQUE,
    tenant_name  VARCHAR(255) NOT NULL,
    plan         VARCHAR(50)  NOT NULL DEFAULT 'free',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    is_deleted   BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by   UUID          -- self-ref not enforced on tenants
);

-- ============================================================
-- USERS (ref: User)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username        VARCHAR(100) NOT NULL,
    email           VARCHAR(255),
    full_name       VARCHAR(255),
    password_hash   TEXT NOT NULL,
    role            VARCHAR(50) NOT NULL DEFAULT 'operator',  -- simple role (Phase 1)
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_deleted      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      UUID REFERENCES users(id),
    deleted_at      TIMESTAMPTZ,
    deleted_by      UUID REFERENCES users(id),
    UNIQUE (tenant_id, username),
    UNIQUE (tenant_id, email)
);

-- ============================================================
-- USER SETTINGS (notification preferences)
-- ============================================================
CREATE TABLE user_settings (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    auto_refresh         BOOLEAN NOT NULL DEFAULT true,
    refresh_interval_sec INTEGER NOT NULL DEFAULT 5,
    anomaly_threshold    REAL NOT NULL DEFAULT 0.7,
    enable_notifications BOOLEAN NOT NULL DEFAULT true,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fault_actions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(50) NOT NULL,            -- email | sms | webhook | slack
    enabled     BOOLEAN NOT NULL DEFAULT false,
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- SITES (ref: Site)
-- ============================================================
CREATE TABLE sites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    site_code   VARCHAR(100) NOT NULL,
    site_name   VARCHAR(255) NOT NULL,
    location    TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    is_deleted  BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID REFERENCES users(id),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID REFERENCES users(id),
    UNIQUE (tenant_id, site_code)
);

-- ============================================================
-- GATEWAYS (ref: Gateway)
-- ============================================================
CREATE TABLE gateways (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    site_id           UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    gateway_code      VARCHAR(100) NOT NULL,
    ip_address        VARCHAR(45),
    firmware_version  VARCHAR(100),
    is_online         BOOLEAN NOT NULL DEFAULT false,
    last_seen         TIMESTAMPTZ,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    is_deleted        BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        UUID REFERENCES users(id),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by        UUID REFERENCES users(id),
    deleted_at        TIMESTAMPTZ,
    deleted_by        UUID REFERENCES users(id),
    UNIQUE (tenant_id, gateway_code)
);

-- ============================================================
-- ASSETS (ref: Asset)
-- ============================================================
CREATE TABLE assets (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    site_id     UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    gateway_id  UUID REFERENCES gateways(id),
    asset_code  VARCHAR(100) NOT NULL,
    asset_name  VARCHAR(255) NOT NULL,
    asset_type  VARCHAR(100) NOT NULL,           -- motor, pump, gearbox, ...
    image_url   TEXT,                            -- URL or path to stored asset image (e.g., S3)
    is_active   BOOLEAN NOT NULL DEFAULT true,
    is_deleted  BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID REFERENCES users(id),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID REFERENCES users(id),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID REFERENCES users(id),
    UNIQUE (tenant_id, asset_code)
);

-- ============================================================
-- SENSORS (ref: Sensor)
-- ============================================================
CREATE TABLE sensors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id          UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    gateway_id        UUID REFERENCES gateways(id),    -- NULL if direct-to-broker
    sensor_code       VARCHAR(100) NOT NULL,
    sensor_type       VARCHAR(100) NOT NULL,            -- vibration, temperature, ultrasonic, ...
    mount_location    VARCHAR(100),                     -- motor_DE, motor_NDE, pump_DE, pump_NDE
    mqtt_topic        VARCHAR(255),
    validation_data   JSONB,                            -- calibration/validation metadata
    installation_date DATE,
    position_x        NUMERIC(5,2) NOT NULL,            -- % position in asset-image from left (0–100)
    position_y        NUMERIC(5,2) NOT NULL,            -- % position in asset-image from top (0–100)
    is_active         BOOLEAN NOT NULL DEFAULT true,
    is_deleted        BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        UUID REFERENCES users(id),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by        UUID REFERENCES users(id),
    deleted_at        TIMESTAMPTZ,
    deleted_by        UUID REFERENCES users(id),
    UNIQUE (tenant_id, sensor_code)
);

-- ============================================================
-- ASSET HEALTH (ref: AssetHealth)
-- ============================================================
CREATE TABLE asset_health (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id),
    site_id            UUID NOT NULL REFERENCES sites(id),
    asset_id           UUID NOT NULL REFERENCES assets(id),
    health_score       REAL NOT NULL CHECK (health_score >= 0 AND health_score <= 100),
    health_status      VARCHAR(50) NOT NULL,    -- Healthy, Warning, Critical
    calculation_method VARCHAR(100),
    health_calc_date   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_asset_health_latest ON asset_health (asset_id, health_calc_date DESC);

-- ============================================================
-- ML MODELS (ref: MLModel)
-- ============================================================
CREATE TABLE ml_models (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    model_name        VARCHAR(255) NOT NULL,     -- e.g. 'fault_classifier'
    model_description TEXT,
    model_type        VARCHAR(100) NOT NULL,      -- Classification, Regression, RUL, ...
    is_active         BOOLEAN NOT NULL DEFAULT true,
    is_deleted        BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        UUID REFERENCES users(id),
    UNIQUE (tenant_id, model_name)
);

-- ============================================================
-- ML MODEL VERSIONS (ref: MLModelVersion)
-- ============================================================
CREATE TABLE ml_model_versions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL REFERENCES tenants(id),
    model_id              UUID NOT NULL REFERENCES ml_models(id) ON DELETE CASCADE,
    semantic_version      VARCHAR(50) NOT NULL,                     -- 1.0.3
    full_version_label    VARCHAR(255) NOT NULL,                    -- fault_classifier:1.0.3
    stage                 VARCHAR(50) NOT NULL DEFAULT 'staging',   -- staging | production | archived
    model_artifact_path   TEXT NOT NULL,
    docker_image_tag      VARCHAR(255),
    dataset_hash          VARCHAR(128),
    feature_schema_hash   VARCHAR(128),
    training_start        TIMESTAMPTZ,
    training_end          TIMESTAMPTZ,
    accuracy              REAL,
    precision_score       REAL,
    recall_score          REAL,
    f1_score              REAL,
    false_alarm_rate      REAL,
    is_active             BOOLEAN NOT NULL DEFAULT true,
    is_deleted            BOOLEAN NOT NULL DEFAULT false,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by            UUID REFERENCES users(id),
    UNIQUE (tenant_id, full_version_label)
);

-- ============================================================
-- ML MODEL DEPLOYMENTS (ref: MLModelDeployment)
-- ============================================================
CREATE TABLE ml_model_deployments (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID NOT NULL REFERENCES tenants(id),
    model_id                 UUID NOT NULL REFERENCES ml_models(id),
    model_version_id         UUID NOT NULL REFERENCES ml_model_versions(id),
    is_production            BOOLEAN NOT NULL DEFAULT false,
    deployment_start         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployment_end           TIMESTAMPTZ,
    rollback_from_version_id UUID REFERENCES ml_model_versions(id),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by               UUID REFERENCES users(id)
);

-- ============================================================
-- ASSET MODEL VERSIONS (ref: AssetModelVersion — per-asset model binding)
-- ============================================================
CREATE TABLE asset_model_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    asset_id          UUID NOT NULL REFERENCES assets(id),
    model_id          UUID NOT NULL REFERENCES ml_models(id),
    model_version_id  UUID NOT NULL REFERENCES ml_model_versions(id),
    stage             VARCHAR(50) NOT NULL DEFAULT 'production',
    deployment_start  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deployment_end    TIMESTAMPTZ,
    is_active         BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        UUID REFERENCES users(id)
);

-- ============================================================
-- FEEDBACK (ref: Feedback)
-- ============================================================
CREATE TABLE feedback (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL REFERENCES tenants(id),
    site_id               UUID REFERENCES sites(id),
    asset_id              UUID REFERENCES assets(id),
    sensor_id             UUID REFERENCES sensors(id),
    prediction_id         VARCHAR(100),             -- MongoDB ObjectId of the prediction doc
    payload_normalized    JSONB,                     -- snapshot of the feature vector
    validation_data       JSONB,
    prediction_label      VARCHAR(255) NOT NULL,     -- original model prediction
    probability           REAL,
    new_label             VARCHAR(255) NOT NULL,     -- human-corrected label
    correction            TEXT,                       -- free-text explanation
    feedback_type         VARCHAR(50) NOT NULL,       -- correction | new_fault | false_positive | correct
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by            UUID NOT NULL REFERENCES users(id)
);

-- ============================================================
-- NOTIFICATION TYPES (ref: NotificationType)
-- ============================================================
CREATE TABLE notification_types (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    notify_type_name    VARCHAR(100) NOT NULL,     -- email, sms, webhook, slack
    notify_type_data    JSONB NOT NULL DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, notify_type_name)
);

-- ============================================================
-- ALARM RULES (ref: AlarmRule)
-- ============================================================
CREATE TABLE alarm_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    asset_id            UUID REFERENCES assets(id),
    sensor_id           UUID REFERENCES sensors(id),
    rule_name           VARCHAR(255) NOT NULL,
    parameter_name      VARCHAR(100) NOT NULL,      -- 'confidence', 'temperature', 'vibration_rms'
    threshold_value     REAL NOT NULL,
    comparison_operator VARCHAR(10) NOT NULL,        -- '>', '>=', '<', '<=', '=='
    severity_level      VARCHAR(50) NOT NULL,        -- low, medium, high, critical
    is_active           BOOLEAN NOT NULL DEFAULT true,
    is_deleted          BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          UUID REFERENCES users(id)
);

-- ============================================================
-- ALARM NOTIFICATION TYPES (ref: AlarmNotificationType — M:N join)
-- ============================================================
CREATE TABLE alarm_notification_types (
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    alarm_rule_id       UUID NOT NULL REFERENCES alarm_rules(id) ON DELETE CASCADE,
    notification_type_id UUID NOT NULL REFERENCES notification_types(id) ON DELETE CASCADE,
    PRIMARY KEY (alarm_rule_id, notification_type_id)
);

-- ============================================================
-- ALARM EVENTS (ref: AlarmEvent)
-- ============================================================
CREATE TABLE alarm_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    asset_id          UUID REFERENCES assets(id),
    sensor_id         UUID REFERENCES sensors(id),
    alarm_rule_id     UUID REFERENCES alarm_rules(id),
    prediction_id     VARCHAR(100),                -- MongoDB ObjectId
    model_version_id  UUID REFERENCES ml_model_versions(id),
    triggered_value   REAL,
    triggered_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cleared_at        TIMESTAMPTZ,
    correction_plan   TEXT,
    status            VARCHAR(50) NOT NULL DEFAULT 'open',  -- open | acknowledged | resolved | cleared
    acknowledged_by   UUID REFERENCES users(id),
    acknowledged_at   TIMESTAMPTZ,
    is_deleted        BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alarm_events_tenant_status ON alarm_events (tenant_id, status, triggered_at DESC);

-- ============================================================
-- NOTIFICATION LOG (ref: NotificationLog)
-- ============================================================
CREATE TABLE notification_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    asset_id            UUID REFERENCES assets(id),
    alarm_event_id      UUID NOT NULL REFERENCES alarm_events(id),
    notification_type_id UUID REFERENCES notification_types(id),
    channel             VARCHAR(50) NOT NULL,       -- email, sms, webhook, slack
    recipient           VARCHAR(255),
    status              VARCHAR(50) NOT NULL,        -- sent, failed, pending
    sent_at             TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- MAINTENANCE WORK ORDERS (ref: MaintenanceWorkOrder)
-- ============================================================
CREATE TABLE maintenance_work_orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    asset_id        UUID NOT NULL REFERENCES assets(id),
    alarm_event_id  UUID REFERENCES alarm_events(id),
    work_number     VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    priority_level  VARCHAR(50) NOT NULL DEFAULT 'medium',  -- low, medium, high, critical
    status          VARCHAR(50) NOT NULL DEFAULT 'open',     -- open, in_progress, completed, cancelled
    assigned_to     UUID REFERENCES users(id),
    is_deleted      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by      UUID REFERENCES users(id)
);

-- ============================================================
-- API KEYS (service-to-service auth)
-- ============================================================
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    key_hash    TEXT NOT NULL,
    scopes      TEXT[] NOT NULL DEFAULT '{}',
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ
);
```

### 3.6 MongoDB Collections — Multi-Tenant Design

The reference ERD's `TelemetryRaw` and `Prediction` entities map to MongoDB collections since they are high-throughput, append-only, and benefit from TTL expiry. **Every document must carry `tenant_id` as the first field in every compound index** — this is the core multi-tenancy enforcement in MongoDB.

#### 3.6.1 Multi-Tenancy Strategy in MongoDB

| Aspect | Decision | Rationale |
|---|---|---|
| **Isolation model** | Application-level (`tenant_id` field on every document) | Same pattern as PostgreSQL; simple, no MongoDB Enterprise features needed |
| **Index prefix** | `tenant_id` is always the **first** key in every compound index | MongoDB can only use one index per query; prefix ensures tenant-scoped queries are efficient |
| **Write enforcement** | mqtt-ingestion resolves `tenant_id` from sensor registry before writing; rejects messages with unknown sensors | Prevents orphaned data without a tenant |
| **Read enforcement** | All backend-api queries pass `tenant_id` as a mandatory filter; enforced in service layer | No cross-tenant data leakage |
| **Schema validation** | MongoDB JSON Schema on both collections enforces `tenant_id` and `asset_id` as required | Prevents accidental writes without tenant context |
| **TTL** | Per-collection TTL index on `timestamp_utc`; same retention for all tenants | Simplest; per-tenant TTL requires background jobs (future) |
| **Separate databases** | Single database for now (`aastreli`); per-tenant databases as a future option when volume exceeds ~100 tenants or compliance requires physical isolation | Simplest; no connection pool bloat |

#### 3.6.2 Collection Definitions

```javascript
// ──────────────────────────────────────────────────
// telemetry_raw (ref: TelemetryRaw)
// Raw MQTT payloads — replaces current sensor_data + sensor_readings
// Written by: mqtt-ingestion (with full tenant context from registry cache)
// Read by: backend-api (dashboard, predictions module)
// ──────────────────────────────────────────────────
db.createCollection("telemetry_raw", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "asset_id", "timestamp_utc", "payload_original"],
      properties: {
        tenant_id:  { bsonType: "string", description: "REQUIRED — PG tenants.id" },
        site_id:    { bsonType: "string" },
        asset_id:   { bsonType: "string", description: "REQUIRED — PG assets.id" },
        sensor_id:  { bsonType: ["string", "null"] },
        timestamp_utc: { bsonType: "date" }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

// TTL: 30 days
db.telemetry_raw.createIndex(
  { "timestamp_utc": 1 },
  { expireAfterSeconds: 2592000 }
);

// Primary: "telemetry for this tenant's asset in time range"
db.telemetry_raw.createIndex({ "tenant_id": 1, "asset_id": 1, "timestamp_utc": -1 });
// Secondary: by specific sensor
db.telemetry_raw.createIndex({ "tenant_id": 1, "sensor_id": 1, "timestamp_utc": -1 });

// Document shape:
// {
//   _id:                 ObjectId,
//   tenant_id:           "uuid-string",          ← MANDATORY (from registry cache)
//   site_id:             "uuid-string",
//   asset_id:            "uuid-string",          ← MANDATORY
//   sensor_id:           "uuid-string" | null,
//   timestamp_utc:       ISODate,
//   payload_original:    { ... raw MQTT JSON ... },
//   payload_normalized:  [336 floats],            ← only after feature extraction
//   validation_data:     { ... },
//   mqtt_topic:          "acme/plant_a/sensors/pump_01"
// }

// ──────────────────────────────────────────────────
// predictions (ref: Prediction)
// One document per ML inference — replaces inline prediction in sensor_readings
// Written by: mqtt-ingestion (after ML service call, with model_version_id)
// Read by: backend-api (dashboard, predictions module, feedback context)
// ──────────────────────────────────────────────────
db.createCollection("predictions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "asset_id", "timestamp_utc", "prediction_label", "model_version_id"],
      properties: {
        tenant_id:        { bsonType: "string", description: "REQUIRED" },
        asset_id:         { bsonType: "string", description: "REQUIRED" },
        model_version_id: { bsonType: "string", description: "REQUIRED — PG ml_model_versions.id" },
        timestamp_utc:    { bsonType: "date" },
        prediction_label: { bsonType: "string" }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

// TTL: 90 days
db.predictions.createIndex(
  { "timestamp_utc": 1 },
  { expireAfterSeconds: 7776000 }
);

// Primary: "predictions for this tenant's asset in time range"
db.predictions.createIndex({ "tenant_id": 1, "asset_id": 1, "timestamp_utc": -1 });
// Secondary: filter by fault type (dashboard anomaly counts)
db.predictions.createIndex({ "tenant_id": 1, "prediction_label": 1, "timestamp_utc": -1 });
// Secondary: by model version (model performance tracking across tenants)
db.predictions.createIndex({ "tenant_id": 1, "model_version_id": 1, "timestamp_utc": -1 });

// Document shape:
// {
//   _id:                  ObjectId,
//   tenant_id:            "uuid-string",          ← MANDATORY
//   site_id:              "uuid-string",
//   asset_id:             "uuid-string",          ← MANDATORY
//   sensor_id:            "uuid-string" | null,
//   telemetry_raw_id:     ObjectId,               ← FK to telemetry_raw
//   timestamp_utc:        ISODate,
//   payload_normalized:   [336 floats],
//   validation_data:      { ... },
//   prediction_label:     "bearing_overgrease_churning",
//   probability:          0.857,
//   top_predictions:      [{label: "...", confidence: 0.857}, ...],
//   model_version_id:     "uuid-string",          ← MANDATORY — PG ml_model_versions.id
//   model_version_label:  "fault_classifier:1.0.3",
//   explanation_payload:  { ... SHAP values (future) ... }
// }
```

#### 3.6.3 Query Patterns (All Tenant-Scoped)

Every service-layer query receives `tenant_id` as the first parameter:

```python
# backend-api: dashboard/service.py
async def get_recent_predictions(tenant_id: str, limit: int = 20):
    return await db.predictions.find(
        {"tenant_id": tenant_id}
    ).sort("timestamp_utc", -1).limit(limit).to_list(limit)

# backend-api: predictions/service.py
async def get_predictions_for_asset(tenant_id: str, asset_id: str,
                                     start: datetime, end: datetime):
    return await db.predictions.find({
        "tenant_id": tenant_id,
        "asset_id": asset_id,
        "timestamp_utc": {"$gte": start, "$lte": end}
    }).sort("timestamp_utc", -1).to_list(1000)

# backend-api: ml_management/service.py
async def get_predictions_by_model_version(tenant_id: str, model_version_id: str):
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "model_version_id": model_version_id}},
        {"$group": {
            "_id": "$prediction_label",
            "count": {"$sum": 1},
            "avg_probability": {"$avg": "$probability"}
        }}
    ]
    return await db.predictions.aggregate(pipeline).to_list(100)
```

#### 3.6.4 Migration: Current Collections → New Schema

| Current Collection | Action | New Collection |
|---|---|---|
| `sensor_data` | Migrate: add `tenant_id`, `site_id`, `asset_id` via sensor registry lookup; rename | `telemetry_raw` |
| `sensor_readings` | Split: raw data → `telemetry_raw`; prediction fields → `predictions` | `telemetry_raw` + `predictions` |
| `predictions` (backend-api) | Merge into new `predictions` collection | `predictions` |
| `users` | Migrated to PostgreSQL in Phase 2 | Drop |
| `user_settings` | Migrated to PostgreSQL in Phase 2 | Drop |
| `sensors` | Migrated to PostgreSQL in Phase 2 | Drop |
| `faults` | Migrated to PG `fault_types` | Drop |
| `feedback` | Migrated to PostgreSQL in Phase 2 | Drop |
| `models` | Never used | Drop |

### 3.7 ml-service — Refactored Architecture

#### 3.7.0 Design Principles

1. **Tenant-scoped models**: Each tenant has its own `MLModel` → `MLModelVersion` chain. A single ml-service instance can load and serve multiple model versions concurrently (keyed by `model_version_id`).
2. **Database-backed lifecycle**: Model metadata, versions, deployments, and feedback all live in PostgreSQL (matching the reference ERD). Only model artifacts (`.json`, `.pkl` files) live on disk or object storage.
3. **Feedback from PostgreSQL, not pickle**: Retraining reads feedback from the `feedback` table (with tenant, asset, model FK context), not a local file.
4. **Artifact abstraction**: A pluggable `ArtifactStore` layer abstracts local disk vs. S3/MinIO, so the same code works in dev and production.
5. **Safe model swaps**: Model loading uses an in-memory registry with atomic reference swaps — no file copying during live serving.
6. **Auth on all boundaries**: API key validation on all endpoints; tenant context passed in request headers/body.

#### 3.7.1 Refactored Folder Structure

```
ml-service/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, lifespan, include_router() for all modules
│   ├── config.py                      # Settings: PG URL, model paths, XGBoost params, API key
│   │
│   ├── common/                        # --- Shared infrastructure ---
│   │   ├── __init__.py
│   │   ├── database.py                # get_pg_session() async dependency (asyncpg or SQLAlchemy)
│   │   ├── auth.py                    # validate_api_key() middleware
│   │   └── exceptions.py             # ModelNotFoundError, TenantNotFoundError, etc.
│   │
│   ├── prediction/                    # --- Prediction serving ---
│   │   ├── __init__.py
│   │   ├── router.py                  # POST /predict
│   │   │                              # POST /predict-batch
│   │   ├── service.py                 # Resolves model version → calls ModelRegistry → returns result
│   │   ├── feature_converter.py       # convert_structured_to_features() — moved out of main.py
│   │   └── schemas.py                 # PredictionRequest (+ tenant_id, asset_id, model_version_id)
│   │                                  # PredictionResponse, TopPrediction
│   │
│   ├── models/                        # --- Model lifecycle & serving ---
│   │   ├── __init__.py
│   │   ├── router.py                  # GET  /models
│   │   │                              # GET  /models/{id}/versions
│   │   │                              # GET  /models/{id}/versions/{v}
│   │   │                              # POST /models/{id}/versions/{v}/activate
│   │   │                              # GET  /metrics
│   │   ├── service.py                 # CRUD against PG ml_models, ml_model_versions
│   │   ├── registry.py                # ModelRegistry: in-memory cache of loaded XGBoost models
│   │   │                              #   keyed by model_version_id (UUID)
│   │   │                              #   loads on demand, evicts LRU when memory limit hit
│   │   ├── manager.py                 # ModelManager: load/predict/save — same core logic, no versioning
│   │   │                              #   (versioning is now in PG, not filesystem)
│   │   └── schemas.py                 # ModelInfo, ModelVersionInfo, MetricsResponse
│   │
│   ├── feedback/                      # --- Feedback ingestion ---
│   │   ├── __init__.py
│   │   ├── router.py                  # POST /feedback
│   │   │                              # GET  /feedback/stats
│   │   ├── service.py                 # Writes to PG feedback table (replaces pickle)
│   │   │                              # Queries feedback stats per tenant/model
│   │   └── schemas.py                 # FeedbackRequest (+ tenant_id), FeedbackResponse, FeedbackStats
│   │
│   ├── retraining/                    # --- Retraining pipeline ---
│   │   ├── __init__.py
│   │   ├── router.py                  # POST /retrain
│   │   ├── pipeline.py                # RetrainingPipeline: loads feedback from PG, trains XGBoost,
│   │   │                              #   saves artifacts via ArtifactStore, creates PG model_version
│   │   ├── data_loader.py             # Loads original training data + feedback from PG
│   │   │                              #   (fixes catastrophic forgetting)
│   │   └── schemas.py                 # RetrainRequest (+ tenant_id, model_id), RetrainResponse
│   │
│   └── artifacts/                     # --- Model artifact storage abstraction ---
│       ├── __init__.py
│       ├── base.py                    # ArtifactStore protocol: save(), load(), list_versions()
│       ├── local_store.py             # LocalArtifactStore: reads/writes models/ directory
│       └── s3_store.py                # S3ArtifactStore: reads/writes S3/MinIO (future)
│
├── models/                            # Local artifact storage (dev/default)
│   └── ...                            # Organized by: {tenant_id}/{model_name}/{version}/
│
├── requirements.txt
├── Dockerfile
└── tests/
    ├── conftest.py
    ├── prediction/
    │   └── test_predict.py
    ├── models/
    │   └── test_registry.py
    ├── feedback/
    │   └── test_feedback.py
    ├── retraining/
    │   └── test_pipeline.py
    └── artifacts/
        └── test_local_store.py
```

#### 3.7.2 Model Registry — Multi-Version Serving

The key architectural change: instead of one global `ModelManager`, the service maintains an in-memory **ModelRegistry** that can hold multiple loaded models simultaneously.

```python
# ml-service/app/models/registry.py
from collections import OrderedDict
from uuid import UUID

class ModelRegistry:
    """
    In-memory cache of loaded XGBoost model instances.
    Keyed by model_version_id (PG UUID).
    Supports LRU eviction when max_models is exceeded.
    """
    def __init__(self, artifact_store: ArtifactStore, max_models: int = 10):
        self.artifact_store = artifact_store
        self.max_models = max_models
        self._cache: OrderedDict[UUID, LoadedModel] = OrderedDict()
        self._default_version: dict[UUID, UUID] = {}  # tenant_id → default model_version_id

    async def get_model(self, model_version_id: UUID) -> LoadedModel:
        """Get a loaded model by version ID. Loads from artifact store on cache miss."""
        if model_version_id in self._cache:
            self._cache.move_to_end(model_version_id)
            return self._cache[model_version_id]

        # Cache miss — load from artifact store
        loaded = await self._load_from_store(model_version_id)
        self._cache[model_version_id] = loaded

        # Evict LRU if over capacity
        while len(self._cache) > self.max_models:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.info(f"Evicted model {evicted_key} from registry (LRU)")

        return loaded

    async def get_default_model(self, tenant_id: UUID) -> LoadedModel:
        """Get the default (production) model for a tenant."""
        version_id = self._default_version.get(tenant_id)
        if not version_id:
            raise ModelNotFoundError(f"No default model for tenant {tenant_id}")
        return await self.get_model(version_id)

    async def refresh_defaults(self, pg_session):
        """Reload default model versions from PG ml_model_deployments where is_production=true."""
        rows = await pg_session.execute(
            "SELECT tenant_id, model_version_id FROM ml_model_deployments "
            "WHERE is_production = true"
        )
        self._default_version = {row.tenant_id: row.model_version_id for row in rows}

    def invalidate(self, model_version_id: UUID):
        """Remove a model from cache (e.g., after retrain replaces it)."""
        self._cache.pop(model_version_id, None)
```

**LoadedModel** wraps the XGBoost model + scaler + encoder:

```python
@dataclass
class LoadedModel:
    model_version_id: UUID
    version_label: str         # e.g. "fault_classifier:1.0.3"
    xgb_model: xgb.XGBClassifier
    label_encoder: LabelEncoder
    scaler: StandardScaler
    metadata: dict
    loaded_at: datetime

    def predict(self, features: List[float], top_k: int = 3) -> dict:
        """Same prediction logic as current ModelManager.predict()"""
        features_array = np.array(features).reshape(1, -1)
        features_scaled = self.scaler.transform(features_array)
        prediction = self.xgb_model.predict(features_scaled)[0]
        probabilities = self.xgb_model.predict_proba(features_scaled)[0]

        top_k_indices = np.argsort(probabilities)[-top_k:][::-1]
        return {
            'prediction': self.label_encoder.classes_[prediction],
            'confidence': float(probabilities[prediction]),
            'top_predictions': [
                {'label': self.label_encoder.classes_[i], 'confidence': float(probabilities[i])}
                for i in top_k_indices
            ],
            'model_version_id': str(self.model_version_id),
            'model_version_label': self.version_label
        }
```

#### 3.7.3 Prediction Flow (Multi-Tenant)

```
POST /predict {
  features: [336 floats],
  tenant_id: "uuid",               ← NEW (from mqtt-ingestion context)
  asset_id: "uuid",                ← NEW
  model_version_id: "uuid",        ← NEW (from ModelBindingCache)
  top_k: 3
}
    │
    ▼
┌───────────────────────────────┐
│ 1. Validate API Key            │
│    (X-API-Key header)          │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐
│ 2. Resolve Model               │
│                                │
│  if model_version_id provided: │
│    → ModelRegistry.get_model() │
│  else:                         │
│    → ModelRegistry              │
│      .get_default_model(       │
│         tenant_id)             │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐
│ 3. Run Prediction              │
│                                │
│  loaded_model.predict(         │
│    features, top_k)            │
│                                │
│  Returns: prediction_label,    │
│    confidence, top_predictions,│
│    model_version_id,           │
│    model_version_label         │
└───────────────────────────────┘
```

#### 3.7.4 Retraining Flow (Tenant-Scoped)

```
POST /retrain {
  tenant_id: "uuid",              ← NEW: scope retraining to this tenant
  model_id: "uuid",               ← NEW: which MLModel to retrain
  include_original_data: true,     ← NEW: fixes catastrophic forgetting (M13)
  async_mode: true
}
    │
    ▼
┌───────────────────────────────────────────┐
│ 1. Load Training Data                      │
│                                            │
│  a) Load ORIGINAL training dataset         │
│     from artifact store (dataset.pkl       │
│     saved alongside model artifacts)       │
│                                            │
│  b) Load FEEDBACK from PostgreSQL:         │
│     SELECT features, new_label             │
│     FROM feedback                          │
│     WHERE tenant_id = ? AND model_id = ?   │
│     AND feedback_type IN                   │
│       ('correction', 'new_fault')          │
│                                            │
│  c) Merge: original + feedback             │
│     (feedback samples get 3x weight)       │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│ 2. Retrain XGBoost                         │
│                                            │
│  • Fit new StandardScaler on merged data   │
│    (fixes M14: stale scaler)               │
│  • Train with balanced class weights       │
│  • Validate on 20% holdout                 │
│  • Compute metrics: accuracy, balanced_acc,│
│    f1, precision, recall, false_alarm_rate │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│ 3. Save New Version                        │
│                                            │
│  a) Save artifacts to ArtifactStore:       │
│     {tenant_id}/{model_name}/{version}/    │
│       xgboost_anomaly_detector.json        │
│       label_encoder.pkl                    │
│       feature_scaler.pkl                   │
│       metadata.json                        │
│       dataset_hash.txt                     │
│                                            │
│  b) Insert into PG ml_model_versions:      │
│     semantic_version, full_version_label,  │
│     stage='staging', artifact_path,        │
│     training_start/end, metrics            │
│                                            │
│  c) Invalidate ModelRegistry cache         │
│     for old version of this model          │
└───────────────────────────────────────────┘
```

#### 3.7.5 Artifact Store — Pluggable Storage Layer

```python
# ml-service/app/artifacts/base.py
from typing import Protocol
from pathlib import Path
from uuid import UUID

class ArtifactStore(Protocol):
    """Protocol for model artifact storage — local or cloud."""

    async def save_model(self, tenant_id: UUID, model_name: str,
                         version: str, artifacts: dict[str, bytes]) -> str:
        """Save model artifacts. Returns the artifact_path for PG."""
        ...

    async def load_model(self, artifact_path: str) -> dict[str, bytes]:
        """Load model artifacts by path. Returns dict of filename → bytes."""
        ...

    async def list_versions(self, tenant_id: UUID, model_name: str) -> list[str]:
        """List available versions for a model."""
        ...
```

**Local implementation** (dev/single-node):
```python
# ml-service/app/artifacts/local_store.py
class LocalArtifactStore:
    def __init__(self, base_dir: str = "/app/models"):
        self.base_dir = Path(base_dir)

    async def save_model(self, tenant_id, model_name, version, artifacts):
        path = self.base_dir / str(tenant_id) / model_name / version
        path.mkdir(parents=True, exist_ok=True)
        for filename, data in artifacts.items():
            (path / filename).write_bytes(data)
        return str(path)

    async def load_model(self, artifact_path):
        path = Path(artifact_path)
        return {f.name: f.read_bytes() for f in path.iterdir() if f.is_file()}
```

**S3/MinIO implementation** (production — added when needed):
```python
# ml-service/app/artifacts/s3_store.py
class S3ArtifactStore:
    def __init__(self, bucket: str, endpoint_url: str = None):
        self.s3 = boto3.client('s3', endpoint_url=endpoint_url)
        self.bucket = bucket
    # ... same interface, different backend
```

#### 3.7.6 Feedback — PostgreSQL-Backed (Replaces Pickle)

```python
# ml-service/app/feedback/service.py
class FeedbackService:
    def __init__(self, pg_session):
        self.pg = pg_session

    async def store_feedback(self, tenant_id: UUID, feedback: FeedbackRequest) -> str:
        """Write feedback directly to PG feedback table."""
        feedback_id = uuid4()
        await self.pg.execute(
            """INSERT INTO feedback
               (id, tenant_id, asset_id, sensor_id, prediction_id,
                payload_normalized, prediction_label, probability,
                new_label, correction, feedback_type, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
            feedback_id, tenant_id, feedback.asset_id, feedback.sensor_id,
            feedback.prediction_id, feedback.features, feedback.original_prediction,
            feedback.confidence, feedback.corrected_label, feedback.notes,
            feedback.feedback_type, feedback.user_id
        )
        return str(feedback_id)

    async def get_feedback_stats(self, tenant_id: UUID, model_id: UUID = None) -> dict:
        """Query feedback counts per type, scoped by tenant and optionally model."""
        query = """
            SELECT feedback_type, COUNT(*) as count
            FROM feedback
            WHERE tenant_id = $1
        """
        params = [tenant_id]
        if model_id:
            query += " AND prediction_id IN (SELECT _id FROM ...)"  # join via MongoDB prediction
            # OR: store model_version_id directly in feedback table
        query += " GROUP BY feedback_type"
        rows = await self.pg.fetch(query, *params)
        return {row['feedback_type']: row['count'] for row in rows}
```

#### 3.7.7 Config — New Settings

```python
class Settings(BaseSettings):
    # ... existing ...
    POSTGRES_URL: str = "postgresql+asyncpg://..."     # NEW: feedback + model versions
    API_KEY: str = ""                                   # NEW: validate inbound requests
    ARTIFACT_STORE_TYPE: str = "local"                  # NEW: "local" | "s3"
    ARTIFACT_STORE_PATH: str = "/app/models"            # NEW: base path for local store
    S3_BUCKET: str = ""                                 # NEW: for S3 store (future)
    S3_ENDPOINT_URL: str = ""                           # NEW: for MinIO (future)
    MAX_LOADED_MODELS: int = 10                         # NEW: ModelRegistry LRU capacity
    DEFAULT_REFRESH_INTERVAL_SEC: int = 60              # NEW: how often to refresh defaults from PG
    INCLUDE_ORIGINAL_DATA_ON_RETRAIN: bool = True       # NEW: fixes catastrophic forgetting
    FEEDBACK_WEIGHT_MULTIPLIER: float = 3.0             # NEW: feedback samples get Nx weight
```

### 3.8 Frontend — Refactored Architecture

#### 3.8.0 Design Principles

1. **Tenant-first context**: A global `TenantContext` provides `tenant_id`, `site_id`, and user info to every component. All API calls include tenant context.
2. **i18n from the start**: Every user-visible string goes through `react-i18next`. Translation files are JSON per locale. RTL supported via MUI `direction`.
3. **Feature-based folder structure**: Each domain (auth, site-setup, predictions, ml-management, alerts, dashboard) is a self-contained folder with its pages, components, hooks, and API functions.
4. **Shared typed API layer**: One `api/` folder with typed request/response interfaces shared across all features. No raw `axios` calls in page components.
5. **Lightweight state management**: React Context for auth/tenant state + `react-query` (TanStack Query) for server state caching, background refetching, and optimistic updates.

#### 3.8.1 Refactored Folder Structure

```
frontend/src/
├── App.tsx                             # Router, ThemeProvider, i18n, TenantProvider
├── index.tsx                           # ReactDOM entry
│
├── i18n/                               # --- Internationalization ---
│   ├── index.ts                        # i18next init: language detection, fallback
│   ├── locales/
│   │   ├── en/                         # English (default)
│   │   │   ├── common.json             # Shared: buttons, labels, errors, nav items
│   │   │   ├── dashboard.json          # Dashboard-specific strings
│   │   │   ├── auth.json               # Login, Register, RBAC labels
│   │   │   ├── sensors.json            # Sensor/asset/site labels
│   │   │   ├── predictions.json        # Prediction, feedback labels
│   │   │   ├── ml.json                 # ML management labels
│   │   │   ├── alerts.json             # Alarm rules, events, work orders
│   │   │   └── faults.json             # 34 fault type display names
│   │   ├── ar/                         # Arabic (RTL)
│   │   │   └── ... (same files)
│   │   └── {locale}/                   # Additional locales
│   │       └── ...
│   └── useTranslation.ts              # Re-export hook with namespace typing
│
├── contexts/                           # --- Global React contexts ---
│   ├── AuthContext.tsx                  # Current user, token, login/logout actions
│   ├── TenantContext.tsx               # Active tenant_id, site_id, tenant list
│   │                                   # Provides: switchTenant(), switchSite()
│   └── ThemeContext.tsx                # Light/dark mode toggle, RTL direction
│
├── api/                                # --- Typed API client layer ---
│   ├── client.ts                       # Axios instance: baseURL from env, JWT interceptor,
│   │                                   #   401 → redirect to login, tenant_id header injection
│   ├── types.ts                        # Shared TypeScript interfaces:
│   │                                   #   Tenant, Site, Gateway, Asset, Sensor, AssetHealth,
│   │                                   #   SensorReading, Prediction, Feedback,
│   │                                   #   MLModel, MLModelVersion, ModelDeployment,
│   │                                   #   AlarmRule, AlarmEvent, WorkOrder, User, etc.
│   ├── auth.ts                         # login(), register(), refreshToken(), getMe()
│   ├── siteSetup.ts                    # getSites(), getAssets(), getSensors(), etc.
│   ├── predictions.ts                  # getPredictions(), getTelemetry(), submitFeedback()
│   ├── ml.ts                           # getModels(), getVersions(), deploy(), retrain()
│   ├── alerts.ts                       # getAlarmRules(), getEvents(), acknowledgeEvent(), etc.
│   ├── dashboard.ts                    # getDashboard(), getAssetHealth()
│   └── websocket.ts                    # createWebSocket(token, tenantId) — authenticated, scoped
│
├── hooks/                              # --- Shared custom hooks ---
│   ├── useAuth.ts                      # Shortcut to AuthContext
│   ├── useTenant.ts                    # Shortcut to TenantContext
│   ├── useWebSocket.ts                 # Hook wrapping authenticated WebSocket lifecycle
│   └── useDebounce.ts                  # Common utility
│
├── components/                         # --- Shared UI components ---
│   ├── Layout/
│   │   ├── AppLayout.tsx               # AppBar + Drawer (reads nav from i18n)
│   │   ├── TenantSwitcher.tsx          # Dropdown: select tenant, select site
│   │   ├── LanguageSwitcher.tsx         # Dropdown: select language (en, ar, ...)
│   │   ├── ThemeToggle.tsx             # Light/dark mode button
│   │   └── Breadcrumb.tsx             # Tenant > Site > Asset > Sensor path
│   ├── ErrorBoundary.tsx              # Catches uncaught errors; shows fallback UI
│   ├── ProtectedRoute.tsx             # Auth gate + token expiry check
│   ├── LoadingSkeleton.tsx            # Placeholder skeletons for tables/cards
│   └── ConfirmDialog.tsx              # Reusable confirmation modal
│
├── features/                           # --- Feature modules (one per domain) ---
│   ├── auth/
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   └── Register.tsx
│   │   └── components/
│   │       └── LoginForm.tsx
│   │
│   ├── dashboard/
│   │   ├── pages/
│   │   │   └── Dashboard.tsx           # Tenant-scoped: stats, charts, recent anomalies
│   │   └── components/
│   │       ├── StatsCards.tsx           # Extracted from current Dashboard
│   │       ├── SensorChart.tsx         # Reusable Recharts wrapper
│   │       ├── RecentPredictions.tsx   # Anomaly list with drill-down
│   │       └── AssetHealthOverview.tsx # NEW: health scores per asset (ERD: AssetHealth)
│   │
│   ├── site-setup/                     # --- NEW: Tenant/Site/Gateway/Asset/Sensor management ---
│   │   ├── pages/
│   │   │   ├── SitesPage.tsx           # Site list + CRUD
│   │   │   ├── GatewaysPage.tsx        # Gateway list per site + CRUD
│   │   │   ├── AssetsPage.tsx          # Asset list grouped by site + CRUD
│   │   │   ├── SensorsPage.tsx         # Sensor list grouped by asset + CRUD
│   │   │   ├── AssetDetailPage.tsx     # Single asset: sensors, health, recent predictions
│   │   │   ├── AssetHealthPage.tsx     # Health scores per asset, trend, status indicators
│   │   │   └── TenantAdminPage.tsx     # Tenant profile, user management (admin only)
│   │   └── components/
│   │       ├── AssetTree.tsx           # Hierarchical tree: Site → Gateway → Asset → Sensor
│   │       ├── SensorForm.tsx          # Create/edit sensor with site/asset context
│   │       └── AssetHealthCard.tsx     # Health score + status indicator
│   │
│   ├── predictions/
│   │   ├── pages/
│   │   │   ├── PredictionsPage.tsx     # Tenant-scoped prediction history with filters
│   │   │   ├── FeedbackPage.tsx        # Feedback submission (sensor readings + corrections)
│   │   │   ├── RealtimeDataPage.tsx    # Authenticated WebSocket with tenant filter
│   │   │   └── FaultTypesPage.tsx      # Fault reference (labels from i18n faults.json)
│   │   └── components/
│   │       ├── PredictionTable.tsx     # Reusable table with model version column
│   │       ├── FeedbackDialog.tsx      # Extracted feedback dialog
│   │       └── PredictionCard.tsx      # Existing component, now with i18n
│   │
│   ├── ml-management/                  # --- NEW: ML lifecycle management ---
│   │   ├── pages/
│   │   │   ├── ModelsPage.tsx          # List ML models + versions + metrics comparison
│   │   │   ├── ModelDetailPage.tsx     # Single model: versions, deployments, performance graph
│   │   │   ├── DeploymentsPage.tsx     # Active deployments, per-asset model bindings
│   │   │   └── RetrainPage.tsx         # Trigger retrain with tenant/model/feedback selection
│   │   └── components/
│   │       ├── VersionCompareChart.tsx # Recharts: accuracy/f1/precision across versions
│   │       ├── DeploymentTimeline.tsx  # Visual: which version was active when
│   │       └── AssetModelBindingTable.tsx # Which model version is bound to which asset
│   │
│   ├── alerts/                         # --- NEW: Alert management ---
│   │   ├── pages/
│   │   │   ├── AlarmRulesPage.tsx      # CRUD alarm rules (threshold, operator, severity)
│   │   │   ├── AlarmEventsPage.tsx     # Event list with acknowledge/resolve actions
│   │   │   ├── NotificationLogPage.tsx # Notification dispatch history
│   │   │   └── WorkOrdersPage.tsx      # Work order list: create, assign, track, complete
│   │   └── components/
│   │       ├── AlarmRuleForm.tsx        # Create/edit alarm rule
│   │       ├── EventStatusBadge.tsx    # open | acknowledged | resolved | cleared
│   │       └── WorkOrderCard.tsx       # Work order detail with status workflow
│   │
│   └── settings/
│       ├── pages/
│       │   └── SettingsPage.tsx         # User preferences, notification actions
│       └── components/
│           ├── NotificationActionList.tsx # Extracted from current Settings
│           └── GeneralSettingsForm.tsx    # Auto-refresh, threshold config
│
├── utils/                              # --- Shared utilities ---
│   ├── formatters.ts                   # formatDate(date, locale), formatNumber()
│   └── constants.ts                    # API routes, default settings
│
└── types/                              # --- Global TypeScript types ---
    └── index.ts                        # Re-export from api/types.ts + app-specific types
```

#### 3.8.2 Tenant Context — Multi-Tenant Navigation

```typescript
// frontend/src/contexts/TenantContext.tsx
interface TenantContextValue {
  tenants: Tenant[];              // All tenants the user has access to
  activeTenant: Tenant | null;    // Currently selected tenant
  activeSite: Site | null;        // Currently selected site (optional drill-down)
  switchTenant: (tenantId: string) => void;
  switchSite: (siteId: string | null) => void;
  isLoading: boolean;
}

// On login:
// 1. Decode JWT → extract tenant_id (primary tenant)
// 2. Fetch /auth/me → get list of accessible tenants (for multi-tenant admins)
// 3. Set activeTenant = primary tenant
// 4. Fetch /site-setup/sites?tenant_id=... → populate site list

// Every API call reads from TenantContext:
// api/client.ts interceptor:
//   config.headers['X-Tenant-Id'] = activeTenant.id;
//   config.params = { ...config.params, tenant_id: activeTenant.id };
```

**TenantSwitcher** in the AppBar:
```
[Acme Corp ▼] → [Plant A ▼] → Dashboard
                                 └─ showing data for Acme Corp / Plant A
```

#### 3.8.3 i18n — Internationalization Architecture

**Framework:** `react-i18next` (most popular React i18n, supports namespaces, lazy loading, plurals).

```typescript
// frontend/src/i18n/index.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';

i18n
  .use(Backend)                    // Load translations from /locales/{lng}/{ns}.json
  .use(LanguageDetector)           // Detect language from browser/localStorage/URL
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ['en', 'ar'],   // Add more as needed
    ns: ['common', 'dashboard', 'auth', 'sensors', 'predictions', 'ml', 'alerts', 'faults'],
    defaultNS: 'common',
    interpolation: { escapeValue: false },  // React already escapes
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    }
  });
```

**Usage in components:**
```tsx
// Before (hardcoded):
<Typography variant="h4">🔮 ML Prediction History</Typography>
<Button>Submit Feedback</Button>

// After (i18n):
const { t } = useTranslation('predictions');
<Typography variant="h4">{t('predictionHistory.title')}</Typography>
<Button>{t('feedback.submitButton')}</Button>
```

**Translation file example (`en/predictions.json`):**
```json
{
  "predictionHistory": {
    "title": "ML Prediction History",
    "totalLabel": "Total: {{count}} predictions",
    "noData": "No predictions yet. Waiting for sensor data..."
  },
  "feedback": {
    "title": "Sensor Data Feedback & Anomalies",
    "submitButton": "Submit Feedback for Selected",
    "dialogTitle": "Submit Feedback for {{count}} Reading(s)",
    "successMessage": "Feedback submitted successfully!"
  }
}
```

**Fault type labels (`en/faults.json`):**
```json
{
  "normal": "Normal (No Fault)",
  "bearing_overgrease_churning": "Bearing Overgrease Churning",
  "electrical_fluting": "Electrical Fluting",
  "phase_unbalance": "Phase Unbalance",
  ...
}
```

**RTL support (Arabic):**
```typescript
// App.tsx — dynamically set direction based on language
const { i18n } = useTranslation();
const direction = i18n.language === 'ar' ? 'rtl' : 'ltr';
const theme = createTheme({ direction, palette: { ... } });

// In index.html or App.tsx:
document.dir = direction;
```

#### 3.8.4 Authenticated WebSocket

```typescript
// frontend/src/api/websocket.ts
export function createWebSocket(token: string, tenantId: string): WebSocket {
  const wsUrl = `${WS_BASE_URL}/stream?token=${encodeURIComponent(token)}`;
  const ws = new WebSocket(wsUrl);

  // Server-side: validates JWT, extracts tenant_id, only streams
  // data belonging to that tenant (see mqtt-ingestion Phase 3B.12)

  return ws;
}

// frontend/src/hooks/useWebSocket.ts
export function useWebSocket(onMessage: (data: any) => void) {
  const { token } = useAuth();
  const { activeTenant } = useTenant();

  useEffect(() => {
    if (!token || !activeTenant) return;

    const ws = createWebSocket(token, activeTenant.id);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    return () => ws.close();
  }, [token, activeTenant?.id]);
}
```

#### 3.8.5 New Pages — Route Map

```typescript
// App.tsx — Refactored routes
<Routes>
  {/* Public */}
  <Route path="/login" element={<Login />} />
  <Route path="/register" element={<Register />} />

  {/* Protected — wrapped in Layout + TenantProvider */}
  <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
    {/* Dashboard */}
    <Route index element={<Dashboard />} />

    {/* Site Setup (NEW) */}
    <Route path="sites" element={<SitesPage />} />
    <Route path="gateways" element={<GatewaysPage />} />
    <Route path="assets" element={<AssetsPage />} />
    <Route path="assets/:assetId" element={<AssetDetailPage />} />
    <Route path="asset-health" element={<AssetHealthPage />} />
    <Route path="sensors" element={<SensorsPage />} />
    <Route path="admin/tenant" element={<TenantAdminPage />} />

    {/* Predictions */}
    <Route path="realtime" element={<RealtimeDataPage />} />
    <Route path="predictions" element={<PredictionsPage />} />
    <Route path="fault-types" element={<FaultTypesPage />} />
    <Route path="feedback" element={<FeedbackPage />} />

    {/* ML Management (NEW) */}
    <Route path="ml/models" element={<ModelsPage />} />
    <Route path="ml/models/:modelId" element={<ModelDetailPage />} />
    <Route path="ml/deployments" element={<DeploymentsPage />} />
    <Route path="ml/retrain" element={<RetrainPage />} />

    {/* Alerts (NEW) */}
    <Route path="alerts/rules" element={<AlarmRulesPage />} />
    <Route path="alerts/events" element={<AlarmEventsPage />} />
    <Route path="alerts/notifications" element={<NotificationLogPage />} />
    <Route path="alerts/work-orders" element={<WorkOrdersPage />} />

    {/* Settings */}
    <Route path="settings" element={<SettingsPage />} />
  </Route>
</Routes>
```

**Updated sidebar navigation:**
```
Dashboard
──────────────
Site Setup
  ├─ Sites
  ├─ Gateways
  ├─ Assets
  ├─ Asset Health
  ├─ Sensors
  └─ Tenant Admin (admin only)
──────────────
Monitoring
  ├─ Real-time Data
  ├─ Predictions
  ├─ Feedback
  └─ Fault Types
──────────────
ML Management
  ├─ Models & Versions
  ├─ Deployments
  └─ Retrain
──────────────
Alerts
  ├─ Alarm Rules
  ├─ Events
  ├─ Notification Log
  └─ Work Orders
──────────────
Settings
```

#### 3.8.6 Config — New Dependencies

```json
// package.json additions:
{
  "dependencies": {
    "react-i18next": "^14.0.0",       // i18n framework
    "i18next": "^23.0.0",             // Core i18n engine
    "i18next-browser-languagedetector": "^7.0.0",  // Detect browser language
    "i18next-http-backend": "^2.0.0", // Load translations lazily
    "@tanstack/react-query": "^5.0.0" // Server state management + caching
  }
}
```

---

## Part 4: Implementation Roadmap

### Phase 0 — Prerequisites & Foundation

| Task | Details |
|---|---|
| Add PostgreSQL to docker-compose | `postgres:16`, volume, health check (see Appendix A) |
| Set up SQLAlchemy 2.0 async + Alembic | `asyncpg` driver, `Base = declarative_base()`, migration scaffolding |
| Create `backend-api/app/db/postgres.py` | Async engine factory, `get_pg_session` dependency |
| Create `backend-api/app/common/base_model.py` | `AuditMixin` with soft-delete fields per reference ERD |
| Run initial Alembic migration | Creates all tables from Section 3.5 |
| Add `POSTGRES_URL` to mqtt-ingestion config | Read-only PG connection for sensor registry + model bindings |
| Add `API_KEY` to mqtt-ingestion config | For authenticated ML service calls |
| Create MongoDB collections with JSON Schema validation | `telemetry_raw` + `predictions` with required `tenant_id` (Section 3.6.2) |
| Add TTL indexes to MongoDB | `telemetry_raw` (30d), `predictions` (90d) |
| Add `POSTGRES_URL` to ml-service config | For model version metadata and feedback storage |
| Add `API_KEY` to ml-service config | For inbound request authentication |
| Add `ARTIFACT_STORE_TYPE` to ml-service config | `local` (default) or `s3` (future) |
| Install frontend dependencies | `react-i18next`, `i18next`, `i18next-browser-languagedetector`, `i18next-http-backend`, `@tanstack/react-query` |
| Create frontend `i18n/locales/en/` directory | Stub JSON files for all namespaces: `common`, `auth`, `dashboard`, `sensors`, `predictions`, `ml`, `alerts`, `faults`, `settings` |
| Fix `auth.ts` hardcoded API URL | Replace `const API_URL = 'http://localhost:8008'` with `import.meta.env.VITE_API_URL` (or CRA's `process.env.REACT_APP_API_URL`) |

### Phase 1 — Modularize All Services Into Domain Folders

#### Phase 1A — Backend API

**Goal:** Break `backend-api/app/main.py` (500 lines) into the 6 domain modules. All endpoints still use MongoDB during this phase — pure structural refactor.

| Step | Module | Action |
|---|---|---|
| 1A.1 | `common/` | Create `database.py` (get_pg_session, get_mongo_db), `dependencies.py` (get_current_user, get_current_tenant), `base_model.py`, `exceptions.py`, `pagination.py` |
| 1A.2 | `auth/` | Move `/register`, `/login`, `/me` + JWT logic + `get_current_user` dependency. Add `security.py` for password hashing & JWT encode/decode |
| 1A.3 | `site_setup/` | Move `/sensors`, `/sensor-readings`, `/sensors/{id}/data`, `/settings`, `/settings/all-users`. These will later expand to include sites, gateways, assets |
| 1A.4 | `predictions/` | Move `/predictions`, `/feedback`. Reads from MongoDB (telemetry/predictions), writes feedback |
| 1A.5 | `ml_management/` | Move `/retrain`, model version listing. Proxy to ML service |
| 1A.6 | `alerts/` | Move `/test-notification`. Placeholder for alarm rules and events |
| 1A.7 | `dashboard/` | Move `/dashboard` |
| 1A.8 | `main.py` | Wire all routers via `app.include_router(auth_router, prefix="/auth")`, etc. |
| 1A.9 | Tests | Mirror folder structure: `tests/auth/`, `tests/site_setup/`, etc. |

#### Phase 1B — mqtt-ingestion Modularization

**Goal:** Break the monolithic 517-line `MQTTClient` into the folder structure from Section 3.4.4. No tenant/ML changes yet — pure structural refactor.

| Step | Module | Action |
|---|---|---|
| 1B.1 | `ingestion/mqtt_client.py` | Extract MQTT connect/disconnect/subscribe logic. Keep `_on_message` as a thin dispatcher that calls `MessageHandler` |
| 1B.2 | `ingestion/message_handler.py` | Extract `_store_data()` — the main processing function. For now, keep existing logic (no tenant resolution yet) |
| 1B.3 | `ingestion/topic_parser.py` | Create `parse_topic(topic) → ParsedTopic` — initially returns just `sensor_code` from the existing `sensors/{sensor_id}` pattern |
| 1B.4 | `features/sliding_window.py` | Extract `sensor_windows` dict + window management into `SlidingWindowManager` class |
| 1B.5 | `features/extractors.py` | Move `_extract_24_features_from_data()` and `_extract_statistical_features_from_window()`. **Delete** `_extract_features_from_complex_data()` (the one with `random.uniform()`) |
| 1B.6 | `prediction/ml_client.py` | Extract `_get_ml_prediction()` into `MLClient` class with **singleton** `httpx.AsyncClient` (fixes I13) |
| 1B.7 | `storage/telemetry_writer.py` | Extract MongoDB `sensor_data` insert into `TelemetryWriter` |
| 1B.8 | `storage/prediction_writer.py` | Extract MongoDB `sensor_readings` insert (prediction part) into `PredictionWriter` |
| 1B.9 | `alerts/publisher.py` | Extract `_trigger_fault_alert()` into `AlertPublisher`. Keep the existing HTTP call to backend-api — Phase 4 will replace the destination endpoint with `POST /alerts/evaluate` |
| 1B.10 | `streaming/websocket.py` | Move WebSocket `/stream` endpoint out of `main.py` |
| 1B.11 | Delete `notifications.py` | Alert dispatch will be handled by backend-api `alerts/` module (Phase 4). The publisher only emits events |
| 1B.12 | Tests | `tests/test_topic_parser.py`, `tests/test_sliding_window.py`, `tests/test_extractors.py` |

#### Phase 1C — ml-service Modularization

**Goal:** Break the monolithic 460-line `main.py` and tightly-coupled `ModelManager` + `RetrainingPipeline` into the folder structure from Section 3.7.1. No multi-tenancy yet — pure structural refactor.

| Step | Module | Action |
|---|---|---|
| 1C.1 | `common/` | Create `database.py` (PG session placeholder — no-op until Phase 2), `auth.py` (API key validation — disabled by default until Phase 5), `exceptions.py` |
| 1C.2 | `prediction/router.py` | Move `POST /predict` and `POST /predict-batch` endpoints |
| 1C.3 | `prediction/feature_converter.py` | Move `convert_structured_to_features()` out of `main.py`. **Fix `predict_batch` to call it** (fixes M9) |
| 1C.4 | `prediction/schemas.py` | Move `PredictionRequest`, `PredictionResponse`, `TopPrediction` from current `schemas.py` |
| 1C.5 | `models/router.py` | Move `GET /models`, `GET /models/{version}`, `POST /models/{version}/activate`, `GET /metrics` |
| 1C.6 | `models/manager.py` | Move `ModelManager` class from `model.py` — same logic, just relocated |
| 1C.7 | `models/registry.py` | Create `ModelRegistry` wrapper around `ModelManager`. Initially holds a single model (no multi-version yet) — this is the seam for Phase 3C |
| 1C.8 | `models/schemas.py` | Move `ModelInfo`, `HealthResponse` |
| 1C.9 | `feedback/router.py` | Move `POST /feedback`, `GET /feedback/stats` |
| 1C.10 | `feedback/service.py` | Extract feedback logic from `RetrainingPipeline.store_feedback()` and `get_feedback_stats()`. For now, keep pickle storage — will be replaced with PG in Phase 2 |
| 1C.11 | `feedback/schemas.py` | Move `FeedbackRequest`, `FeedbackResponse`, `FeedbackType` |
| 1C.12 | `retraining/router.py` | Move `POST /retrain` |
| 1C.13 | `retraining/pipeline.py` | Move `RetrainingPipeline.retrain_model()` — training logic only, feedback storage now in `feedback/service.py` |
| 1C.14 | `artifacts/base.py` + `artifacts/local_store.py` | Create `ArtifactStore` protocol and `LocalArtifactStore`. Wrap current file I/O in `ModelManager.save_new_version()` and `load_current_model()` behind this interface |
| 1C.15 | `main.py` | Wire all routers: `app.include_router(prediction_router, prefix="/predict", ...)`, etc. Replace global variables with `app.state.model_registry` (fixes M8) |
| 1C.16 | Delete `model.py`, `retrain.py`, `schemas.py` | All code moved to new module locations |
| 1C.17 | Tests | `tests/prediction/test_predict.py`, `tests/models/test_registry.py`, `tests/feedback/test_feedback.py`, `tests/retraining/test_pipeline.py`, `tests/artifacts/test_local_store.py` |

#### Phase 1D — Frontend Modularization

**Goal:** Restructure the flat `frontend/src/pages/` into feature-based folders (Section 3.8.1). Install new dependencies. No multi-tenancy or i18n logic yet — pure structural refactor.

| Step | Action |
|---|---|
| 1D.1 | Install new dependencies: `npm install react-i18next i18next i18next-browser-languagedetector i18next-http-backend @tanstack/react-query` |
| 1D.2 | Create folder structure: `features/auth/`, `features/dashboard/`, `features/site-setup/`, `features/predictions/`, `features/ml-management/`, `features/alerts/`, `features/settings/`, `features/chatbot/` |
| 1D.3 | Move `Login.tsx` → `features/auth/pages/Login.tsx`, `Register.tsx` → `features/auth/pages/Register.tsx`. Move `auth.ts` → `api/auth.ts` (shared typed API layer per Section 3.8.1) |
| 1D.4 | Move `Dashboard.tsx` → `features/dashboard/pages/DashboardPage.tsx`. Extract chart components into `features/dashboard/components/` (MotorTempChart, MotorVibChart, PumpTempChart, PumpUltraChart, RecentPredictions) |
| 1D.5 | Move `Sensors.tsx` → `features/site-setup/pages/SensorsPage.tsx`, `RealtimeData.tsx` → `features/predictions/pages/RealtimeDataPage.tsx` |
| 1D.6 | Move `Predictions.tsx` → `features/predictions/pages/PredictionsPage.tsx`, `Feedback.tsx` → `features/predictions/pages/FeedbackPage.tsx`, `FaultTypes.tsx` → `features/predictions/pages/FaultTypesPage.tsx` |
| 1D.7 | Move `Settings.tsx` → `features/settings/pages/SettingsPage.tsx` |
| 1D.8 | Create `components/` — extract reusable pieces: `ErrorBoundary.tsx`, `ProtectedRoute.tsx`, `LoadingSkeleton.tsx`, `ConfirmDialog.tsx` (per Section 3.8.1) |
| 1D.9 | Create `api/client.ts` — move Axios instance + interceptor from `api.ts`. Create `api/websocket.ts` — move `connectWebSocket()`. Create `api/types.ts` with shared TypeScript interfaces |
| 1D.10 | Fix all hardcoded `axios.get('http://localhost:8008/...')` calls in Feedback.tsx and Predictions.tsx — route through `apiClient` (fixes F13) |
| 1D.11 | Create `hooks/useAuth.ts`, `hooks/useTenant.ts`, `hooks/useWebSocket.ts` — shared custom hooks (per Section 3.8.1) |
| 1D.12 | Create stub pages (empty shells) for new routes: `SitesPage`, `GatewaysPage`, `AssetsPage`, `AssetDetailPage`, `TenantAdminPage`, `ModelsPage`, `ModelDetailPage`, `DeploymentsPage`, `RetrainPage`, `AlarmRulesPage`, `AlarmEventsPage`, `NotificationLogPage`, `WorkOrdersPage` |
| 1D.13 | Update `App.tsx` — wire all new routes per Section 3.8.5 route map. Use lazy imports (`React.lazy`) for code splitting |
| 1D.14 | Update `Layout.tsx` — restructure sidebar with grouped navigation sections (Dashboard, Site Setup, Predictions, ML Management, Alerts, Settings) using MUI `ListSubheader` |
| 1D.15 | Tests | Basic render tests for each moved page. Per-feature test folders (e.g., `features/auth/__tests__/`, `features/dashboard/__tests__/`) |

### Phase 2 — Migrate Core Business to PostgreSQL

**Goal:** Move all relational entities to PostgreSQL. MongoDB retains only `telemetry_raw` and `predictions`.

| Step | Action | Rollback |
|---|---|---|
| 2.1 | Define SQLAlchemy ORM models: `Tenant`, `User` in `auth/models.py` and `site_setup/models.py` | — |
| 2.2 | Write + run Alembic migration for tenants, users, user_settings, fault_actions | `alembic downgrade` |
| 2.3 | One-time migration script: copy MongoDB `users` + `user_settings` → PostgreSQL | Keep MongoDB data |
| 2.4 | Update `auth/service.py` to read/write PostgreSQL | Feature flag `USE_POSTGRES_AUTH` |
| 2.5 | Update `site_setup/service.py` for settings (PG) | Feature flag |
| 2.6 | Add `Site`, `Gateway`, `Asset`, `Sensor`, `AssetHealth` ORM models | Alembic migration |
| 2.7 | Migrate MongoDB `sensors` collection → PG `sensors` table (with tenant/site/asset hierarchy) | Migration script |
| 2.8 | Add full ML management tables: `ml_models`, `ml_model_versions`, `ml_model_deployments`, `asset_model_versions` | Alembic migration |
| 2.9 | Add `POSTGRES_URL` to ml-service config. Wire `get_pg_session()` dependency in `common/database.py` | |
| 2.10 | ML service writes version metadata to PG `ml_model_versions` after retraining (replaces filesystem-only `metadata.json` tracking). Reads model list from PG instead of scanning `models/versions/` directory | |
| 2.11 | Migrate feedback to PostgreSQL: ML service `feedback/service.py` writes to PG `feedback` table (replaces `feedback_data.pkl` and `feedback_log.json`). Delete pickle files after migration | |
| 2.12 | Seed initial `ml_models` + `ml_model_versions` rows in PG for the existing v1 model. Set `model_artifact_path` to current local path. Mark as `stage='production'` | |
| 2.13 | Add alarm management tables: `notification_types`, `alarm_rules`, `alarm_notification_types`, `alarm_events`, `notification_logs`, `maintenance_work_orders` | Alembic migration |
| 2.14 | Rename MongoDB `sensor_data` → `telemetry_raw`; add JSON Schema validation | |
| 2.15 | Create new MongoDB `predictions` collection with JSON Schema validation | |
| 2.16 | Drop unused MongoDB collections: `users`, `user_settings`, `sensors`, `faults`, `models`, `sensor_readings` | After validation |

### Phase 3 — Multi-Tenancy (All Services)

#### Phase 3A — Backend API Multi-Tenancy

| Step | Action |
|---|---|
| 3A.1 | Add `tenant_id` + `tenant_code` to JWT claims |
| 3A.2 | Create `get_current_tenant()` dependency that extracts tenant from JWT |
| 3A.3 | Enforce tenant filtering on all PG queries via `AuditMixin.tenant_id` (application-level WHERE) |
| 3A.4 | Enforce `tenant_id` filter on all MongoDB reads (dashboard, predictions, telemetry endpoints) |
| 3A.5 | Add tenant management endpoints in `site_setup/router.py` (admin only) |
| 3A.6 | Add site, gateway, asset CRUD endpoints in `site_setup/router.py` |

#### Phase 3B — mqtt-ingestion Multi-Tenancy & ML Routing (Critical)

This is the most impactful phase — it transforms mqtt-ingestion from a tenant-blind pipe into a context-aware, model-routing ingestion engine.

| Step | Action | Resolves |
|---|---|---|
| 3B.1 | **Add PostgreSQL read connection** to mqtt-ingestion config and lifespan. Use `asyncpg` directly (no ORM needed — read-only queries) | I17 |
| 3B.2 | **Create `context/registry.py`** — `SensorRegistryCache` that loads sensor→tenant/site/asset mapping from PG on startup and refreshes every 60s. Query: `SELECT sensors JOIN assets JOIN sites JOIN tenants WHERE is_active AND NOT is_deleted` | I5 |
| 3B.3 | **Create `context/model_bindings.py`** — `ModelBindingCache` that loads `asset_model_versions JOIN ml_model_versions WHERE is_active AND stage='production'` from PG. Maps `asset_id → ModelBinding(model_version_id, version_label)` | I8 |
| 3B.4 | **Implement MQTT topic convention** — Update `topic_parser.py` to handle `{tenant_code}/{site_code}/sensors/{sensor_code}` format. Fallback: if old format `sensors/{sensor_id}`, resolve via registry cache by `sensor_code` | I1 |
| 3B.5 | **Update `message_handler.py`** — On each message: (1) parse topic → sensor_code, (2) lookup `SensorRegistryCache` → `SensorContext`, (3) if not found → log warning + drop message. Pass `SensorContext` to all downstream calls | I5 |
| 3B.6 | **Tenant-scope the sliding window** — Change `SlidingWindowManager` key from `sensor_id` (string) to `(tenant_id, asset_id, sensor_id)` (tuple of UUIDs). This prevents cross-tenant window contamination | I2 |
| 3B.7 | **Tenant-scope `latest_data`** — Change from flat `dict[topic, data]` to `dict[tenant_id, dict[topic, data]]`. WebSocket streams only the requesting tenant's data | I3 |
| 3B.8 | **Update `telemetry_writer.py`** — Write `tenant_id`, `site_id`, `asset_id`, `sensor_id` into every `telemetry_raw` document. MongoDB schema validation will reject documents missing required fields | I4 |
| 3B.9 | **Update `ml_client.py`** — Before calling `/predict`, lookup `ModelBindingCache` by `context.asset_id` to get the `model_version_id`. Send `tenant_id`, `asset_id`, `model_version_id` in the request body. Add `X-API-Key` header | I6, I11 |
| 3B.10 | **Update `prediction_writer.py`** — Write `tenant_id`, `site_id`, `asset_id`, `sensor_id`, `model_version_id`, `model_version_label` into every `predictions` document. Link back to `telemetry_raw_id` | I7 |
| 3B.11 | **Update `alerts/publisher.py`** — Include `tenant_id`, `site_id`, `asset_id`, `sensor_id`, `model_version_id` in the alert event payload. Remove the hardcoded `confidence > 0.6`. Call backend-api `POST /alerts/evaluate` with the enriched tenant-scoped payload (endpoint created in Phase 4). Backend-api evaluates `AlarmRules` from PG and dispatches notifications asynchronously | I15, I16 |
| 3B.12 | **Add WebSocket JWT auth** — Require `token` query param on `/stream`. Validate JWT, extract `tenant_id`. Filter streamed data to that tenant only. Reject unauthenticated connections with `4001` | I10, I12 |
| 3B.13 | **Update `simulate_sensors.py`** — Change topic pattern to `{tenant_code}/{site_code}/sensors/{sensor_code}`. Add `sensor_code` to the JSON payload for fallback resolution | — |

#### Phase 3C — ML Service Multi-Tenancy (Critical)

This phase transforms the ML service from a single-model singleton into a multi-tenant, multi-version prediction engine aligned with the reference ERD's ML Management domain.

| Step | Action | Resolves |
|---|---|---|
| 3C.1 | **Verify PostgreSQL connection** (wired in Phase 2.9). Ensure ml-service reads `ml_model_versions`, `ml_model_deployments`, `feedback` with tenant-scoped queries | M12 |
| 3C.2 | **Update `PredictionRequest` schema** — Add optional `tenant_id`, `asset_id`, `model_version_id` fields. Keep `features` array and structured fields as-is for backward compatibility | M1 |
| 3C.3 | **Implement `ModelRegistry` with LRU cache** — Replace the single global `ModelManager` with the multi-version `ModelRegistry` from Section 3.7.2. On startup, load production model versions from PG `ml_model_deployments WHERE is_production=true`. Serve predictions by `model_version_id` lookup | M2 |
| 3C.4 | **Add `refresh_defaults()` periodic task** — Every 60s (configurable), query PG for current production deployments per tenant and update `ModelRegistry._default_version` map. Config changes propagate within one refresh cycle (acceptable for infrequent deployment operations) | M2 |
| 3C.5 | **Update prediction service** — On each `/predict` call: if `model_version_id` is provided, use it; otherwise fall back to `get_default_model(tenant_id)`. Return the actual PG UUID `model_version_id` and `model_version_label` in the response (not just "v1") | M5 |
| 3C.6 | **Fix `predict_batch` to call `convert_structured_to_features()`** — Ensure batch predictions go through the same feature conversion as single predictions | M9 |
| 3C.7 | **Add tenant scoping to PG feedback** (PG writes established in Phase 2.11) — Update `FeedbackService.store_feedback()` to require and write `tenant_id`, `asset_id`, `sensor_id`, `prediction_id`, `model_version_id`. Ensure all queries filter by `tenant_id` | M3, M17 |
| 3C.8 | **Tenant-scoped feedback stats** — `FeedbackService.get_feedback_stats()` queries PG with `WHERE tenant_id = ?` and optional `model_id` filter. Returns per-type counts, per-model breakdown, date ranges | M17 |
| 3C.9 | **Fix catastrophic forgetting in retraining** — `RetrainingPipeline.retrain_model()` loads original training dataset from artifact store alongside feedback from PG. Feedback samples are weighted `FEEDBACK_WEIGHT_MULTIPLIER`x (default 3x). Original data preserves knowledge of all fault classes | M13 |
| 3C.10 | **Fit new scaler during retrain** — Instead of reusing the old `feature_scaler.pkl`, fit a new `StandardScaler` on the merged training data (original + feedback). Save it with the new model version | M14 |
| 3C.11 | **Tenant-scoped retraining** — `POST /retrain` requires `tenant_id` and `model_id`. Loads only that tenant's feedback. Saves new version under tenant's artifact namespace (`{tenant_id}/{model_name}/{version}/`). Creates PG `ml_model_versions` row with `stage='staging'` | M4 |
| 3C.12 | **Atomic model activation** — Replace `shutil.copy()` in `activate_version()` with: (a) load new version into `ModelRegistry`, (b) update PG `ml_model_deployments` (end old deployment, start new), (c) swap `_default_version` reference atomically, (d) evict old version from cache. No file copying during live serving | M16 |
| 3C.13 | **Save artifacts via `ArtifactStore`** — All model save/load goes through the `ArtifactStore` protocol. `model_artifact_path` in PG points to the artifact location (local path or S3 key). Remove direct `shutil.copy()` and `Path` I/O from model management code | M15 |
| 3C.14 | **Wire model version metadata to PG** — After retraining, write to `ml_model_versions`: `semantic_version`, `full_version_label`, `stage`, `model_artifact_path`, `training_start/end`, `accuracy`, `precision_score`, `recall_score`, `f1_score`, `false_alarm_rate`, `dataset_hash`, `feature_schema_hash` | M5, M7 |
| 3C.15 | **Add API key validation middleware (ml-service)** — Reject requests without a valid `X-API-Key` header. Validate against environment variable for now (Phase 5 upgrades to PG `api_keys` table) | M10 |
| 3C.16 | **Add retrain concurrency guard** — Only one retrain can run per `(tenant_id, model_id)` at a time. Use an in-memory `asyncio.Lock` per key (sufficient for single-replica ml-service). Return 409 Conflict if a retrain is already in progress. *Scale-up note: switch to PG advisory lock or Redis distributed lock if running multiple ml-service replicas* | M11 |

#### Phase 3D — Frontend Multi-Tenancy & i18n

This phase transforms the frontend from a single-tenant, English-only SPA into a multi-tenant, multi-language application aligned with all backend changes.

| Step | Action | Resolves |
|---|---|---|
| 3D.1 | **Create `TenantContext`** — `contexts/TenantContext.tsx` per Section 3.8.2. On login, fetch user's tenant list from backend-api `GET /auth/me` (which now returns `tenants[]`). Store `active_tenant_id`, `active_site_id` in context + `localStorage` | F1 |
| 3D.2 | **Add `TenantSwitcher` to AppBar** — Dropdown in `Layout.tsx` showing user's tenants. On switch, update context + refetch all queries. Disable if user has only one tenant | F1 |
| 3D.3 | **Inject `X-Tenant-Id` header** — Update `api/client.ts` Axios request interceptor to read `active_tenant_id` from `TenantContext` and attach `X-Tenant-Id` header on every request | F2 |
| 3D.4 | **Add JWT expiry check** — Update `ProtectedRoute.tsx` to decode JWT and check `exp` claim. Redirect to login if expired. Add `POST /auth/refresh` call if within grace window | F14 |
| 3D.5 | **Set up i18n** — Create `i18n/index.ts` per Section 3.8.3. Configure `i18next` with `LanguageDetector` and `HttpBackend`. Create `i18n/locales/en/` translation files for all namespaces: `common`, `auth`, `dashboard`, `sensors`, `predictions`, `ml`, `alerts`, `faults`, `settings` | F6 |
| 3D.6 | **Add `LanguageSwitcher`** — Dropdown in AppBar (or Settings page) with supported locales. Persist choice in `localStorage` and user settings API | F7 |
| 3D.7 | **Externalize all hardcoded strings** — Replace all inline English text in every page/component with `t('namespace:key')` calls. Start with `common` namespace (shared labels like "Save", "Cancel", "Loading"), then per-feature namespaces | F8 |
| 3D.8 | **Add RTL support** — Configure MUI `ThemeProvider` with `direction: 'rtl'` when locale is Arabic. Add `jss-rtl` plugin. Wrap `<CacheProvider>` with RTL-aware `stylis` plugin | F9 |
| 3D.9 | **Add Arabic translations** — Create `locales/ar/` translation files for all namespaces. Verify RTL layout on all pages | F10 |
| 3D.10 | **Authenticate WebSocket** — Update `connectWebSocket()` to pass JWT token as query param: `ws://host/stream?token=xxx`. Backend filters data to active tenant only (already prepared in Phase 3B.12) | F3 |
| 3D.11 | **Implement Site Setup pages** — `SitesPage` (CRUD for sites within active tenant), `GatewaysPage` (per-site gateways), `AssetsPage` (per-site assets with gateway assignment), `SensorsPage` (per-asset sensors). All use `@tanstack/react-query` + `apiClient` with tenant header | F18, F19, F20 |
| 3D.12 | **Implement Asset Health page** — Real-time health scores per asset. Color-coded health status (Healthy/Warning/Critical). Link to asset detail with prediction history | F21 |
| 3D.13 | **Implement ML Management pages** — `ModelsPage` (list models per tenant), `ModelVersionsPage` (version history with metrics: accuracy, F1, precision, recall), `DeploymentsPage` (promote staging→production, rollback). Retrain trigger with progress indicator | F22 |
| 3D.14 | **Implement Alert Management pages** — `AlarmRulesPage` (CRUD alarm rules per asset/sensor), `AlarmEventsPage` (live alarm feed with acknowledge/clear actions), `WorkOrdersPage` (maintenance work orders with status tracking) | F23 |
| 3D.15 | **Replace hardcoded fault types** — `FaultTypesPage` fetches fault labels from backend-api (or ML service model metadata) instead of hardcoded 34-item array. Support tenant-specific custom fault types | F24 |
| 3D.16 | **Fix Settings page** — Replace hardcoded model info ("XGBoost v1.0") with live data from ML Management API. Replace hardcoded URLs with config. Dark mode toggle persisted in user settings | F15, F16 |
| 3D.17 | **Tenant-scoped Dashboard** — Dashboard stats, charts, and predictions show only active tenant's data. Add site filter dropdown for multi-site tenants | F4 |
| 3D.18 | **Registration with tenant** — Update RegisterPage to accept optional `tenant_code` (invite-based) or create a new tenant (self-service). Backend creates `Tenant` + `User` in one transaction | F5 |

### Phase 4 — Alert Processing (Backend API `alerts/` Module)

**Goal:** Implement the full alarm rules engine inside backend-api's existing `alerts/` domain module. mqtt-ingestion calls `POST /alerts/evaluate` on backend-api. Rule evaluation is synchronous (fast PG query); notification dispatch is asynchronous (background task).

| Step | Action |
|---|---|
| 4.1 | **Add `POST /alerts/evaluate` endpoint** in `backend-api/app/alerts/router.py`. Accepts alert event payload from mqtt-ingestion (tenant_id, asset_id, sensor_id, prediction_label, probability, model_version_id, prediction_id, timestamp). Secured with API key (`X-API-Key` header) |
| 4.2 | **Implement `AlertEvaluationService`** in `alerts/service.py` — Reads `alarm_rules` from PG for the event's `tenant_id + asset_id + sensor_id`. Evaluates each matching `AlarmRule` (threshold + operator) against the `triggered_value` (prediction probability) |
| 4.3 | For matched rules: creates `alarm_events` row in PG, looks up `alarm_notification_types` to find notification channels |
| 4.4 | **Implement `NotificationDispatcher`** in `alerts/notifications.py` — Dispatches via `notification_types` config (email/SMS/webhook/Slack). Runs as `asyncio.create_task()` to avoid blocking the HTTP response to mqtt-ingestion |
| 4.5 | Writes `notification_logs` for every dispatch attempt (success or failure) |
| 4.6 | Auto-creates `maintenance_work_orders` for critical-severity alarm events |
| 4.7 | **Update mqtt-ingestion `alerts/publisher.py`** — Replace the old backend-api call with `httpx.AsyncClient.post()` to `POST /alerts/evaluate` (with retry via `tenacity`). Add `X-API-Key` header |
| 4.8 | Remove `notifications.py` entirely from mqtt-ingestion |
| 4.9 | Remove `/settings/all-users` endpoint from backend-api |
| 4.10 | *Scale-up note:* If notification dispatch volume becomes a bottleneck for the backend-api process (hundreds of concurrent dispatches), extract `alerts/` into a standalone service. The module boundary is already clean — only the URL in mqtt-ingestion's `alerts/publisher.py` needs to change |

### Phase 5 — Auth Hardening & Future RBAC Prep

| Step | Action |
|---|---|
| 5.1 | Implement `api_keys` table seeding: generate keys for `mqtt-ingestion` and `ml-service` |
| 5.2 | Upgrade API key validation to PG `api_keys` table lookup (ml-service already has env-var validation from Phase 3C.15). Add same middleware to backend-api internal endpoints |
| 5.3 | mqtt-ingestion sends `X-API-Key` header on all outbound calls (already prepared in Phase 3B.9) |
| 5.4 | Add `POST /auth/refresh` for JWT token refresh |
| 5.5 | **(When needed)** Add `roles`, `permissions`, `role_permissions`, `user_roles` tables via Alembic |
| 5.6 | **(When needed)** Create `auth/rbac.py` with `require_permission()` dependency |
| 5.7 | **(When needed)** Replace `if user.role != 'admin'` checks with `Depends(require_permission("resource:action"))` |

### Phase 6 — Operational Improvements (Ongoing)

| Task | Details |
|---|---|
| Circuit breaker for ML calls | Add `tenacity` retry with exponential backoff + circuit breaker in mqtt-ingestion `ml_client.py` |
| Fix catastrophic forgetting | ~~ML retrain pipeline loads original training data alongside feedback~~ (now done in Phase 3C.9) |
| Asset health calculation | Periodic job (cron or Celery beat) computes `AssetHealth` scores from recent predictions per asset and writes to PG |
| Registry cache invalidation | Currently polling every 60s (sufficient for infrequent config changes). *Scale-up:* If sub-second propagation is needed, add PG `LISTEN/NOTIFY` — backend-api does `NOTIFY config_changed` on sensor/model CRUD, services listen and refresh immediately |
| ML model registry monitoring | Track per-model: cache hit rate, load latency, eviction count, prediction latency P50/P95/P99, active model count |
| ML retraining dashboard | Expose `/retrain/status` endpoint: current retrain jobs, queued, history. Integrate with frontend ML Management page |
| Feature drift detection | Compare incoming feature distributions against training data statistics. Log warnings when drift exceeds threshold (future: auto-trigger retrain) |
| Model A/B testing | Support `stage='canary'` in `asset_model_versions`: route a percentage of predictions to a staging model, compare metrics against production |
| Monitoring | Prometheus metrics: prediction latency per tenant, throughput per asset, error rate, sliding window fill levels, cache hit rate |
| Structured logging | JSON logs with `tenant_id`, `asset_id`, `model_version_id`, `correlation_id` on every log line for traceability |
| Frontend error boundary | Global `ErrorBoundary` component with tenant-aware error reporting; per-feature fallback UI |
| Frontend bundle optimization | Lazy routes, tree-shaking unused MUI components, locale-based translation chunk splitting |
| Frontend E2E tests | Cypress or Playwright tests covering critical flows: login → tenant switch → dashboard → create alarm rule → view alarm events |

### Phase 7 — Chatbot / Knowledge Base (Future)

| Step | Action |
|---|---|
| 7.1 | Add `knowledge_base`, `knowledge_embeddings` tables (per reference ERD) |
| 7.2 | Create `chatbot/` domain module in backend-api |
| 7.3 | Add `conversations`, `messages` tables |
| 7.4 | Integrate vector DB or PG `pgvector` for embedding search |
| 7.5 | Add RAG pipeline: user question → embedding → knowledge retrieval → LLM response |

---

## Summary of Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Core business DB** | PostgreSQL | Relational integrity, ACID, deep FK hierarchy (Tenant→Site→Gateway→Asset→Sensor), Alembic migrations |
| **Streaming data DB** | MongoDB (keep) | Append-heavy telemetry and predictions, flexible payload schema, TTL indexes |
| **MongoDB multi-tenancy** | Application-level (`tenant_id` on every document + JSON Schema validation) | Same pattern as PG; `tenant_id` as first key in all compound indexes; schema validation rejects writes without tenant context |
| **ORM** | SQLAlchemy 2.0 async (backend-api), raw asyncpg (mqtt-ingestion read-only) | Full ORM for CRUD services; lightweight driver for high-throughput ingestion |
| **Multi-tenancy in ingestion** | Sensor registry cache from PG + topic convention `{tenant}/{site}/sensors/{sensor}` | Resolves tenant context at message arrival; no coupling to backend-api at runtime |
| **ML model routing** | ModelBindingCache from PG `asset_model_versions` → send `model_version_id` to ML service per prediction | Per-asset model versions; enables staged rollout and A/B testing |
| **Auth strategy** | Simple role column → RBAC tables later | Start shipping fast; `auth/` module absorbs RBAC without affecting other domains |
| **RBAC transition** | `require_permission()` dependency replaces role checks | Other modules don't change — they just add a dependency |
| **Alert delivery** | Backend-api `alerts/` module (no separate service) | mqtt-ingestion calls `POST /alerts/evaluate`; backend-api evaluates rules synchronously, dispatches notifications via `asyncio.create_task()`. One fewer service to deploy. *Scale-up:* extract `alerts/` into standalone service if notification volume demands it — module boundary is already clean |
| **ML lifecycle** | MLModel → Version → Deployment → AssetModelVersion | Per-asset model binding, rollback tracking, staging/production lifecycle |
| **Domain modules** | 6 backend-api folders + 7 mqtt-ingestion folders + 5 ml-service folders + 8 frontend feature folders | Each folder is independently testable and maintainable; frontend mirrors backend domain structure |
| **ML model serving** | `ModelRegistry` with LRU cache, keyed by `model_version_id` (UUID) | Supports multi-tenant, multi-version serving from a single ml-service instance; loads on demand, evicts LRU |
| **ML feedback storage** | PostgreSQL `feedback` table (replaces pickle file) | Tenant-scoped, queryable per model/asset, FK to users, audit trail; pickle had no isolation or query capability |
| **ML retraining** | Original training data + feedback (weighted 3x), new scaler per retrain | Fixes catastrophic forgetting (M13) and stale scaler (M14); feedback amplified but doesn't drown original data |
| **ML artifacts** | `ArtifactStore` protocol: `LocalArtifactStore` → `S3ArtifactStore` later | Pluggable storage; `model_artifact_path` in PG works for both local paths and S3 keys |
| **ML model activation** | In-memory registry swap + PG deployment record (no file copy during serving) | Atomic model switch; no inconsistent state during activation (fixes M16) |
| **Frontend structure** | Feature-based folders (`features/{domain}/`) | Each domain is self-contained (pages, components, services, hooks); mirrors backend module structure |
| **Frontend i18n** | `react-i18next` with namespaced JSON files + `LanguageDetector` | Industry standard for React; lazy-loaded per namespace; browser language auto-detection; RTL support for Arabic |
| **Frontend state** | React Context (auth/tenant) + `@tanstack/react-query` (server state) | Context for cross-cutting concerns; react-query for caching, deduplication, background refetch of API data |
| **Frontend multi-tenancy** | `TenantContext` + `X-Tenant-Id` Axios interceptor + authenticated WebSocket | Tenant context flows through all components; API calls automatically scoped; WebSocket streams filtered server-side |
| **Frontend routing** | React Router v6 with lazy loading, grouped by domain | Code splitting per feature; sidebar mirrors route groups; stub pages for Phase 3D |
| **Migration strategy** | Incremental with feature flags | Zero-downtime; roll back by flipping flag |

---

## Appendix A: Docker Compose Additions

```yaml
  # Add to services:
  postgres:
    image: postgres:16
    container_name: aastreli-postgres
    restart: always
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: aastreli
      POSTGRES_USER: aastreli
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-aastreli_dev}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aastreli"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - aastreli-network

# Add to volumes:
#   postgres_data:

```

Environment variables to add to services:
```yaml
  # backend-api, ml-service:
  - POSTGRES_URL=postgresql+asyncpg://aastreli:${POSTGRES_PASSWORD:-aastreli_dev}@postgres:5432/aastreli

  # mqtt-ingestion:
  - BACKEND_API_URL=http://backend-api:8000      # for alert evaluation (POST /alerts/evaluate)

  # ml-service additional:
  - ARTIFACT_STORE_TYPE=local                    # "local" or "s3"
  - ARTIFACT_STORE_PATH=/app/models              # base path for local store
  - MAX_LOADED_MODELS=10                         # LRU cache capacity
  - API_KEY=${ML_SERVICE_API_KEY:-dev_key}       # inbound auth from mqtt-ingestion
  - INCLUDE_ORIGINAL_DATA_ON_RETRAIN=true        # fixes catastrophic forgetting
  - FEEDBACK_WEIGHT_MULTIPLIER=3.0               # feedback sample weight during retrain

  # mqtt-ingestion additional:
  - ML_API_KEY=${ML_SERVICE_API_KEY:-dev_key}    # outbound auth to ml-service

  # frontend additional (build-time):
  - REACT_APP_API_URL=http://localhost:8008      # backend-api gateway URL
  - REACT_APP_WS_URL=ws://localhost:8002         # mqtt-ingestion WebSocket URL
  - REACT_APP_DEFAULT_LOCALE=en                  # default i18n locale
  - REACT_APP_SUPPORTED_LOCALES=en,ar            # comma-separated locale list
```

## Appendix B: ERD Entity → Module Mapping

| Reference ERD Entity | PostgreSQL Table | Backend Module | Notes |
|---|---|---|---|
| Tenant | `tenants` | `site_setup/` | |
| User | `users` | `auth/` | |
| — | `user_settings` | `site_setup/` | Not in ERD, kept for UI preferences |
| — | `fault_actions` | `site_setup/` | Not in ERD, kept for notification channels |
| Site | `sites` | `site_setup/` | |
| Gateway | `gateways` | `site_setup/` | |
| Asset | `assets` | `site_setup/` | |
| Sensor | `sensors` | `site_setup/` | |
| AssetHealth | `asset_health` | `site_setup/` | |
| TelemetryRaw | MongoDB `telemetry_raw` | `predictions/` | High-throughput, TTL |
| Prediction | MongoDB `predictions` | `predictions/` | High-throughput, TTL |
| Feedback | `feedback` | backend-api: `predictions/`, ml-service: `feedback/` | Written by ml-service `feedback/service.py`; read by both services |
| MLModel | `ml_models` | backend-api: `ml_management/`, ml-service: `models/` | CRUD via backend-api; read by ml-service for model registry |
| MLModelVersion | `ml_model_versions` | backend-api: `ml_management/`, ml-service: `models/` + `retraining/` | Created by ml-service after retrain; read/managed by backend-api |
| MLModelDeployment | `ml_model_deployments` | backend-api: `ml_management/`, ml-service: `models/registry.py` | Managed by backend-api; read by ml-service for default model resolution |
| AssetModelVersion | `asset_model_versions` | backend-api: `ml_management/`, mqtt-ingestion: `context/model_bindings.py` | Managed by backend-api; cached by mqtt-ingestion for ML routing |
| NotificationType | `notification_types` | `alerts/` | |
| AlarmRule | `alarm_rules` | `alerts/` | |
| AlarmNotificationType | `alarm_notification_types` | `alerts/` | M:N join |
| AlarmEvent | `alarm_events` | `alerts/` | |
| NotificationLog | `notification_logs` | `alerts/` | |
| MaintenanceWorkOrder | `maintenance_work_orders` | `alerts/` | |
| KnowledgeBase | `knowledge_base` | `chatbot/` (Phase 7) | |
| KnowledgeEmbedding | `knowledge_embeddings` | `chatbot/` (Phase 7) | |
| Conversation | `conversations` | `chatbot/` (Phase 7) | |
| Message | `messages` | `chatbot/` (Phase 7) | |
| — (RBAC) | `roles`, `permissions`, `role_permissions`, `user_roles` | `auth/` (Phase 5) | Added when RBAC is needed |
| — (System) | `api_keys` | `common/` | Service-to-service auth |

### Frontend Feature Module → ERD Domain Mapping

| Frontend Feature Module | ERD Domains Covered | Key Pages |
|---|---|---|
| `features/auth/` | User, Tenant (login/register) | LoginPage, RegisterPage |
| `features/dashboard/` | TelemetryRaw, Prediction, AssetHealth (read-only aggregations) | DashboardPage |
| `features/site-setup/` | Tenant, Site, Gateway, Asset, Sensor, AssetHealth | SitesPage, GatewaysPage, AssetsPage, SensorsPage, AssetHealthPage, AssetDetailPage, TenantAdminPage |
| `features/predictions/` | Prediction, Feedback, TelemetryRaw | PredictionsPage, FeedbackPage, FaultTypesPage, RealtimeDataPage |
| `features/ml-management/` | MLModel, MLModelVersion, MLModelDeployment, AssetModelVersion | ModelsPage, ModelDetailPage, DeploymentsPage, RetrainPage |
| `features/alerts/` | AlarmRule, AlarmEvent, NotificationLog, NotificationType, MaintenanceWorkOrder | AlarmRulesPage, AlarmEventsPage, NotificationLogPage, WorkOrdersPage |
| `features/settings/` | User (preferences), UserSettings, FaultActions | SettingsPage |
| `features/chatbot/` | KnowledgeBase, Conversation, Message (Phase 7) | ChatPage |
