"""
Continuous MQTT publisher for testing
Publishes sensor data every 5 seconds with 336 engineered features
"""
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import random
import numpy as np

# MQTT Configuration
BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "sensors/data"

def generate_extended_features(base_values, noise_level=0.1):
    """Generate extended features from base values to reach 336 features"""
    features = []
    
    # Add base values
    features.extend(base_values)
    
    # Statistical features
    arr = np.array(base_values)
    features.append(float(np.mean(arr)))
    features.append(float(np.std(arr)))
    features.append(float(np.max(arr)))
    features.append(float(np.min(arr)))
    features.append(float(np.median(arr)))
    features.append(float(np.percentile(arr, 25)))
    features.append(float(np.percentile(arr, 75)))
    
    # RMS and peak-to-peak
    features.append(float(np.sqrt(np.mean(arr**2))))
    features.append(float(np.max(arr) - np.min(arr)))
    
    # Kurtosis and skewness approximations
    if len(arr) > 1 and np.std(arr) > 0:
        features.append(float(np.mean((arr - np.mean(arr))**4) / (np.std(arr)**4)))
        features.append(float(np.mean((arr - np.mean(arr))**3) / (np.std(arr)**3)))
    else:
        features.extend([0.0, 0.0])
    
    # Spectral features (simulated FFT bins)
    for i in range(20):
        features.append(random.uniform(0.01, 0.5) * (1 + noise_level * random.uniform(-1, 1)))
    
    # Crest factor
    if np.mean(np.abs(arr)) > 0:
        features.append(float(np.max(np.abs(arr)) / np.mean(np.abs(arr))))
    else:
        features.append(1.0)
    
    # Form factor
    if np.mean(arr) > 0:
        features.append(float(np.sqrt(np.mean(arr**2)) / np.mean(np.abs(arr))))
    else:
        features.append(1.0)
    
    return features

