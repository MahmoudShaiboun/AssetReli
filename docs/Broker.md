# enterprise-grade multi-tenant MQTT ingestion system using:

Eclipse Mosquitto
Python ingestion service
Auth layer
MongoDB (Strict tenant isolation - Topic registration per tenant)

## 🏗 1️⃣ High-Level Architecture

```bash
IoT Devices (OnTrack Gateway)
        ↓
MQTT over TLS
        ↓
Mosquitto Broker
   - Auth (username/password or cert)
   - ACL per tenant
        ↓
Python Ingestion Service (subscriber)
        ↓
Validation Layer
        ↓
MongoDB
   - tenants
   - assets
   - sensors
   - telemetry
```

## 🧱 2️⃣ Topic Design (Multi-Tenant Safe)

✅ Final Topic Pattern
tenants/{tenantId}/assets/{assetId}/sensors/{sensorId}/telemetry

```bash
    # Example
    tenants/acme/assets/truck-102/sensors/temp-1/telemetry
```

This enables:
Broker-level routing
ACL restriction
Easy parsing
Scalable subscriptions

## 🔐 3️⃣ Authentication Layer (Critical)

You must never trust JSON alone.

We will use:

Username = Tenant ID

Device connects with:
Username: tenant_acme
Password: secure_generated_password

Why?
Because Mosquitto can:
Authenticate user
Apply ACL rules
Restrict publishing

## 🔒 4️⃣ Mosquitto Configuration
Install Mosquitto

On Ubuntu:
```bash
sudo apt install mosquitto mosquitto-clients

mosquitto.conf
listener 8883
allow_anonymous false

password_file /etc/mosquitto/passwd
acl_file /etc/mosquitto/acl

require_certificate false
```

## 🔑 5️⃣ Create Tenant Users

When a new tenant registers:

sudo mosquitto_passwd /etc/mosquitto/passwd tenant_acme

This creates tenant-specific credentials.

## 📜 6️⃣ ACL File (Critical for Isolation)

/etc/mosquitto/acl

user tenant_acme
topic write tenants/acme/#

user tenant_beta
topic write tenants/beta/#

user ingestion_service
topic read tenants/#


Now:

tenant_acme can ONLY publish to tenants/acme/#

Cannot publish to another tenant

ingestion service reads all

## 🗂 7️⃣ MongoDB Data Model
tenants collection
{
  "_id": "acme",
  "name": "Acme Corp",
  "createdAt": ISODate()
}

assets collection
{
  "_id": "truck-102",
  "tenantId": "acme",
  "type": "vehicle"
}

sensors collection
{
  "_id": "temp-1",
  "tenantId": "acme",
  "assetId": "truck-102",
  "type": "temperature",
  "unit": "C"
}

telemetry collection
{
  "tenantId": "acme",
  "assetId": "truck-102",
  "sensorId": "temp-1",
  "timestamp": ISODate(),
  "value": 27.4
}

🚀 8️⃣ Python Ingestion Service

We’ll use:

paho-mqtt

pymongo

Install
pip install paho-mqtt pymongo

ingestion_service.py
import json
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
mongo = MongoClient("mongodb://localhost:27017")
db = mongo.iot_platform

# MQTT settings
BROKER = "localhost"
PORT = 8883
USERNAME = "ingestion_service"
PASSWORD = "strong_password"

def validate_entities(tenant_id, asset_id, sensor_id):
    tenant = db.tenants.find_one({"_id": tenant_id})
    if not tenant:
        return False

    asset = db.assets.find_one({
        "_id": asset_id,
        "tenantId": tenant_id
    })
    if not asset:
        return False

    sensor = db.sensors.find_one({
        "_id": sensor_id,
        "tenantId": tenant_id,
        "assetId": asset_id
    })
    if not sensor:
        return False

    return True

def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")

        tenant_id = topic_parts[1]
        asset_id = topic_parts[3]
        sensor_id = topic_parts[5]

        payload = json.loads(msg.payload)

        if not validate_entities(tenant_id, asset_id, sensor_id):
            print("Invalid entity mapping")
            return

        telemetry = {
            "tenantId": tenant_id,
            "assetId": asset_id,
            "sensorId": sensor_id,
            "timestamp": datetime.utcnow(),
            "value": payload["value"]
        }

        db.telemetry.insert_one(telemetry)
        print("Stored telemetry")

    except Exception as e:
        print("Error:", e)

client = mqtt.Client()
client.username_pw_set(USERNAME, PASSWORD)

client.on_message = on_message
client.connect(BROKER, PORT)

client.subscribe("tenants/#")

client.loop_forever()

🧩 9️⃣ Tenant Registration Flow (Very Important)

When new tenant signs up:

Step 1 — Create MongoDB tenant record
Step 2 — Create Mosquitto user
mosquitto_passwd /etc/mosquitto/passwd tenant_new

Step 3 — Add ACL entry

Append to ACL file:

user tenant_new
topic write tenants/new/#

Step 4 — Reload Mosquitto
sudo systemctl restart mosquitto

🔄 10️⃣ Automating Tenant Topic Registration

You should NOT manually edit ACL in production.

Better approach:

Use dynamic security plugin (recommended for enterprise)

Mosquitto supports dynamic security plugin which allows:

Add user via API

Add ACL via API

No restart required

This is the enterprise way.

📊 11️⃣ Scalability Improvements

For large scale:

Use separate ingestion workers

Use Kafka between broker and DB (optional)

Use MongoDB time-series collections

Add TTL index for telemetry if needed

🛡 12️⃣ Security Best Practices

✔ Always use TLS
✔ Never allow anonymous
✔ Validate topic vs DB
✔ Validate sensor ownership
✔ Log rejected messages
✔ Use rate limiting

🏁 Final Enterprise Pattern
Device → TLS → Mosquitto
       → Auth (username=tenant)
       → ACL (tenant isolation)
       → Python Ingestion
       → Validation (MongoDB)
       → Store telemetry