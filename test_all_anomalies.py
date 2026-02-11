"""
Test ML model against all anomaly patterns from the anomalies directory
"""
import json
import requests
import os
import numpy as np
from pathlib import Path
from collections import defaultdict

ML_SERVICE_URL = "http://localhost:8001/predict"
ANOMALIES_DIR = r"c:\Users\mahmo\Desktop\assetReli\anomalies"

# Sensor columns in exact order - matches notebook
SENSOR_COLUMNS = [
    'motor_DE_vib_band_1', 'motor_DE_vib_band_2', 'motor_DE_vib_band_3', 'motor_DE_vib_band_4',
    'motor_DE_ultra_db', 'motor_DE_temp_c',
    'motor_NDE_vib_band_1', 'motor_NDE_vib_band_2', 'motor_NDE_vib_band_3', 'motor_NDE_vib_band_4',
    'motor_NDE_ultra_db', 'motor_NDE_temp_c',
    'pump_DE_vib_band_1', 'pump_DE_vib_band_2', 'pump_DE_vib_band_3', 'pump_DE_vib_band_4',
    'pump_DE_ultra_db', 'pump_DE_temp_c',
    'pump_NDE_vib_band_1', 'pump_NDE_vib_band_2', 'pump_NDE_vib_band_3', 'pump_NDE_vib_band_4',
    'pump_NDE_ultra_db', 'pump_NDE_temp_c'
]

def extract_expected_fault(filename):
    """Extract expected fault type from filename"""
    # Remove _input.json and replace underscores with spaces
    fault = filename.replace("_input.json", "")
    return fault

