"""
Test script to publish MQTT data matching your real system format
"""
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime

# MQTT Configuration
BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "sensors/data"

def publish_test_data():
    """Publish test data matching your system's schema"""
    client = mqtt.Client()
    
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        print(f"✅ Connected to MQTT broker: {BROKER_HOST}:{BROKER_PORT}")
        
        # Sample data matching your format
        sensor_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "state": "fault_injections",
            "regime": "nominal",
            "motor_DE_vib_band_1": 1.1621228284774068,
            "motor_DE_vib_band_2": 1.0648153657040833,
            "motor_DE_vib_band_3": 0.747656691128974,
            "motor_DE_vib_band_4": 0.6599437360603098,
            "motor_DE_ultra_db": 35.526266079126906,
            "motor_DE_temp_c": 44.6,
            "motor_NDE_vib_band_1": 1.3501950879742473,
            "motor_NDE_vib_band_2": 1.0532905628546119,
            "motor_NDE_vib_band_3": 0.8945284437604059,
            "motor_NDE_vib_band_4": 0.7019707190919708,
            "motor_NDE_ultra_db": 34.12497334937679,
            "motor_NDE_temp_c": 44.4,
            "pump_DE_vib_band_1": 1.362221451694224,
            "pump_DE_vib_band_2": 0.8859158212281661,
            "pump_DE_vib_band_3": 0.9207954991086116,
            "pump_DE_vib_band_4": 0.9054051378532024,
            "pump_DE_ultra_db": 37.4,
            "pump_DE_temp_c": 42.12368089368843,
            "pump_NDE_vib_band_1": 1.7430029623443275,
            "pump_NDE_vib_band_2": 1.0509347155837236,
            "pump_NDE_vib_band_3": 1.0751336937335911,
            "pump_NDE_vib_band_4": 1.0140558979361147,
            "pump_NDE_ultra_db": 38.32876125251017,
            "pump_NDE_temp_c": 42.19633206228287,
            "fault_label": "normal"
        }
        
        # Publish the message
        payload = json.dumps(sensor_data)
        result = client.publish(TOPIC, payload)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"✅ Published message to {TOPIC}")
            print(f"   Timestamp: {sensor_data['timestamp']}")
            print(f"   Fault label: {sensor_data['fault_label']}")
        else:
            print(f"❌ Failed to publish: {result.rc}")
        
        time.sleep(1)  # Wait for message to be delivered
        client.disconnect()
        print("✅ Test complete")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("📡 Publishing test MQTT message...")
    publish_test_data()
