// Initialize Aastreli MongoDB Database
// Phase 2: MongoDB retains only telemetry_raw and predictions.
// All business entities (users, sensors, feedback, etc.) are in PostgreSQL.

db = db.getSiblingDB('aastreli');

// ============================================================
// Legacy collections (read-only — kept until mqtt-ingestion Phase 3 migration)
// These are NOT created for fresh installs but may exist in upgraded deployments.
// ============================================================
db.createCollection('sensor_data');
db.createCollection('sensor_readings');

// Legacy indexes (for mqtt-ingestion backward compatibility)
db.sensor_data.createIndex({ "timestamp": -1 });
db.sensor_data.createIndex({ "data.sensor_id": 1, "timestamp": -1 });
db.sensor_readings.createIndex({ "timestamp": -1 });
db.sensor_readings.createIndex({ "sensor_id": 1, "timestamp": -1 });

// ============================================================
// telemetry_raw (ref: TelemetryRaw)
// Raw MQTT payloads
// Written by: mqtt-ingestion | Read by: backend-api
// ============================================================
db.createCollection("telemetry_raw", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "asset_id", "timestamp_utc", "payload_original"],
      properties: {
        tenant_id:        { bsonType: "string", description: "REQUIRED - PG tenants.id" },
        site_id:          { bsonType: "string" },
        asset_id:         { bsonType: "string", description: "REQUIRED - PG assets.id" },
        sensor_id:        { bsonType: ["string", "null"] },
        timestamp_utc:    { bsonType: "date" },
        payload_original: { bsonType: "object" },
        payload_normalized: { bsonType: "array" },
        validation_data:  { bsonType: "object" },
        mqtt_topic:       { bsonType: "string" }
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

// Primary: telemetry for tenant's asset in time range
db.telemetry_raw.createIndex({ "tenant_id": 1, "asset_id": 1, "timestamp_utc": -1 });
// Secondary: by specific sensor
db.telemetry_raw.createIndex({ "tenant_id": 1, "sensor_id": 1, "timestamp_utc": -1 });

// ============================================================
// predictions (ref: Prediction)
// One document per ML inference
// Written by: mqtt-ingestion | Read by: backend-api
// ============================================================

// Drop legacy predictions collection so we can recreate with validation
db.predictions.drop();

db.createCollection("predictions", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["tenant_id", "asset_id", "timestamp_utc", "prediction_label", "model_version_id"],
      properties: {
        tenant_id:          { bsonType: "string", description: "REQUIRED" },
        site_id:            { bsonType: "string" },
        asset_id:           { bsonType: "string", description: "REQUIRED" },
        sensor_id:          { bsonType: ["string", "null"] },
        telemetry_raw_id:   { bsonType: "objectId" },
        timestamp_utc:      { bsonType: "date" },
        payload_normalized: { bsonType: "array" },
        validation_data:    { bsonType: "object" },
        prediction_label:   { bsonType: "string" },
        probability:        { bsonType: "double" },
        top_predictions:    { bsonType: "array" },
        model_version_id:   { bsonType: "string", description: "REQUIRED - PG ml_model_versions.id" },
        model_version_label: { bsonType: "string" },
        explanation_payload: { bsonType: "object" }
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

// Primary: predictions for tenant's asset in time range
db.predictions.createIndex({ "tenant_id": 1, "asset_id": 1, "timestamp_utc": -1 });
// Secondary: filter by fault type
db.predictions.createIndex({ "tenant_id": 1, "prediction_label": 1, "timestamp_utc": -1 });
// Secondary: by model version
db.predictions.createIndex({ "tenant_id": 1, "model_version_id": 1, "timestamp_utc": -1 });

print("MongoDB initialized (telemetry_raw + predictions only)!");
