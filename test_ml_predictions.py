"""Test ML Service Predictions"""
import requests
import json

# Test different feature patterns
test_cases = [
    {
        "name": "Normal Operation",
        "features": [1.16,1.06,0.75,0.66,1.35,1.05,0.89,0.70,35.0,44.0,1.36,0.89,0.92,0.91,1.74,1.05,1.08,1.01,36.0,42.0] + [0.0] * 316
    },
    {
        "name": "High Vibration (Bearing Fault)",
        "features": [5.5,4.2,3.1,2.8,6.1,5.3,4.2,3.5,45.0,55.0,5.8,4.5,3.9,3.2,7.2,6.1,5.4,4.3,48.0,52.0] + [0.0] * 316
    },
    {
        "name": "High Temperature",
        "features": [1.2,1.1,0.8,0.7,1.4,1.1,0.9,0.7,38.0,85.0,1.4,0.9,0.9,0.9,1.8,1.1,1.1,1.0,42.0,78.0] + [0.0] * 316
    },
    {
        "name": "All Zeros (Data Dropout)",
        "features": [0.0] * 336
    },
    {
        "name": "Very High Ultrasound",
        "features": [1.2,1.0,0.8,0.7,1.3,1.0,0.9,0.7,88.0,92.0,1.4,0.9,1.0,0.9,1.7,1.0,1.1,1.0,85.0,87.0] + [0.0] * 316
    }
]

print("=" * 80)
print("ML SERVICE PREDICTION TEST")
print("=" * 80)

for test in test_cases:
    try:
        response = requests.post(
            "http://localhost:8001/predict",
            json={"features": test["features"]},
            timeout=5
        )
        result = response.json()
        print(f"\nTest: {test['name']}")
        print(f"  Prediction: {result.get('prediction')}")
        print(f"  Confidence: {result.get('confidence', 0):.4f}")
        if 'top_predictions' in result:
            print(f"  Top 3:")
            for pred in result['top_predictions'][:3]:
                print(f"    - {pred['label']}: {pred['probability']:.4f}")
    except Exception as e:
        print(f"\nTest: {test['name']}")
        print(f"  ERROR: {e}")

print("\n" + "=" * 80)
print("CHECKING DATABASE PREDICTIONS")
print("=" * 80)

try:
    # Check what predictions are in the database
    import subprocess
    result = subprocess.run(
        ['docker', 'exec', 'aastreli-mongodb', 'mongosh', 'aastreli', '--quiet', '--eval',
         'db.sensor_readings.distinct("prediction")'],
        capture_output=True,
        text=True
    )
    print("\nUnique predictions in database:")
    print(result.stdout)
    
    # Count predictions
    result = subprocess.run(
        ['docker', 'exec', 'aastreli-mongodb', 'mongosh', 'aastreli', '--quiet', '--eval',
         'db.sensor_readings.aggregate([{$group: {_id: "$prediction", count: {$sum: 1}}}]).toArray()'],
        capture_output=True,
        text=True
    )
    print("\nPrediction counts:")
    print(result.stdout)
    
except Exception as e:
    print(f"Database check error: {e}")

print("\n" + "=" * 80)
