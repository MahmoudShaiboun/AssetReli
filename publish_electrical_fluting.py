"""
Publish the electrical_fluting anomaly from user's file
"""
import json
import paho.mqtt.client as mqtt
import time

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"
ANOMALY_FILE = r"c:\Users\mahmo\Desktop\assetReli\anomalies\electrical_fluting_input.json"

with open(ANOMALY_FILE, 'r') as f:
    data = json.load(f)

window_data = data['window_data']

# Pad to 14 timesteps
while len(window_data) < 14:
    window_data.append(window_data[-1].copy())

print("="*80)
print("  PUBLISHING ELECTRICAL FLUTING TO MQTT")
print("="*80)
print(f"\nData: {len(window_data)} timesteps")
print(f"Expected: electrical_fluting\n")

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()
time.sleep(1)

# Publish with sensor_id that frontend will display
sensor_id = f"industrial_sensor_{int(time.time())}"  # Unique sensor ID per test
print(f"Using sensor_id: {sensor_id}\n")

for i, reading in enumerate(window_data, 1):
    reading["sensor_id"] = sensor_id
    client.publish(MQTT_TOPIC, json.dumps(reading))
    if i % 5 == 0:
        print(f"Published {i}/{len(window_data)}...")
    time.sleep(0.15)

print(f"\n✅ Published all {len(window_data)} readings")
print(f"\n⏳ Waiting for ML prediction...")
time.sleep(5)

client.loop_stop()
client.disconnect()

print("\n" + "="*80)
print("  RESULT")
print("="*80)
print("\n✅ Data published to MQTT")
print("📊 Check logs: docker logs aastreli-mqtt-ingestion --tail 20")
print("🌐 Refresh frontend: Press Ctrl+Shift+R in browser")
print("\n" + "="*80)
