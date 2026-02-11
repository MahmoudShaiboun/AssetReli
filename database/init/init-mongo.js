// Initialize Aastreli MongoDB Database

db = db.getSiblingDB('aastreli');

// Create collections
db.createCollection('sensors');
db.createCollection('sensor_data');
db.createCollection('predictions');
db.createCollection('feedback');
db.createCollection('models');
db.createCollection('faults');

// Create indexes
db.sensor_data.createIndex({ "timestamp": -1 });
db.sensor_data.createIndex({ "data.sensor_id": 1, "timestamp": -1 });

db.predictions.createIndex({ "timestamp": -1 });
db.predictions.createIndex({ "prediction": 1 });

db.feedback.createIndex({ "created_at": -1 });
db.feedback.createIndex({ "feedback_type": 1 });

// Insert initial fault types
db.faults.insertMany([
  { name: "normal", category: "operational", description: "Normal operation" },
  { name: "bearing_overgrease_churning", category: "mechanical", description: "Bearing overgreased causing churning" },
  { name: "bearing_fit_loose_housing", category: "mechanical", description: "Loose bearing fit in housing" },
  { name: "phase_unbalance", category: "electrical", description: "Electrical phase unbalance" },
  { name: "sensor_drift_bias", category: "instrumentation", description: "Sensor drift or bias" }
]);

// Insert sample sensor configuration
db.sensors.insertMany([
  {
    sensor_id: "pump_01",
    name: "Main Pump 1",
    type: "pump",
    location: "Building A",
    status: "active",
    sampling_rate: 1000,
    features: ["vibration", "temperature", "pressure"]
  },
  {
    sensor_id: "motor_01",
    name: "Motor 1",
    type: "motor",
    location: "Building A",
    status: "active",
    sampling_rate: 1000,
    features: ["vibration", "temperature", "current"]
  }
]);

print("✅ Database initialized successfully!");