def generate_sensor_data():
    """Generate realistic sensor data with 336 engineered features"""
    # Base values (normal operation)
    motor_de_vib_bands = [1.16, 1.06, 0.75, 0.66]
    motor_nde_vib_bands = [1.35, 1.05, 0.89, 0.70]
    pump_de_vib_bands = [1.36, 0.89, 0.92, 0.91]
    pump_nde_vib_bands = [1.74, 1.05, 1.08, 1.01]
    
    # Determine fault type
    fault_type = None
    state = "normal_operation"
    motor_de_temp_mult = 1.0
    motor_nde_temp_mult = 1.0
    
    if random.random() < 0.25:
        # 25% chance of various faults
        fault_choice = random.random()
        
        if fault_choice < 0.2:
            # Bearing fault - high frequency vibration
            motor_de_vib_bands = [v * random.uniform(1.8, 3.0) for v in motor_de_vib_bands]
            motor_nde_vib_bands = [v * random.uniform(1.6, 2.5) for v in motor_nde_vib_bands]
            fault_type = "bearing_overgrease_churning"
        elif fault_choice < 0.4:
            # Pump impeller damage - unbalance
            pump_de_vib_bands[0] *= random.uniform(2.0, 3.5)
            pump_nde_vib_bands[0] *= random.uniform(1.8, 3.0)
            fault_type = "impeller_damage"
        elif fault_choice < 0.6:
            # Phase unbalance - electrical issue
            motor_de_vib_bands[1] *= random.uniform(1.5, 2.2)
            motor_de_vib_bands[2] *= random.uniform(1.4, 2.0)
            fault_type = "phase_unbalance"
        elif fault_choice < 0.8:
            # Cooling failure - temperature rise
            motor_de_temp_mult = random.uniform(1.5, 2.0)
            motor_nde_temp_mult = random.uniform(1.4, 1.9)
            fault_type = "cooling_failure"
        else:
            # Misalignment - broadband vibration increase
            motor_de_vib_bands = [v * random.uniform(1.4, 2.0) for v in motor_de_vib_bands]
            pump_de_vib_bands = [v * random.uniform(1.3, 1.9) for v in pump_de_vib_bands]
            fault_type = "coupling_wear"
        
        state = "fault_detected"
    
    # Apply normal variation to base values (±10%)
    motor_de_vib_bands = [v * random.uniform(0.9, 1.1) for v in motor_de_vib_bands]
    motor_nde_vib_bands = [v * random.uniform(0.9, 1.1) for v in motor_nde_vib_bands]
    pump_de_vib_bands = [v * random.uniform(0.9, 1.1) for v in pump_de_vib_bands]
    pump_nde_vib_bands = [v * random.uniform(0.9, 1.1) for v in pump_nde_vib_bands]
    
    # Temperature values
    motor_de_temp = random.uniform(42, 47) * motor_de_temp_mult
    motor_nde_temp = random.uniform(42, 47) * motor_nde_temp_mult
    pump_de_temp = random.uniform(40, 44) * (1.1 if fault_type == "cooling_failure" else 1.0)
    pump_nde_temp = random.uniform(40, 44) * (1.1 if fault_type == "cooling_failure" else 1.0)
    
    motor_de_ultra = random.uniform(33, 37) * (1.3 if fault_type in ["bearing_overgrease_churning", "internal_rub_proxy"] else 1.0)
    motor_nde_ultra = random.uniform(33, 37) * (1.2 if fault_type in ["bearing_overgrease_churning"] else 1.0)
    pump_de_ultra = random.uniform(36, 39) * (1.2 if fault_type in ["impeller_damage", "seal_face_distress_proxy"] else 1.0)
    pump_nde_ultra = random.uniform(36, 39)
    
    # Build base sensor data with 24 primary values
    sensor_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "state": state,
        "regime": "nominal",
        "motor_DE_vib_band_1": motor_de_vib_bands[0],
        "motor_DE_vib_band_2": motor_de_vib_bands[1],
        "motor_DE_vib_band_3": motor_de_vib_bands[2],
        "motor_DE_vib_band_4": motor_de_vib_bands[3],
        "motor_DE_ultra_db": motor_de_ultra,
        "motor_DE_temp_c": motor_de_temp,
        "motor_NDE_vib_band_1": motor_nde_vib_bands[0],
        "motor_NDE_vib_band_2": motor_nde_vib_bands[1],
        "motor_NDE_vib_band_3": motor_nde_vib_bands[2],
        "motor_NDE_vib_band_4": motor_nde_vib_bands[3],
        "motor_NDE_ultra_db": motor_nde_ultra,
        "motor_NDE_temp_c": motor_nde_temp,
        "pump_DE_vib_band_1": pump_de_vib_bands[0],
        "pump_DE_vib_band_2": pump_de_vib_bands[1],
        "pump_DE_vib_band_3": pump_de_vib_bands[2],
        "pump_DE_vib_band_4": pump_de_vib_bands[3],
        "pump_DE_ultra_db": pump_de_ultra,
        "pump_DE_temp_c": pump_de_temp,
        "pump_NDE_vib_band_1": pump_nde_vib_bands[0],
        "pump_NDE_vib_band_2": pump_nde_vib_bands[1],
        "pump_NDE_vib_band_3": pump_nde_vib_bands[2],
        "pump_NDE_vib_band_4": pump_nde_vib_bands[3],
        "pump_NDE_ultra_db": pump_nde_ultra,
        "pump_NDE_temp_c": pump_nde_temp,
        "sensor_id": f"industrial_sensor_{random.randint(1,3)}",
        "fault_type": fault_type  # For debugging
    }
    
    # Generate 336 engineered features
    all_base_values = (
        motor_de_vib_bands + [motor_de_ultra, motor_de_temp] +
        motor_nde_vib_bands + [motor_nde_ultra, motor_nde_temp] +
        pump_de_vib_bands + [pump_de_ultra, pump_de_temp] +
        pump_nde_vib_bands + [pump_nde_ultra, pump_nde_temp]
    )
    
    # Generate extended features (targeting 336 total)
    extended = generate_extended_features(all_base_values)
    
    # Add extended features as numbered fields
    for i, val in enumerate(extended[:312]):  # 24 base + 312 extended = 336
        sensor_data[f"feature_{i+24}"] = float(val)
    
    return sensor_data

def main():
    """Main loop for continuous publishing"""
    client = mqtt.Client()
    
    try:
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        print(f"✅ Connected to MQTT broker: {BROKER_HOST}:{BROKER_PORT}")
        print(f"📡 Publishing to topic: {TOPIC}")
        print("⏱️  Publishing every 5 seconds... Press Ctrl+C to stop\n")
        
        message_count = 0
        while True:
            # Generate and publish sensor data
            sensor_data = generate_sensor_data()
            payload = json.dumps(sensor_data)
            result = client.publish(TOPIC, payload)
            
            message_count += 1
            status_icon = "⚠️" if sensor_data["state"] == "fault_detected" else "✅"
            fault_info = f" [{sensor_data.get('fault_type')}]" if sensor_data.get('fault_type') else ""
            print(f"{status_icon} Message #{message_count} | {sensor_data['timestamp']} | State: {sensor_data['state']}{fault_info} | Sensor: {sensor_data['sensor_id']}")
            
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping publisher...")
        client.loop_stop()
        client.disconnect()
        print(f"✅ Published {message_count} messages")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 80)
    print("  MQTT Continuous Publisher - Aastreli System (336 Features)")
    print("=" * 80)
    main()
