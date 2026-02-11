"""
Test cooling_failure detection by sending data with elevated temperatures
"""
import json
import requests
import time

ML_SERVICE_URL = "http://localhost:8001/predict"

# Create cooling_failure pattern: Progressive temperature rise
# Cooling failure is characterized by:
# - Rising motor temperatures (especially >50°C)
# - Rising pump temperatures
# - Normal vibration levels
# - Normal ultrasonic readings

def create_cooling_failure_window():
    """Create 14 timesteps showing progressive temperature rise"""
    window_data = []
    
    base_temp_motor = 45.0  # Start at normal
    base_temp_pump = 42.0
    
    for i in range(14):
        # Progressive temperature rise (2-3°C per reading)
        motor_temp = base_temp_motor + (i * 2.5)
        pump_temp = base_temp_pump + (i * 2.2)
        
        reading = {
            "motor_DE_vib_band_1": 1.2 + (i * 0.01),  # Slight increase
            "motor_DE_vib_band_2": 1.0 + (i * 0.008),
            "motor_DE_vib_band_3": 0.9 + (i * 0.007),
            "motor_DE_vib_band_4": 0.65 + (i * 0.005),
            "motor_DE_ultra_db": 34.0 + (i * 0.2),
            "motor_DE_temp_c": motor_temp,  # Rising temperature
            
            "motor_NDE_vib_band_1": 1.3 + (i * 0.01),
            "motor_NDE_vib_band_2": 1.05 + (i * 0.008),
            "motor_NDE_vib_band_3": 0.85 + (i * 0.007),
            "motor_NDE_vib_band_4": 0.62 + (i * 0.005),
            "motor_NDE_ultra_db": 34.0 + (i * 0.2),
            "motor_NDE_temp_c": motor_temp + 0.5,  # Rising temperature
            
            "pump_DE_vib_band_1": 1.25 + (i * 0.01),
            "pump_DE_vib_band_2": 1.07 + (i * 0.008),
            "pump_DE_vib_band_3": 1.18 + (i * 0.007),
            "pump_DE_vib_band_4": 0.96 + (i * 0.005),
            "pump_DE_ultra_db": 44.0 + (i * 0.3),
            "pump_DE_temp_c": pump_temp,  # Rising temperature
            
            "pump_NDE_vib_band_1": 1.17 + (i * 0.01),
            "pump_NDE_vib_band_2": 1.03 + (i * 0.008),
            "pump_NDE_vib_band_3": 1.08 + (i * 0.007),
            "pump_NDE_vib_band_4": 0.90 + (i * 0.005),
            "pump_NDE_ultra_db": 43.5 + (i * 0.3),
            "pump_NDE_temp_c": pump_temp + 1.0,  # Rising temperature
        }
        window_data.append(reading)
    
    return window_data

# Create window with cooling failure pattern
window = create_cooling_failure_window()

# Flatten to 336 features (14 timesteps × 24 features)
features = []
for reading in window:
    for key in [
        "motor_DE_vib_band_1", "motor_DE_vib_band_2", "motor_DE_vib_band_3", "motor_DE_vib_band_4",
        "motor_NDE_vib_band_1", "motor_NDE_vib_band_2", "motor_NDE_vib_band_3", "motor_NDE_vib_band_4",
        "motor_DE_ultra_db", "motor_NDE_ultra_db",
        "motor_DE_temp_c", "motor_NDE_temp_c",
        "pump_DE_vib_band_1", "pump_DE_vib_band_2", "pump_DE_vib_band_3", "pump_DE_vib_band_4",
        "pump_NDE_vib_band_1", "pump_NDE_vib_band_2", "pump_NDE_vib_band_3", "pump_NDE_vib_band_4",
        "pump_DE_ultra_db", "pump_NDE_ultra_db",
        "pump_DE_temp_c", "pump_NDE_temp_c",
    ]:
        features.append(reading[key])

print(f"Testing cooling_failure detection...")
print(f"Temperature profile:")
print(f"  Start: Motor={window[0]['motor_DE_temp_c']:.1f}°C, Pump={window[0]['pump_DE_temp_c']:.1f}°C")
print(f"  End:   Motor={window[13]['motor_DE_temp_c']:.1f}°C, Pump={window[13]['pump_DE_temp_c']:.1f}°C")
print(f"  Rise:  Motor=+{window[13]['motor_DE_temp_c'] - window[0]['motor_DE_temp_c']:.1f}°C, Pump=+{window[13]['pump_DE_temp_c'] - window[0]['pump_DE_temp_c']:.1f}°C\n")

# Send request
payload = {"features": features}

try:
    response = requests.post(ML_SERVICE_URL, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Status Code: {response.status_code}")
        print(f"\n📊 Prediction Results:")
        print(f"  Predicted Fault: {result['prediction']}")
        print(f"  Confidence: {result['confidence']:.4f} ({result['confidence']*100:.2f}%)")
        
        if 'top_predictions' in result:
            print(f"\n🏆 Top 5 Predictions:")
            for i, pred in enumerate(result['top_predictions'][:5], 1):
                # Handle both dict formats
                if isinstance(pred, dict):
                    fault = pred.get('fault_type') or pred.get('class') or pred.get('label')
                    conf = pred.get('confidence') or pred.get('probability')
                else:
                    fault = pred
                    conf = None
                    
                if conf is not None:
                    print(f"    {i}. {fault}: {conf:.4f} ({conf*100:.2f}%)")
                else:
                    print(f"    {i}. {fault}")
                
        # Check if cooling_failure was detected
        if result['prediction'] == 'cooling_failure':
            print(f"\n✅ SUCCESS: cooling_failure correctly detected!")
        else:
            print(f"\n⚠️ WARNING: Expected cooling_failure, got {result['prediction']}")
            print(f"   This indicates the model may need retraining with better cooling_failure examples")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Error: {e}")
