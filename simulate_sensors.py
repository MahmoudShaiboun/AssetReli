#!/usr/bin/env python3
"""
MQTT Sensor Data Simulator
Simulates industrial sensors sending data to MQTT broker
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC = "sensors/industrial/data"

# Sensor configurations
SENSORS = [
    {"id": "sensor_001", "name": "Motor A"},
    {"id": "sensor_002", "name": "Pump B"},
    {"id": "sensor_003", "name": "Compressor C"}
]

def generate_sensor_data(sensor_id):
    """Generate realistic sensor data with occasional anomalies"""
    
    # Base normal values
    base_temp = 65.0
    base_vibration = 2.5
    base_pressure = 100.0
    base_humidity = 45.0
    
    # Add random variation
    temp_var = random.uniform(-5, 5)
    vib_var = random.uniform(-0.5, 0.5)
    press_var = random.uniform(-10, 10)
    humid_var = random.uniform(-5, 5)
    
    # Occasionally introduce anomalies (10% chance)
    if random.random() < 0.1:
        print(f"⚠️  Generating anomaly for {sensor_id}")
        temp_var += random.uniform(15, 25)  # High temperature
        vib_var += random.uniform(3, 5)     # High vibration
    
    return {
        "sensor_id": sensor_id,
        "temperature": round(base_temp + temp_var, 2),
        "vibration": round(base_vibration + vib_var, 2),
        "pressure": round(base_pressure + press_var, 2),
        "humidity": round(base_humidity + humid_var, 2),
        "timestamp": datetime.utcnow().isoformat()
    }

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"❌ Connection failed with code {rc}")

def main():
    print("🏭 Industrial Sensor Data Simulator")
    print("=" * 50)
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topic: {TOPIC}")
    print(f"Sensors: {len(SENSORS)}")
    print("=" * 50)
    
    # Create MQTT client
    client = mqtt.Client()
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        print("\n📡 Starting to publish sensor data...")
        print("Press Ctrl+C to stop\n")
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n--- Iteration {iteration} ---")
            
            for sensor in SENSORS:
                # Generate data
                data = generate_sensor_data(sensor["id"])
                
                # Publish to MQTT
                payload = json.dumps(data)
                result = client.publish(TOPIC, payload)
                
                if result.rc == 0:
                    print(f"✓ {sensor['name']} ({sensor['id']}): "
                          f"Temp={data['temperature']}°C, "
                          f"Vib={data['vibration']}Hz, "
                          f"Press={data['pressure']}Pa, "
                          f"Humid={data['humidity']}%")
                else:
                    print(f"✗ Failed to publish data for {sensor['id']}")
            
            # Wait before next reading (5 seconds)
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping simulator...")
        client.loop_stop()
        client.disconnect()
        print("👋 Simulator stopped")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
