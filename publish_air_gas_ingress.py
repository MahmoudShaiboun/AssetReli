"""
Publish air_gas_ingress anomaly data through MQTT pipeline
This script sends structured sensor data that will flow through:
MQTT → mqtt-ingestion → MongoDB → backend-api → frontend
"""
import json
import time
import paho.mqtt.client as mqtt

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/motor_pump"

# Load the air_gas_ingress data
with open(r'c:\Users\mahmo\Desktop\assetReli\anomalies\air_gas_ingress_input.json', 'r') as f:
    data = json.load(f)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT Broker!")
    else:
        print(f"❌ Failed to connect, return code {rc}")

def on_publish(client, userdata, mid):
    print(f"📤 Message {mid} published successfully")

# Create MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_publish = on_publish

print(f"🔌 Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# Wait for connection
time.sleep(2)

print(f"\n📊 Publishing {len(data['window_data'])} sensor readings to topic: {MQTT_TOPIC}")
print(f"🎯 Expected fault: {data['expected_fault']}\n")

# Publish each reading from the window
for i, reading in enumerate(data['window_data'], 1):
    # Format the message as mqtt-ingestion expects
    message = {
        "timestamp": reading["timestamp"],
        "sensor_id": "PUMP_001",  # Default sensor ID
        "motor_data": {
            "DE_vib_band_1": reading["motor_DE_vib_band_1"],
            "DE_vib_band_2": reading["motor_DE_vib_band_2"],
            "DE_vib_band_3": reading["motor_DE_vib_band_3"],
            "DE_vib_band_4": reading["motor_DE_vib_band_4"],
            "DE_ultra_db": reading["motor_DE_ultra_db"],
            "DE_temp_c": reading["motor_DE_temp_c"],
            "NDE_vib_band_1": reading["motor_NDE_vib_band_1"],
            "NDE_vib_band_2": reading["motor_NDE_vib_band_2"],
            "NDE_vib_band_3": reading["motor_NDE_vib_band_3"],
            "NDE_vib_band_4": reading["motor_NDE_vib_band_4"],
            "NDE_ultra_db": reading["motor_NDE_ultra_db"],
            "NDE_temp_c": reading["motor_NDE_temp_c"]
        },
        "pump_data": {
            "DE_vib_band_1": reading["pump_DE_vib_band_1"],
            "DE_vib_band_2": reading["pump_DE_vib_band_2"],
            "DE_vib_band_3": reading["pump_DE_vib_band_3"],
            "DE_vib_band_4": reading["pump_DE_vib_band_4"],
            "DE_ultra_db": reading["pump_DE_ultra_db"],
            "DE_temp_c": reading["pump_DE_temp_c"],
            "NDE_vib_band_1": reading["pump_NDE_vib_band_1"],
            "NDE_vib_band_2": reading["pump_NDE_vib_band_2"],
            "NDE_vib_band_3": reading["pump_NDE_vib_band_3"],
            "NDE_vib_band_4": reading["pump_NDE_vib_band_4"],
            "NDE_ultra_db": reading["pump_NDE_ultra_db"],
            "NDE_temp_c": reading["pump_NDE_temp_c"]
        }
    }
    
    # Publish to MQTT
    result = client.publish(MQTT_TOPIC, json.dumps(message))
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"✅ Reading {i}/10: {reading['timestamp']} - Published")
    else:
        print(f"❌ Reading {i}/10: Failed to publish")
    
    # Small delay between messages
    time.sleep(0.5)

print("\n⏳ Waiting for all messages to be sent...")
time.sleep(2)

client.loop_stop()
client.disconnect()

print("\n" + "="*60)
print("✅ All sensor readings published successfully!")
print("="*60)
print("\n📋 Next steps to verify data flow:")
print("1. Check MongoDB:")
print("   docker exec aastreli-mongodb mongosh aastreli --quiet --eval \"db.sensor_data.find().sort({_id:-1}).limit(1).pretty()\"")
print("\n2. Check ML predictions:")
print("   docker logs aastreli-ml-service --tail 20 | Select-String -Pattern 'PREDICTION'")
print("\n3. Check mqtt-ingestion logs:")
print("   docker logs aastreli-mqtt-ingestion --tail 30")
print("\n4. Check backend API:")
print("   curl http://localhost:8000/sensors/latest")
print("\n5. Check frontend:")
print("   Open http://localhost:3000/dashboard")
