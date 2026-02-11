"""
Test cooling_failure on live MQTT system
"""
import json
import paho.mqtt.client as mqtt
import time
import sys

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"

# Load anomaly pattern
ANOMALY_FILE = r"c:\Users\mahmo\Desktop\assetReli\anomalies\cooling_failure_input.json"

def publish_anomaly():
    """Publish cooling_failure anomaly pattern to MQTT"""
    
    print("="*80)
    print("  TESTING COOLING FAILURE - LIVE MQTT SYSTEM")
    print("="*80)
    
    # Load anomaly data
    try:
        with open(ANOMALY_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"\n❌ Anomaly file not found: {ANOMALY_FILE}")
        sys.exit(1)
    
    window_data = data.get("window_data", [])
    if not window_data:
        print("\n❌ No window_data in anomaly file")
        sys.exit(1)
    
    # Pad window_data to 14 timesteps if needed (repeat last reading)
    while len(window_data) < 14:
        window_data.append(window_data[-1].copy())
    
    print(f"\n📦 Loaded/padded to {len(window_data)} timesteps from anomaly file")
    print(f"✅ Expected prediction: cooling_failure")
    
    # Connect to MQTT
    client = mqtt.Client()
    
    try:
        print(f"\n🔌 Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        time.sleep(1)  # Wait for connection
        
        print(f"\n📡 Publishing {len(window_data)} readings to '{MQTT_TOPIC}'...")
        
        # Publish all timesteps
        for i, reading in enumerate(window_data, 1):
            # Add sensor_id to reading
            reading["sensor_id"] = "cooling_failure_test"
            
            # Publish
            result = client.publish(MQTT_TOPIC, json.dumps(reading))
            
            if i % 5 == 0:
                print(f"  Published {i}/{len(window_data)} readings...")
            
            time.sleep(0.1)  # Small delay between readings
        
        print(f"\n✅ Published all {len(window_data)} readings")
        print("\n⏱️  Waiting 5 seconds for processing...")
        time.sleep(5)
        
        print("\n" + "="*80)
        print("  CHECK LOGS FOR RESULT")
        print("="*80)
        print("\n  docker logs aastreli-mqtt-ingestion --tail 30 | findstr /i \"cooling_failure\"")
        print("\n✅ Expected: cooling_failure (confidence ~73%)")
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("\n🔌 Disconnected from MQTT broker")

if __name__ == "__main__":
    publish_anomaly()