def load_anomaly_file(filepath):
    """Load anomaly JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def extract_window_features(window_data):
    """
    Extract statistical features from window - MATCHES NOTEBOOK EXACTLY
    Creates 14 statistical features per sensor × 24 sensors = 336 features
    """
    features = []
    
    # Convert window_data to dictionary format for each sensor
    for sensor_col in SENSOR_COLUMNS:
        # Extract values for this sensor across all timesteps
        values = np.array([reading.get(sensor_col, 0.0) for reading in window_data])
        
        # Calculate 14 statistical features - EXACT MATCH to notebook
        features.extend([
            float(np.mean(values)),                           # 1. Mean
            float(np.std(values)),                            # 2. Standard deviation
            float(np.min(values)),                            # 3. Min
            float(np.max(values)),                            # 4. Max
            float(np.median(values)),                         # 5. Median
            float(np.percentile(values, 25)),                 # 6. 25th percentile
            float(np.percentile(values, 75)),                 # 7. 75th percentile
            float(np.max(values) - np.min(values)),          # 8. Range
            float(np.var(values)),                            # 9. Variance
            float(np.sqrt(np.mean(values**2))),              # 10. RMS
            float(np.mean(np.abs(values - np.mean(values)))), # 11. Mean absolute deviation
            float(np.sum(values)),                            # 12. Sum
            float(np.sum(values**2)),                         # 13. Sum of squares
            float(np.max(values) / (np.min(values) + 1e-8))  # 14. Max/Min ratio
        ])
    
    return features

def test_anomaly(filepath):
    """Test a single anomaly file"""
    filename = os.path.basename(filepath)
    expected_fault = extract_expected_fault(filename)
    
    try:
        data = load_anomaly_file(filepath)
        
        # Check if it has window_data or is single reading
        if "window_data" in data:
            features = extract_window_features(data["window_data"])
            expected = data.get("expected_fault", expected_fault)
        else:
            # Single reading - duplicate to create window
            reading = data
            window = [reading] * 14
            features = extract_window_features(window)
            expected = expected_fault
        
        # Make prediction
        payload = {"features": features}
        response = requests.post(ML_SERVICE_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            prediction = result['prediction']
            confidence = result['confidence']
            
            # Check if prediction matches expected
            is_correct = prediction == expected
            
            return {
                "filename": filename,
                "expected": expected,
                "predicted": prediction,
                "confidence": confidence,
                "correct": is_correct,
                "top_predictions": result.get('top_predictions', [])[:3],
                "status": "[OK]" if is_correct else "[FAIL]"
            }
        else:
            return {
                "filename": filename,
                "expected": expected,
                "error": f"HTTP {response.status_code}",
                "status": "[WARN]"
            }
            
    except Exception as e:
        return {
            "filename": filename,
            "expected": expected_fault,
            "error": str(e),
            "status": "[ERR]"
        }

def main():
    import sys
    import io
    
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("  ML MODEL EVALUATION - TESTING ALL ANOMALY PATTERNS")
    print("=" * 80)
    print()
    
    # Get all JSON files from anomalies directory
    anomaly_files = list(Path(ANOMALIES_DIR).glob("*_input.json"))
    anomaly_files.sort()
    
    print(f"Found {len(anomaly_files)} anomaly patterns\n")
    
    results = []
    correct_count = 0
    total_count = 0
    
    for filepath in anomaly_files:
        result = test_anomaly(filepath)
        results.append(result)
        
        if "error" not in result:
            total_count += 1
            if result["correct"]:
                correct_count += 1
    
    # Print detailed results
    print("\n" + "=" * 80)
    print("  DETAILED RESULTS")
    print("=" * 80)
    print()
    
    for result in results:
        print(f"{result['status']} {result['filename']}")
        print(f"   Expected:  {result['expected']}")
        
        if "error" in result:
            print(f"   Error:     {result['error']}")
        else:
            print(f"   Predicted: {result['predicted']} ({result['confidence']*100:.1f}% confidence)")
            
            if not result['correct']:
                print(f"   Top 3:     ", end="")
                top3 = result.get('top_predictions', [])[:3]
                if top3 and len(top3) > 0:
                    # Handle different response formats
                    formatted = []
                    for p in top3:
                        if isinstance(p, dict):
                            fault = p.get('fault_type') or p.get('class') or p.get('label') or str(p)
                            prob = p.get('probability') or p.get('confidence', 0)
                            formatted.append(f"{fault}({prob*100:.1f}%)")
                        else:
                            formatted.append(str(p))
                    print(", ".join(formatted))
                else:
                    print("N/A")
        
        print()
    
    # Print summary
    print("=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print()
    
    if total_count > 0:
        accuracy = (correct_count / total_count) * 100
        print(f"Overall Accuracy: {correct_count}/{total_count} ({accuracy:.1f}%)")
        print()
        
        # Group results by correctness
        correct_faults = [r['expected'] for r in results if r.get('correct', False)]
        incorrect_faults = [(r['expected'], r['predicted']) for r in results if not r.get('correct', True) and 'error' not in r]
        
        if correct_faults:
            print(f"[OK] Correctly Identified ({len(correct_faults)}):")
            for fault in sorted(set(correct_faults)):
                print(f"   - {fault}")
            print()
        
        if incorrect_faults:
            print(f"[FAIL] Misclassified ({len(incorrect_faults)}):")
            for expected, predicted in incorrect_faults:
                print(f"   - {expected} -> predicted as {predicted}")
            print()
        
        # Confusion analysis
        confusion = defaultdict(lambda: defaultdict(int))
        for result in results:
            if "error" not in result:
                confusion[result['expected']][result['predicted']] += 1
        
        print("[INFO] Model Performance by Fault Type:")
        print()
        for expected in sorted(confusion.keys()):
            predictions = confusion[expected]
            correct = predictions.get(expected, 0)
            total = sum(predictions.values())
            accuracy_pct = (correct / total * 100) if total > 0 else 0
            
            print(f"   {expected}: {accuracy_pct:.0f}% accurate")
            if predictions[expected] == 0:
                # Show what it was confused with
                top_confusion = sorted(predictions.items(), key=lambda x: x[1], reverse=True)[0]
                print(f"      -> Most often predicted as: {top_confusion[0]}")
    
    print()
    print("=" * 80)
    print()

if __name__ == "__main__":
    main()
