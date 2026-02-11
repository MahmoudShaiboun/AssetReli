"""
Direct ML Service Testing - No MQTT Required
Tests the ML service with various sensor patterns to verify predictions
"""
import requests
import numpy as np
import random
import json

ML_SERVICE_URL = "http://localhost:8001/predict"

def generate_features(pattern="normal"):
    """Generate 336 features for different patterns"""
    
    if pattern == "normal":
        # Normal operation - low vibration, normal temps
        motor_de_vib = [1.16, 1.06, 0.75, 0.66]
        motor_nde_vib = [1.35, 1.05, 0.89, 0.70]
        pump_de_vib = [1.36, 0.89, 0.92, 0.91]
        pump_nde_vib = [1.74, 1.05, 1.08, 1.01]
        motor_temps = [44.0, 43.5]
        pump_temps = [41.0, 40.5]
        ultrasounds = [35.0, 34.5, 37.0, 36.5]
        
    elif pattern == "bearing_fault":
        # High frequency vibration (bearing damage)
        motor_de_vib = [3.5, 3.2, 2.8, 2.4]
        motor_nde_vib = [3.8, 3.0, 2.5, 2.2]
        pump_de_vib = [1.4, 0.9, 0.95, 0.92]
        pump_nde_vib = [1.8, 1.1, 1.1, 1.0]
        motor_temps = [46.0, 45.0]
        pump_temps = [42.0, 41.0]
        ultrasounds = [48.0, 47.0, 38.0, 37.0]  # High ultrasound
        
    elif pattern == "imbalance":
        # Unbalance - high low frequency vibration
        motor_de_vib = [3.2, 1.1, 0.8, 0.7]
        motor_nde_vib = [3.5, 1.0, 0.9, 0.7]
        pump_de_vib = [4.2, 0.9, 0.95, 0.92]
        pump_nde_vib = [4.5, 1.1, 1.1, 1.0]
        motor_temps = [44.5, 43.8]
        pump_temps = [41.5, 40.8]
        ultrasounds = [36.0, 35.5, 38.0, 37.5]
        
    elif pattern == "cooling_failure":
        # High temperatures
        motor_de_vib = [1.2, 1.1, 0.8, 0.7]
        motor_nde_vib = [1.4, 1.0, 0.9, 0.7]
        pump_de_vib = [1.4, 0.9, 0.95, 0.92]
        pump_nde_vib = [1.8, 1.1, 1.1, 1.0]
        motor_temps = [85.0, 82.0]  # Very high temps
        pump_temps = [75.0, 73.0]
        ultrasounds = [37.0, 36.5, 39.0, 38.5]
        
    elif pattern == "misalignment":
        # Broadband vibration increase
        motor_de_vib = [2.0, 1.8, 1.5, 1.3]
        motor_nde_vib = [2.2, 1.7, 1.4, 1.2]
        pump_de_vib = [2.1, 1.6, 1.5, 1.4]
        pump_nde_vib = [2.4, 1.8, 1.6, 1.5]
        motor_temps = [48.0, 47.0]
        pump_temps = [44.0, 43.0]
        ultrasounds = [38.0, 37.5, 40.0, 39.5]
    
    else:  # zeros - data dropout
        motor_de_vib = [0.0, 0.0, 0.0, 0.0]
        motor_nde_vib = [0.0, 0.0, 0.0, 0.0]
        pump_de_vib = [0.0, 0.0, 0.0, 0.0]
        pump_nde_vib = [0.0, 0.0, 0.0, 0.0]
        motor_temps = [0.0, 0.0]
        pump_temps = [0.0, 0.0]
        ultrasounds = [0.0, 0.0, 0.0, 0.0]
    
    # Build 24 base features
    base_features = (
        motor_de_vib + [ultrasounds[0], motor_temps[0]] +
        motor_nde_vib + [ultrasounds[1], motor_temps[1]] +
        pump_de_vib + [ultrasounds[2], pump_temps[0]] +
        pump_nde_vib + [ultrasounds[3], pump_temps[1]]
    )
    
    # Generate 312 extended features (statistical + spectral)
    arr = np.array(base_features)
    extended = []
    
    # Add base values again
    extended.extend(base_features)
    
    # Statistical features
    extended.append(float(np.mean(arr)))
    extended.append(float(np.std(arr)))
    extended.append(float(np.max(arr)))
    extended.append(float(np.min(arr)))
    extended.append(float(np.median(arr)))
    extended.append(float(np.percentile(arr, 25)))
    extended.append(float(np.percentile(arr, 75)))
    extended.append(float(np.sqrt(np.mean(arr**2))))  # RMS
    extended.append(float(np.max(arr) - np.min(arr)))  # Peak-to-peak
    
    # Kurtosis and skewness
    if np.std(arr) > 0:
        extended.append(float(np.mean((arr - np.mean(arr))**4) / (np.std(arr)**4)))
        extended.append(float(np.mean((arr - np.mean(arr))**3) / (np.std(arr)**3)))
    else:
        extended.extend([0.0, 0.0])
    
    # Spectral features (simulated FFT bins) - need 278 more to reach 312 total
    for i in range(278):
        extended.append(random.uniform(0.01, 0.5))
    
    # Crest factor and form factor
    if np.mean(np.abs(arr)) > 0:
        extended.append(float(np.max(np.abs(arr)) / np.mean(np.abs(arr))))
    else:
        extended.append(1.0)
    
    if np.mean(arr) > 0:
        extended.append(float(np.sqrt(np.mean(arr**2)) / np.mean(np.abs(arr))))
    else:
        extended.append(1.0)
    
    # Ensure exactly 312 extended features
    while len(extended) < 312:
        extended.append(random.uniform(0.0, 0.1))
    
    # Combine: 24 base + 312 extended = 336 total
    all_features = base_features + extended[:312]
    
    # Verify count
    assert len(all_features) == 336, f"Expected 336 features, got {len(all_features)}"
    
    return all_features

