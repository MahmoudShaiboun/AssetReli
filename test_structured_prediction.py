"""
Test ML service with structured sensor data format
"""
import requests
import json

# Test data for air_gas_ingress fault
air_gas_ingress_data = {
    "timestamp": "2025-12-31 19:14:00",
    "motor_DE_vib_band_1": 1.214455883,
    "motor_DE_vib_band_2": 1.000316203,
    "motor_DE_vib_band_3": 0.951707565,
    "motor_DE_vib_band_4": 0.633685833,
    "motor_DE_ultra_db": 34.27373445,
    "motor_DE_temp_c": 44.82613797,
    "motor_NDE_vib_band_1": 1.303139892,
    "motor_NDE_vib_band_2": 1.049893763,
    "motor_NDE_vib_band_3": 0.852789328,
    "motor_NDE_vib_band_4": 0.612093125,
    "motor_NDE_ultra_db": 33.98650489,
    "motor_NDE_temp_c": 44.93635378,
    "pump_DE_vib_band_1": 1.245676051,
    "pump_DE_vib_band_2": 1.065547248,
    "pump_DE_vib_band_3": 1.177302897,
    "pump_DE_vib_band_4": 0.955404368,
    "pump_DE_ultra_db": 43.93242271,
    "pump_DE_temp_c": 42.10419328,
    "pump_NDE_vib_band_1": 1.167457931,
    "pump_NDE_vib_band_2": 1.034660082,
    "pump_NDE_vib_band_3": 1.080542864,
    "pump_NDE_vib_band_4": 0.903014606,
    "pump_NDE_ultra_db": 43.10568606,
    "pump_NDE_temp_c": 42.03743536,
    "top_k": 5
}

print("🧪 Testing ML Service with Structured Data Format")
print("=" * 60)

# Test the prediction endpoint
try:
    response = requests.post(
        "http://localhost:8001/predict",
        json=air_gas_ingress_data,
        timeout=10
    )
    
    print(f"\n✅ Status Code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n🔮 PREDICTION RESULTS:")
        print(f"   Predicted Fault: {result['prediction']}")
        print(f"   Confidence: {result['confidence']:.4f} ({result['confidence']*100:.2f}%)")
        print(f"   Model Version: {result['model_version']}")
        print(f"\n📊 Top {len(result['top_predictions'])} Predictions:")
        for i, pred in enumerate(result['top_predictions'], 1):
            print(f"   {i}. {pred['label']:35} - {pred['confidence']:.4f} ({pred['confidence']*100:.2f}%)")
        
        print(f"\n✅ Expected: air_gas_ingress")
        print(f"   Got: {result['prediction']}")
        
        if "air_gas_ingress" in [p['label'] for p in result['top_predictions'][:5]]:
            print("   ✅ air_gas_ingress is in top 5 predictions!")
        else:
            print("   ⚠️  air_gas_ingress not in top 5 predictions")
    else:
        print(f"\n❌ Error: {response.text}")

except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "=" * 60)
print("Test completed!")
