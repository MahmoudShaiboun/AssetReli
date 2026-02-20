# MQTT Ingestion Flow

End-to-end trace of how sensor data flows from MQTT publish to storage, prediction, alerts, and WebSocket streaming.

---

## 1. MQTT Subscription & Dispatch

**File:** `mqtt-ingestion/app/ingestion/mqtt_client.py`

### Subscribed Topics (config.py)

```
sensors/#              ← legacy: sensors/{sensor_id}
equipment/#            ← legacy: equipment/{sensor_id}
+/+/sensors/#          ← multi-tenant: {tenant_code}/{site_code}/sensors/{sensor_code}
```

### Message Receipt

```
MQTTClient._on_message(topic, raw_bytes)
  │
  ├─ payload = json.loads(raw_bytes)
  ├─ store in latest_data[topic] (used by /latest endpoint + WebSocket)
  └─ asyncio.run_coroutine_threadsafe(handler.handle(topic, payload))
```

The MQTT client runs paho in a background thread; `_on_message` dispatches to the async `MessageHandler.handle()` on the FastAPI event loop.

---

## 2. Topic Parsing

**File:** `mqtt-ingestion/app/ingestion/topic_parser.py`

```
parse_topic(topic) → ParsedTopic | None

  "sensors/pump_01"                           → ParsedTopic(sensor_code="pump_01")
  "equipment/motor_01"                        → ParsedTopic(sensor_code="motor_01")
  "default/main_site/sensors/SENSOR_001"      → ParsedTopic(sensor_code="SENSOR_001",
                                                             tenant_code="default",
                                                             site_code="main_site")
  "unknown/format"                            → None (logged as warning)
```

### Supported Formats

| Pattern | Parts | Source |
|---------|-------|--------|
| `sensors/{sensor_code}` | 2 | simulate_sensors.py |
| `equipment/{sensor_code}` | 2 | legacy |
| `{tenant}/{site}/sensors/{sensor}` | 4 | simulate_sensors_mt.py |

---

## 3. Context Resolution

**File:** `mqtt-ingestion/app/ingestion/message_handler.py` → `_resolve_context()`

```
_resolve_context(topic, payload)
  │
  ├─ parsed = parse_topic(topic)
  │   └─ if None → fallback: ctx.sensor_code = payload["sensor_id"]
  │
  ├─ ctx = MessageContext(sensor_code, tenant_code?, site_code?)
  │
  ├─ SensorRegistryCache.lookup(sensor_code)
  │   └─ if found → enrich ctx with:
  │       tenant_id, tenant_code, site_id, site_code, asset_id, sensor_id (UUIDs)
  │
  └─ ModelBindingCache.lookup(asset_id)
      └─ if found → ctx.model_version_id = binding.model_version_id
```

### MessageContext (context.py)

```python
@dataclass
class MessageContext:
    tenant_id      # UUID from PG, None if unresolved
    tenant_code    # from topic or registry
    site_id        # UUID from PG
    site_code      # from topic or registry
    asset_id       # UUID from PG
    sensor_id      # UUID from PG
    sensor_code    # from topic
    model_version_id  # UUID from model binding

    is_resolved → True if tenant_id AND sensor_id are set
    window_key  → "{tenant_id}:{asset_id}:{sensor_id}" or sensor_code
```

### SensorRegistryCache (sensor_registry.py)

- Loaded on startup from PostgreSQL (`sensors` + `tenants` + `assets` + `sites` JOIN)
- Auto-refreshed every 60 seconds in background
- Key: `sensor_code` → Value: `SensorBinding(sensor_id, tenant_id, tenant_code, site_id, site_code, asset_id, gateway_id)`
- Check cache size: `GET /health` → `sensor_cache_size`

### ModelBindingCache (prediction/model_binding.py)

- Loaded from `asset_model_versions` + `ml_model_versions` JOIN
- Key: `asset_id` → Value: `ModelBinding(model_id, model_version_id, version_label, artifact_path)`
- Check cache size: `GET /health` → `model_cache_size`

---

## 4. Raw Telemetry Storage

**File:** `mqtt-ingestion/app/storage/telemetry_writer.py`

```
TelemetryWriter.write(topic, payload, timestamp, ctx)
  └─ MongoDB collection: sensor_data
     {
       "topic": "default/site1/sensors/pump_01",
       "data": { <entire flat payload> },
       "timestamp": <server UTC>,
       "tenant_id": "...",    ← only if ctx.is_resolved
       "site_id": "...",
       "asset_id": "...",
       "sensor_id": "..."
     }
```

**Always stored**, regardless of prediction outcome.

---

## 5. Sensor Type Detection & Feature Extraction

**File:** `mqtt-ingestion/app/ingestion/message_handler.py` → `handle()`

