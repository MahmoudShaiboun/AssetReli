"""
Debug: Print the exact window being processed
"""
import json
import numpy as np

ANOMALY_FILE = r"c:\Users\mahmo\Desktop\assetReli\anomalies\electrical_fluting_input.json"

with open(ANOMALY_FILE, 'r') as f:
    data = json.load(f)

window_data = data['window_data']
while len(window_data) < 14:
    window_data.append(window_data[-1].copy())

print("First reading from JSON:")
print(json.dumps(window_data[0], indent=2))

print("\n" + "="*80)
print("MQTT Client Extraction (from _extract_24_features_from_data):")
print("="*80)

# Simulate MQTT client's extraction
reading = window_data[0]
mqtt_features = []

# Motor DE: vib_band_1-4, ultra_db, temp_c
for i in range(1, 5):
    mqtt_features.append(reading.get(f"motor_DE_vib_band_{i}", 0.0))
mqtt_features.append(reading.get("motor_DE_ultra_db", 0.0))
mqtt_features.append(reading.get("motor_DE_temp_c", 0.0))

# Motor NDE: vib_band_1-4, ultra_db, temp_c
for i in range(1, 5):
    mqtt_features.append(reading.get(f"motor_NDE_vib_band_{i}", 0.0))
mqtt_features.append(reading.get("motor_NDE_ultra_db", 0.0))
mqtt_features.append(reading.get("motor_NDE_temp_c", 0.0))

# Pump DE: vib_band_1-4, ultra_db, temp_c
for i in range(1, 5):
    mqtt_features.append(reading.get(f"pump_DE_vib_band_{i}", 0.0))
mqtt_features.append(reading.get("pump_DE_ultra_db", 0.0))
mqtt_features.append(reading.get("pump_DE_temp_c", 0.0))

# Pump NDE: vib_band_1-4, ultra_db, temp_c
for i in range(1, 5):
    mqtt_features.append(reading.get(f"pump_NDE_vib_band_{i}", 0.0))
mqtt_features.append(reading.get("pump_NDE_ultra_db", 0.0))
mqtt_features.append(reading.get("pump_NDE_temp_c", 0.0))

for i, val in enumerate(mqtt_features):
    print(f"{i:2d}. {val:.6f}")

print(f"\nTotal: {len(mqtt_features)} features")

# Now check what order test script expects
print("\n" + "="*80)
print("Test Script Expected Order (SENSOR_COLUMNS):")
print("="*80)

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

test_features = [reading.get(col, 0.0) for col in SENSOR_COLUMNS]

for i, val in enumerate(test_features):
    print(f"{i:2d}. {val:.6f}")

print(f"\nTotal: {len(test_features)} features")

print("\n" + "="*80)
print("COMPARISON:")
print("="*80)
print(f"Match: {mqtt_features == test_features}")

for i in range(24):
    if mqtt_features[i] != test_features[i]:
        print(f"MISMATCH at index {i}: MQTT={mqtt_features[i]:.6f}, Test={test_features[i]:.6f}")
