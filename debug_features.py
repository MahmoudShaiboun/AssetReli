"""
Debug feature extraction - compare test script vs MQTT client
"""
import json
import numpy as np

# Load anomaly data
ANOMALY_FILE = r"c:\Users\mahmo\Desktop\assetReli\anomalies\electrical_fluting_input.json"

with open(ANOMALY_FILE, 'r') as f:
    data = json.load(f)

window_data = data['window_data']

# Pad to 14 timesteps
while len(window_data) < 14:
    window_data.append(window_data[-1].copy())

print("="*80)
print("  FEATURE EXTRACTION COMPARISON")
print("="*80)

# Test script's approach (statistical features)
SENSOR_COLUMNS = [
    'motor_DE_vib_band_1', 'motor_DE_vib_band_2', 'motor_DE_vib_band_3', 'motor_DE_vib_band_4',
    'motor_DE_ultra_db', 'motor_DE_temp_c',
    'motor_NDE_vib_band_1', 'motor_NDE_vib_band_2', 'motor_NDE_vib_band_3', 'motor_NDE_vib_band_4',
    'motor_NDE_ultra_db', 'motor_NDE_temp_c',
    'pump_DE_vib_band_1', 'pump_DE_vib_band_2', 'pump_DE_vib_band_3', 'pump_DE_vib_band_4',
    'pump_DE_ultra_db', 'pump_DE_temp_c',
    'pump_NDE_vib_band_1', 'pump_NDE_vib_band_2', 'pump_NDE_vib_band_3', 'pump_NDE_vib_band_4',
    'pump_NDE_ultra_db', 'pump_NDE_temp_c'
]

features_test = []
for sensor_col in SENSOR_COLUMNS:
    values = np.array([reading.get(sensor_col, 0.0) for reading in window_data])
    
    features_test.extend([
        float(np.mean(values)),
        float(np.std(values)),
        float(np.min(values)),
        float(np.max(values)),
        float(np.median(values)),
        float(np.percentile(values, 25)),
        float(np.percentile(values, 75)),
        float(np.max(values) - np.min(values)),
        float(np.var(values)),
        float(np.sqrt(np.mean(values**2))),
        float(np.mean(np.abs(values - np.mean(values)))),
        float(np.sum(values)),
        float(np.sum(values**2)),
        float(np.max(values) / (np.min(values) + 1e-8))
    ])

print(f"\nTest script features: {len(features_test)}")
print(f"First 10 features: {features_test[:10]}")
print(f"Last 10 features: {features_test[-10:]}")

# MQTT client's approach (should be same)
# Simulate building window buffer like MQTT client does
sensor_windows = []
for reading in window_data:
    # Extract 24 features from current reading (like _extract_24_features_from_data)
    current_features = []
    for i in range(1, 5):
        current_features.append(reading.get(f"motor_DE_vib_band_{i}", 0.0))
    for i in range(1, 5):
        current_features.append(reading.get(f"motor_NDE_vib_band_{i}", 0.0))
    current_features.append(reading.get("motor_DE_ultra_db", 0.0))
    current_features.append(reading.get("motor_NDE_ultra_db", 0.0))
    current_features.append(reading.get("motor_DE_temp_c", 0.0))
    current_features.append(reading.get("motor_NDE_temp_c", 0.0))
    for i in range(1, 5):
        current_features.append(reading.get(f"pump_DE_vib_band_{i}", 0.0))
    for i in range(1, 5):
        current_features.append(reading.get(f"pump_NDE_vib_band_{i}", 0.0))
    current_features.append(reading.get("pump_DE_ultra_db", 0.0))
    current_features.append(reading.get("pump_NDE_ultra_db", 0.0))
    current_features.append(reading.get("pump_DE_temp_c", 0.0))
    current_features.append(reading.get("pump_NDE_temp_c", 0.0))
    
    sensor_windows.append(current_features)

# Now extract statistical features like MQTT client
features_mqtt = []
window_array = np.array(sensor_windows)  # Shape: (14, 24)

for sensor_idx in range(24):
    values = window_array[:, sensor_idx]
    
    features_mqtt.extend([
        float(np.mean(values)),
        float(np.std(values)),
        float(np.min(values)),
        float(np.max(values)),
        float(np.median(values)),
        float(np.percentile(values, 25)),
        float(np.percentile(values, 75)),
        float(np.max(values) - np.min(values)),
        float(np.var(values)),
        float(np.sqrt(np.mean(values**2))),
        float(np.mean(np.abs(values - np.mean(values)))),
        float(np.sum(values)),
        float(np.sum(values**2)),
        float(np.max(values) / (np.min(values) + 1e-8))
    ])

print(f"\nMQTT client features: {len(features_mqtt)}")
print(f"First 10 features: {features_mqtt[:10]}")
print(f"Last 10 features: {features_mqtt[-10:]}")

# Compare
print(f"\n{'='*80}")
print("  COMPARISON")
print("="*80)
print(f"Features match: {features_test == features_mqtt}")

diff = np.abs(np.array(features_test) - np.array(features_mqtt))
print(f"Max difference: {np.max(diff):.6f}")
print(f"Mean difference: {np.mean(diff):.6f}")
print(f"Num differences > 0.01: {np.sum(diff > 0.01)}")

# Find where they differ most
max_diff_idx = np.argmax(diff)
sensor_num = max_diff_idx // 14
feature_num = max_diff_idx % 14
print(f"\nLargest diff at index {max_diff_idx}:")
print(f"  Sensor #{sensor_num}, Feature #{feature_num}")
print(f"  Test value: {features_test[max_diff_idx]:.6f}")
print(f"  MQTT value: {features_mqtt[max_diff_idx]:.6f}")

# Test with ML service
import requests

print("\n" + "="*80)
print("  TESTING WITH ML SERVICE")
print("="*80)

response = requests.post(
    "http://localhost:8001/predict",
    json={"features": features_test, "top_k": 3},
    timeout=10
)

if response.status_code == 200:
    result = response.json()
    print(f"\nTest script features →  Prediction: {result['prediction']}")
    print(f"                        Confidence: {result['confidence']:.4f}")
    print(f"                        Top 3: {[p['label'] for p in result['top_predictions']]}")

response2 = requests.post(
    "http://localhost:8001/predict",
    json={"features": features_mqtt, "top_k": 3},
    timeout=10
)

if response2.status_code == 200:
    result2 = response2.json()
    print(f"\nMQTT client features → Prediction: {result2['prediction']}")
    print(f"                        Confidence: {result2['confidence']:.4f}")
    print(f"                        Top 3: {[p['label'] for p in result2['top_predictions']]}")