def test_ml_service(pattern_name, features):
    """Test ML service with given features"""
    try:
        response = requests.post(
            ML_SERVICE_URL,
            json={"features": features},
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}
    
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 80)
    print("ML SERVICE DIRECT TESTING")
    print("=" * 80)
    print(f"\nTesting ML Service at: {ML_SERVICE_URL}")
    print(f"Feature count: 336\n")
    
    test_patterns = [
        ("Normal Operation", "normal"),
        ("Bearing Fault (High Vibration + Ultrasound)", "bearing_fault"),
        ("Imbalance (High Band 1)", "imbalance"),
        ("Cooling Failure (High Temperature)", "cooling_failure"),
        ("Misalignment (Broadband Vibration)", "misalignment"),
        ("Data Dropout (All Zeros)", "zeros"),
    ]
    
    results = []
    
    for test_name, pattern in test_patterns:
        print(f"\n{'='*80}")
        print(f"TEST: {test_name}")
        print(f"{'='*80}")
        
        features = generate_features(pattern)
        print(f"✓ Generated {len(features)} features")
        print(f"  Sample values: {features[:6]} ... {features[-3:]}")
        
        result = test_ml_service(test_name, features)
        
        if "error" in result:
            print(f"❌ ERROR: {result['error']}")
            if "detail" in result:
                print(f"   Detail: {result['detail'][:200]}")
        else:
            prediction = result.get('prediction', 'N/A')
            confidence = result.get('confidence', 0)
            
            print(f"\n🔮 PREDICTION: {prediction}")
            print(f"📊 CONFIDENCE: {confidence:.4f} ({confidence*100:.2f}%)")
            
            if 'top_predictions' in result:
                print(f"\n📈 TOP 3 PREDICTIONS:")
                for i, pred in enumerate(result['top_predictions'][:3], 1):
                    print(f"   {i}. {pred['label']}: {pred['confidence']:.4f}")
            
            results.append({
                "test": test_name,
                "prediction": prediction,
                "confidence": confidence
            })
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n{'Test':<50} {'Prediction':<30} {'Confidence':>10}")
    print("-" * 90)
    
    for r in results:
        print(f"{r['test']:<50} {r['prediction']:<30} {r['confidence']:>9.2%}")
    
    print("\n" + "=" * 80)
    print("✅ Testing complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