```
if "motor_DE_vib_band_1" in payload:
    → Complex sensor path (Path A)
elif "sensor_id" in payload AND any of (temperature, vibration, pressure, humidity):
    → Simple sensor path (Path B)
else:
    → No prediction (raw telemetry still stored)
```

### Path A — Complex Sensor (24-feature motor/pump data)

**Sources:** Industrial motor/pump sensors with fields like `motor_DE_vib_band_1..4`, `motor_DE_temp_c`, `motor_DE_ultra_db`, etc.

```
_handle_complex_sensor(payload, timestamp, ctx)
  │
  ├─ extract_24_features_from_data(payload)
  │   └─ 4 locations × 6 features = 24 floats
  │      Motor DE:  vib_band_1-4, ultra_db, temp_c
  │      Motor NDE: vib_band_1-4, ultra_db, temp_c
  │      Pump DE:   vib_band_1-4, ultra_db, temp_c
  │      Pump NDE:  vib_band_1-4, ultra_db, temp_c
  │
  ├─ SlidingWindowManager.add_reading(window_key, 24_features)
  │   ├─ if window < 14 readings → return None (still building)
  │   └─ if window == 14 → return full window (14 × 24 array)
  │
  ├─ extract_statistical_features_from_window(window)
  │   └─ For each of 24 sensors, compute 14 statistics:
  │      mean, std, min, max, median, q25, q75, range,
  │      var, rms, mad, sum, sum_sq, max/min_ratio
  │      = 24 × 14 = 336 features
  │
  └─ MLClient.predict(336_features, tenant_id, asset_id, model_version_id)
```

### Path B — Simple Sensor (4-feature temperature/vibration data)

**Sources:** `simulate_sensors.py`, `simulate_sensors_mt.py`

```
_handle_simple_sensor(payload, ctx)
  │
  ├─ features = [temperature, vibration, pressure, humidity]
  ├─ pad to 336 with zeros
  └─ MLClient.predict(336_features, tenant_id, asset_id, model_version_id)
```

**No sliding window** — predicts immediately per reading.

---

## 6. ML Prediction

**File:** `mqtt-ingestion/app/prediction/ml_client.py`

```
MLClient.predict(features, tenant_id?, asset_id?, model_version_id?)
  │
  └─ POST http://{ML_SERVICE_URL}/predict
     Body: { "features": [336 floats], "top_k": 3, "tenant_id": "...", ... }
     Headers: { "X-API-Key": "..." }

     Response 200: { "prediction": "normal", "confidence": 0.95, "top_k": [...] }
     Response !200 or error: returns None (prediction skipped, data still stored)
```

---

## 7. Structured Reading Storage

**File:** `mqtt-ingestion/app/storage/prediction_writer.py`

### Simple sensors → `write_simple_reading()`

```
MongoDB collection: sensor_readings
{
  "sensor_id": "pump_01",
  "timestamp": "2026-02-20T12:34:56",
  "temperature": 72.5,
  "vibration": 2.3,
  "pressure": 105.2,
  "humidity": 48.1,
  "topic": "default/site1/sensors/pump_01",
  "has_feedback": false,
  "prediction": "normal",
  "confidence": 0.95,
  "tenant_id": "...",      ← if ctx.is_resolved
  "site_id": "...",
  "asset_id": "...",
  "sensor_uuid": "..."
}
```

### Complex sensors → `write_complex_reading()`

```
MongoDB collection: sensor_readings
{
  "sensor_id": "industrial_sensor",
  "timestamp": "...",
  "state": "...",
  "regime": "...",
  "motor_data": { "DE_temp": ..., "DE_vib_band_1": ..., ... },
  "pump_data": { "DE_temp": ..., ... },
  "topic": "...",
  "has_feedback": false,
  "prediction": "bearing_fault",
  "confidence": 0.87,
  "tenant_id": "...",
  ...
}
```

---

## 8. Alert Evaluation

**File:** `mqtt-ingestion/app/alerts/publisher.py`

**Trigger condition** (complex sensors only):
```
prediction != "normal" AND confidence > ALERT_CONFIDENCE_THRESHOLD (0.6) AND ctx.is_resolved
```

```
AlertPublisher.publish(prediction, confidence, sensor_reading, ctx)
  │
  └─ POST http://{BACKEND_API_URL}/alerts/evaluate
     Body: {
       "tenant_id": "...",
       "prediction_label": "bearing_fault",
       "probability": 0.87,
       "timestamp": "...",
       "asset_id": "...",
       "sensor_id": "...",
       "model_version_id": "...",
       "prediction_id": "..."
     }
     Retries: 3 attempts, exponential backoff (1-4s)
```

---

## 9. WebSocket Streaming

**File:** `mqtt-ingestion/app/streaming/websocket.py`

