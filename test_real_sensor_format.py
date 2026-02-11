#!/usr/bin/env python3
"""
Test publisher sending sensor data in real format (24 features only).
The MQTT ingestion service will do feature engineering to generate 336 features.
"""

import paho.mqtt.client as mqtt
import json
import time
import random
from datetime import datetime

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensor/asset1/data"

def generate_sensor_reading(fault_type=None):
    """Generate sensor reading in real format (24 base features only)"""
    
    # Base values for normal operation
    base_vib = 1.2
    base_temp = 43.0
    base_ultra = 35.0
    
    # Fault injection
    if fault_type == "bearing_overgrease_churning":
        vib_mult = random.uniform(1.8, 2.5)
        temp_mult = random.uniform(1.1, 1.3)
        ultra_mult = random.uniform(1.05, 1.15)
        fault_label = "bearing_overgrease_churning"
    elif fault_type == "impeller_damage":
        vib_mult = random.uniform(2.0, 3.0)
        temp_mult = random.uniform(1.0, 1.1)
        ultra_mult = random.uniform(1.1, 1.25)
        fault_label = "impeller_damage"
    elif fault_type == "phase_unbalance":
        vib_mult = random.uniform(1.5, 2.2)
        temp_mult = random.uniform(1.15, 1.35)
        ultra_mult = random.uniform(1.0, 1.1)
        fault_label = "phase_unbalance"
    elif fault_type == "cooling_failure":
        vib_mult = random.uniform(1.0, 1.2)
        temp_mult = random.uniform(1.6, 2.0)
        ultra_mult = random.uniform(1.0, 1.05)
        fault_label = "cooling_failure"
    elif fault_type == "coupling_wear":
        vib_mult = random.uniform(1.4, 1.9)
        temp_mult = random.uniform(1.05, 1.2)
        ultra_mult = random.uniform(1.0, 1.1)
        fault_label = "coupling_wear"
    else:
        vib_mult = random.uniform(0.95, 1.05)
        temp_mult = random.uniform(0.98, 1.02)
        ultra_mult = random.uniform(0.98, 1.02)
        fault_label = "normal"
    
    # Generate 24 base features
    reading = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state": "fault_injection" if fault_type else "nominal",
        "regime": "nominal",
        
        # Motor DE (4 vibration bands + ultrasound + temp)
        "motor_DE_vib_band_1": round(base_vib * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_DE_vib_band_2": round(base_vib * 0.85 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_DE_vib_band_3": round(base_vib * 0.65 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_DE_vib_band_4": round(base_vib * 0.55 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_DE_ultra_db": round(base_ultra * ultra_mult * random.uniform(0.98, 1.02), 2),
        "motor_DE_temp_c": round(base_temp * temp_mult * random.uniform(0.98, 1.02), 2),
        
        # Motor NDE (4 vibration bands + ultrasound + temp)
        "motor_NDE_vib_band_1": round(base_vib * 1.05 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_NDE_vib_band_2": round(base_vib * 0.9 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_NDE_vib_band_3": round(base_vib * 0.67 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_NDE_vib_band_4": round(base_vib * 0.52 * vib_mult * random.uniform(0.95, 1.05), 3),
        "motor_NDE_ultra_db": round(base_ultra * ultra_mult * random.uniform(0.98, 1.02), 2),
        "motor_NDE_temp_c": round(base_temp * temp_mult * random.uniform(0.98, 1.02), 2),
        
        # Pump DE (4 vibration bands + ultrasound + temp)
        "pump_DE_vib_band_1": round(base_vib * 1.08 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_DE_vib_band_2": round(base_vib * 0.92 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_DE_vib_band_3": round(base_vib * 0.66 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_DE_vib_band_4": round(base_vib * 0.64 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_DE_ultra_db": round((base_ultra + 4) * ultra_mult * random.uniform(0.98, 1.02), 2),
        "pump_DE_temp_c": round((base_temp - 1) * temp_mult * random.uniform(0.98, 1.02), 2),
        
        # Pump NDE (4 vibration bands + ultrasound + temp)
        "pump_NDE_vib_band_1": round(base_vib * 1.03 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_NDE_vib_band_2": round(base_vib * 0.84 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_NDE_vib_band_3": round(base_vib * 0.59 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_NDE_vib_band_4": round(base_vib * 0.61 * vib_mult * random.uniform(0.95, 1.05), 3),
        "pump_NDE_ultra_db": round((base_ultra + 3.5) * ultra_mult * random.uniform(0.98, 1.02), 2),
        "pump_NDE_temp_c": round((base_temp - 1) * temp_mult * random.uniform(0.98, 1.02), 2),
        
        "fault_label": fault_label
    }
    
    return reading

def main():
    """Publish sensor readings in real format"""
    
    client = mqtt.Client()
    
    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    print(f"Publishing sensor data to topic: {MQTT_TOPIC}")
    print("=" * 80)
    
    # Test scenarios
    fault_scenarios = [
        ("normal", 2),
        ("bearing_overgrease_churning", 2),
        ("impeller_damage", 2),
        ("phase_unbalance", 2),
        ("cooling_failure", 2),
        ("coupling_wear", 2),
    ]
    
    message_count = 0
    
    for fault_type, repeat in fault_scenarios:
        for _ in range(repeat):
            message_count += 1
            
            reading = generate_sensor_reading(fault_type)
            payload = json.dumps(reading)
            
            print(f"\nMessage {message_count}: {fault_type.upper()}")
            print(f"   Timestamp: {reading['timestamp']}")
            print(f"   Motor DE Vibration: {reading['motor_DE_vib_band_1']:.3f} mm/s")
            print(f"   Motor DE Temp: {reading['motor_DE_temp_c']:.2f} °C")
            print(f"   Pump DE Vibration: {reading['pump_DE_vib_band_1']:.3f} mm/s")
            print(f"   Fault Label: {reading['fault_label']}")
            
            result = client.publish(MQTT_TOPIC, payload)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"   [OK] Published successfully")
            else:
                print(f"   [ERROR] Publish failed: {result.rc}")
            
            time.sleep(3)  # Wait 3 seconds between messages
    
    print("\n" + "=" * 80)
    print(f"[DONE] Published {message_count} messages")
    print("Check logs: docker logs aastreli-mqtt-ingestion --tail 30")
    print("Check predictions: docker logs aastreli-mqtt-ingestion | Select-String 'ML Prediction'")
    
    client.disconnect()

if __name__ == "__main__":
    main()
