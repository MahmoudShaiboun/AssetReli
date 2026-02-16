#!/usr/bin/env python3
"""
MQTT Sensor Data Simulator
Simulates industrial sensors sending data to MQTT broker.
Registers sensors via the backend API on startup, then publishes
readings to per-sensor MQTT topics (sensors/{sensor_id}).
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import requests
from datetime import datetime

# Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
BACKEND_API_URL = "http://localhost:8008"

# Sensor definitions — IDs match the DB seeds in init-mongo.js
SENSORS = [
    {"sensor_id": "pump_01", "name": "Main Pump 1", "type": "pump", "location": "Building A",
     "features": ["vibration", "temperature", "pressure"]},
    {"sensor_id": "motor_01", "name": "Motor 1", "type": "motor", "location": "Building A",
     "features": ["vibration", "temperature", "current"]},
    {"sensor_id": "compressor_01", "name": "Compressor 1", "type": "compressor", "location": "Building B",
     "features": ["vibration", "temperature", "pressure", "humidity"]},
]


def register_sensors():
    """Register each sensor via POST /sensors (skip if already exists)."""
    for sensor in SENSORS:
        try:
            resp = requests.post(
                f"{BACKEND_API_URL}/sensors",
                json=sensor,
                timeout=5,
            )
            if resp.status_code == 201:
                topic = resp.json().get("mqtt_topic")
                print(f"  Registered {sensor['sensor_id']} -> {topic}")
            elif resp.status_code == 400:
                print(f"  {sensor['sensor_id']} already registered, skipping")
            else:
                print(f"  Unexpected response for {sensor['sensor_id']}: {resp.status_code}")
        except requests.ConnectionError:
            print(f"  Could not reach backend API at {BACKEND_API_URL} — skipping registration")
            break


def generate_sensor_data(sensor_id):
    """Generate realistic sensor data with occasional anomalies."""
    base_temp = 65.0
    base_vibration = 2.5
    base_pressure = 100.0
    base_humidity = 45.0

    temp_var = random.uniform(-20, 5)
    vib_var = random.uniform(-0.5, 0.5)
    press_var = random.uniform(-10, 10)
    humid_var = random.uniform(-5, 5)

    # 10% chance of anomaly
    if random.random() < 0.1:
        print(f"  Anomaly injected for {sensor_id}")
        temp_var += random.uniform(15, 25)
        vib_var += random.uniform(3, 5)

    return {
        "sensor_id": sensor_id,
        "temperature": round(base_temp + temp_var, 2),
        "vibration": round(base_vibration + vib_var, 2),
        "pressure": round(base_pressure + press_var, 2),
        "humidity": round(base_humidity + humid_var, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"Connection failed with code {rc}")


def main():
    print("Industrial Sensor Data Simulator")
    print("=" * 50)
    print(f"Broker:  {MQTT_BROKER}:{MQTT_PORT}")
    print(f"API:     {BACKEND_API_URL}")
    print(f"Sensors: {len(SENSORS)}")
    print("=" * 50)

    # Register sensors with the backend API
    print("\nRegistering sensors...")
    register_sensors()

    # Connect to MQTT
    client = mqtt.Client()
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        print("\nPublishing sensor data (Ctrl+C to stop)\n")

        iteration = 0
        while True:
            iteration += 1
            print(f"--- Iteration {iteration} ---")

            for sensor in SENSORS:
                sid = sensor["sensor_id"]
                topic = f"sensors/{sid}"
                data = generate_sensor_data(sid)

                payload = json.dumps(data)
                result = client.publish(topic, payload)

                if result.rc == 0:
                    print(f"  [{topic}] Temp={data['temperature']}C "
                          f"Vib={data['vibration']}Hz "
                          f"Press={data['pressure']}Pa "
                          f"Humid={data['humidity']}%")
                else:
                    print(f"  Failed to publish to {topic}")

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nStopping simulator...")
        client.loop_stop()
        client.disconnect()
        print("Simulator stopped")

    except Exception as e:
        print(f"\nError: {e}")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