```
Client connects: ws://localhost:8002/stream?token=<jwt>&tenant_id=<optional>
  │
  ├─ Extract tenant_id from JWT (or query param for super_admin)
  └─ Every 1 second:
      ├─ Read mqtt_client.latest_data (dict of topic → last payload)
      ├─ Filter topics by tenant (via SensorRegistryCache lookup)
      └─ Send filtered JSON to client
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     MQTT Broker (Mosquitto)                      │
│  Subscriptions: sensors/#, equipment/#, +/+/sensors/#           │
└──────────┬──────────────────────────────────────────────────────┘
           │ _on_message(topic, raw_json)
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  MQTTClient                                                      │
│  ├─ json.loads(payload)                                          │
│  ├─ latest_data[topic] = payload  (for WebSocket + /latest)      │
│  └─ dispatch → MessageHandler.handle(topic, payload)             │
└──────────┬──────────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────────┐
│  MessageHandler.handle()                                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Step 0: Resolve Context                                  │     │
│  │  parse_topic(topic) → sensor_code, tenant_code?, site?   │     │
│  │  SensorRegistryCache.lookup(sensor_code)                 │     │
│  │    → tenant_id, site_id, asset_id, sensor_id (UUIDs)     │     │
│  │  ModelBindingCache.lookup(asset_id)                      │     │
│  │    → model_version_id                                    │     │
│  └─────────────────────────────────────────────────────────┘     │
│                          │                                       │
│  ┌───────────────────────▼─────────────────────────────────┐     │
│  │ Step 1: Store raw telemetry → MongoDB sensor_data        │     │
│  └─────────────────────────────────────────────────────────┘     │
│                          │                                       │
│  ┌───────────────────────▼─────────────────────────────────┐     │
│  │ Step 2: Detect sensor type → extract features → predict  │     │
│  │                                                          │     │
│  │  Complex (motor_DE_vib_band_1 in data):                  │     │
│  │    24 features → sliding window (14 steps)               │     │
│  │    → 336 statistical features → ML predict               │     │
│  │                                                          │     │
│  │  Simple (sensor_id + temp/vib/press/humid):              │     │
│  │    4 features → pad to 336 → ML predict                  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                          │                                       │
│  ┌───────────────────────▼─────────────────────────────────┐     │
│  │ Step 3: Store reading + prediction → MongoDB readings    │     │
│  └─────────────────────────────────────────────────────────┘     │
│                          │                                       │
│  ┌───────────────────────▼─────────────────────────────────┐     │
│  │ Step 4: Alert (complex only, anomaly, confidence > 0.6)  │     │
│  │  POST /alerts/evaluate → backend-api                     │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

               ┌───────────────────────────┐
               │ WebSocket /stream          │
               │  Every 1s: latest_data     │
               │  filtered by tenant_id     │
               └───────────────────────────┘
```

---

## Simulator Compatibility

| Simulator | Topic Format | Subscription Match | Parser Result | Payload |
|-----------|-------------|-------------------|---------------|---------|
| `simulate_sensors.py` | `sensors/{sensor_id}` | `sensors/#` | 2-part: sensor_code only | flat: sensor_id, temperature, vibration, pressure, humidity |
| `simulate_sensors_mt.py` | `{tenant}/{site}/sensors/{sensor}` | `+/+/sensors/#` | 4-part: sensor_code + tenant_code + site_code | flat: sensor_id, temperature, vibration, pressure, humidity |

Both use the **simple sensor path** (Path B) and produce identical MongoDB documents in `sensor_data` and `sensor_readings`.

---

## Debugging Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Service status, subscribed topics |
| `GET /health` | MQTT connected, message count, cache sizes |
| `GET /latest` | Last payload per topic (raw dict) |
| `WS /stream?token=jwt` | Real-time filtered data |

---

## Key Files

| File | Responsibility |
|------|---------------|
| `app/main.py` | Lifespan: PG pool, caches, MQTT client init |
| `app/config.py` | Settings (topics, URLs, thresholds) |
| `app/ingestion/mqtt_client.py` | MQTT connect/subscribe/dispatch |
| `app/ingestion/topic_parser.py` | Topic → sensor_code + tenant/site |
| `app/ingestion/sensor_registry.py` | PG cache: sensor_code → UUIDs |
| `app/ingestion/context.py` | MessageContext dataclass |
| `app/ingestion/message_handler.py` | Main pipeline: resolve → store → predict → alert |
| `app/features/extractors.py` | 24-feature extraction, 336-stat computation |
| `app/features/sliding_window.py` | Per-sensor 14-step FIFO window |
| `app/prediction/ml_client.py` | HTTP POST to ML service |
| `app/prediction/model_binding.py` | PG cache: asset_id → model version |
| `app/storage/telemetry_writer.py` | Raw payload → MongoDB sensor_data |
| `app/storage/prediction_writer.py` | Reading + prediction → MongoDB sensor_readings |
| `app/alerts/publisher.py` | POST anomaly alerts to backend-api |
| `app/streaming/websocket.py` | WebSocket /stream with tenant filtering |
