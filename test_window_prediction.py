#!/usr/bin/env python3
"""
Test ML prediction with time window data.
Aggregates multiple timesteps into 336 features for prediction.
"""

import requests
import json
import numpy as np

ML_SERVICE_URL = "http://localhost:8001/predict"

def extract_features_from_window(window_data):
    """
    Extract 336 features from time window data (10 timesteps x 24 features).
    
    Strategy:
    1. Extract 24 base features from the LAST reading in window
    2. Generate statistical features across the time window
    3. Generate spectral features (simulated)
    """
    
    # Extract all 24 base features from each timestep
    all_readings = []
    for reading in window_data:
        base_features = [
            reading.get("motor_DE_vib_band_1", 0.0),
            reading.get("motor_DE_vib_band_2", 0.0),
            reading.get("motor_DE_vib_band_3", 0.0),
            reading.get("motor_DE_vib_band_4", 0.0),
            reading.get("motor_DE_ultra_db", 0.0),
            reading.get("motor_DE_temp_c", 0.0),
            reading.get("motor_NDE_vib_band_1", 0.0),
            reading.get("motor_NDE_vib_band_2", 0.0),
            reading.get("motor_NDE_vib_band_3", 0.0),
            reading.get("motor_NDE_vib_band_4", 0.0),
            reading.get("motor_NDE_ultra_db", 0.0),
            reading.get("motor_NDE_temp_c", 0.0),
            reading.get("pump_DE_vib_band_1", 0.0),
            reading.get("pump_DE_vib_band_2", 0.0),
            reading.get("pump_DE_vib_band_3", 0.0),
            reading.get("pump_DE_vib_band_4", 0.0),
            reading.get("pump_DE_ultra_db", 0.0),
            reading.get("pump_DE_temp_c", 0.0),
            reading.get("pump_NDE_vib_band_1", 0.0),
            reading.get("pump_NDE_vib_band_2", 0.0),
            reading.get("pump_NDE_vib_band_3", 0.0),
            reading.get("pump_NDE_vib_band_4", 0.0),
            reading.get("pump_NDE_ultra_db", 0.0),
            reading.get("pump_NDE_temp_c", 0.0),
        ]
        all_readings.append(base_features)
    
    # Convert to numpy array (timesteps x features)
    window_array = np.array(all_readings)
    
    # Use last reading as base features (24 features)
    last_reading = window_array[-1, :]
    
    # Generate extended features (312 more)
    extended_features = []
    
    # Add base values again (24 features)
    extended_features.extend(last_reading.tolist())
    
    # Statistical features across time window for each sensor (24 * 5 = 120 features)
    # For each of 24 sensors: mean, std, max, min, range
    for sensor_idx in range(24):
        sensor_timeseries = window_array[:, sensor_idx]
        extended_features.append(float(np.mean(sensor_timeseries)))
        extended_features.append(float(np.std(sensor_timeseries)))
        extended_features.append(float(np.max(sensor_timeseries)))
        extended_features.append(float(np.min(sensor_timeseries)))
        extended_features.append(float(np.max(sensor_timeseries) - np.min(sensor_timeseries)))
    
    # Overall statistics (11 features)
    flat_data = window_array.flatten()
    extended_features.append(float(np.mean(flat_data)))
    extended_features.append(float(np.std(flat_data)))
    extended_features.append(float(np.max(flat_data)))
    extended_features.append(float(np.min(flat_data)))
    extended_features.append(float(np.median(flat_data)))
    extended_features.append(float(np.percentile(flat_data, 25)))
    extended_features.append(float(np.percentile(flat_data, 75)))
    extended_features.append(float(np.sqrt(np.mean(flat_data**2))))  # RMS
    extended_features.append(float(np.max(flat_data) - np.min(flat_data)))  # Peak-to-peak
    
    # Kurtosis and skewness (2 features)
    if np.std(flat_data) > 0:
        extended_features.append(float(np.mean((flat_data - np.mean(flat_data))**4) / (np.std(flat_data)**4)))
        extended_features.append(float(np.mean((flat_data - np.mean(flat_data))**3) / (np.std(flat_data)**3)))
    else:
        extended_features.extend([0.0, 0.0])
    
    # Temporal trend features (24 features - slope for each sensor)
    for sensor_idx in range(24):
        sensor_timeseries = window_array[:, sensor_idx]
        time_indices = np.arange(len(sensor_timeseries))
        if len(sensor_timeseries) > 1:
            slope = np.polyfit(time_indices, sensor_timeseries, 1)[0]
            extended_features.append(float(slope))
        else:
            extended_features.append(0.0)
    
    # Spectral features (simulated FFT bins) - fill remaining to reach 312
    current_count = len(extended_features)
    needed = 312 - current_count
    
    for i in range(needed):
        # Generate simulated spectral features based on vibration data variance
        vib_std = np.std(window_array[:, :16])  # Vibration bands only
        extended_features.append(float(np.random.uniform(0.01, 0.1) * vib_std))
    
    # Combine: 24 base + 312 extended = 336 total
    all_features = last_reading.tolist() + extended_features[:312]
    
    assert len(all_features) == 336, f"Expected 336 features, got {len(all_features)}"
    
    return all_features

def test_window_prediction(window_data, expected_fault):
    """Test ML prediction with time window data"""
    
    print("=" * 80)
    print(f"TIME WINDOW PREDICTION TEST")
    print("=" * 80)
    print(f"Window size: {len(window_data)} timesteps")
    print(f"First timestamp: {window_data[0]['timestamp']}")
    print(f"Last timestamp: {window_data[-1]['timestamp']}")
    print(f"Expected fault: {expected_fault}")
    print()
    
    # Extract 336 features from time window
    print("Extracting features from time window...")
    features = extract_features_from_window(window_data)
    print(f"[OK] Generated {len(features)} features")
    
    # Show some key values from last reading
    last_reading = window_data[-1]
    print(f"\nLast reading values:")
    print(f"  Motor DE Vib Band 1: {last_reading['motor_DE_vib_band_1']:.3f} mm/s")
    print(f"  Motor DE Temp: {last_reading['motor_DE_temp_c']:.2f} C")
    print(f"  Pump DE Vib Band 1: {last_reading['pump_DE_vib_band_1']:.3f} mm/s")
    
    # Calculate window statistics
    vib_values = []
    for reading in window_data:
        vib_values.extend([
            reading['motor_DE_vib_band_1'],
            reading['motor_NDE_vib_band_1'],
            reading['pump_DE_vib_band_1'],
            reading['pump_NDE_vib_band_1']
        ])
    
    print(f"\nWindow statistics (all vibration band 1):")
    print(f"  Mean: {np.mean(vib_values):.3f} mm/s")
    print(f"  Std Dev: {np.std(vib_values):.3f} mm/s")
    print(f"  Min: {np.min(vib_values):.3f} mm/s")
    print(f"  Max: {np.max(vib_values):.3f} mm/s")
    
    # Send to ML service
    print(f"\nSending to ML service: {ML_SERVICE_URL}")
    try:
        response = requests.post(
            ML_SERVICE_URL,
            json={"features": features},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "=" * 80)
            print("PREDICTION RESULT")
            print("=" * 80)
            
            # Handle different response formats
            fault_type = result.get('fault_type') or result.get('prediction')
            confidence = result.get('confidence') or result.get('probability', 0)
            top_3 = result.get('top_3', [])
            
            print(f"Predicted Fault: {fault_type}")
            print(f"Confidence: {confidence:.4f} ({confidence*100:.2f}%)")
            
            if top_3:
                print(f"\nTop 3 Predictions:")
                for i, item in enumerate(top_3, 1):
                    if isinstance(item, dict):
                        fault = item.get('class') or item.get('fault')
                        conf = item.get('confidence') or item.get('probability', 0)
                    else:
                        fault, conf = item
                    print(f"  {i}. {fault}: {conf:.4f} ({conf*100:.2f}%)")
            
            print(f"\nExpected: {expected_fault}")
            if fault_type == expected_fault:
                print("[OK] Prediction matches expected fault!")
            else:
                print("[MISMATCH] Prediction does not match expected fault")
            
            return result
            
        else:
            print(f"[ERROR] ML service returned status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to connect to ML service: {e}")
        return None

def main():
    """Main test function"""
    
    # Load test data from user's input
    test_data = {
        "window_data": [
            {
                "timestamp": "2025-12-26 02:25:00",
                "motor_DE_vib_band_1": 1.482433655,
                "motor_DE_vib_band_2": 1.261839258,
                "motor_DE_vib_band_3": 0.832362888,
                "motor_DE_vib_band_4": 0.609325903,
                "motor_DE_ultra_db": 33.95041074,
                "motor_DE_temp_c": 45.02543918,
                "motor_NDE_vib_band_1": 1.496734544,
                "motor_NDE_vib_band_2": 1.209545089,
                "motor_NDE_vib_band_3": 0.82170755,
                "motor_NDE_vib_band_4": 0.625700271,
                "motor_NDE_ultra_db": 33.59208869,
                "motor_NDE_temp_c": 44.79274554,
                "pump_DE_vib_band_1": 1.505032218,
                "pump_DE_vib_band_2": 1.304806782,
                "pump_DE_vib_band_3": 0.887586866,
                "pump_DE_vib_band_4": 0.729873775,
                "pump_DE_ultra_db": 38.94680918,
                "pump_DE_temp_c": 42.01605235,
                "pump_NDE_vib_band_1": 1.626882396,
                "pump_NDE_vib_band_2": 1.314549145,
                "pump_NDE_vib_band_3": 0.883738228,
                "pump_NDE_vib_band_4": 0.790347372,
                "pump_NDE_ultra_db": 38.62108166,
                "pump_NDE_temp_c": 41.92385151
            },
            {
                "timestamp": "2025-12-26 02:26:00",
                "motor_DE_vib_band_1": 1.553870693,
                "motor_DE_vib_band_2": 1.251783413,
                "motor_DE_vib_band_3": 0.893627197,
                "motor_DE_vib_band_4": 0.641161051,
                "motor_DE_ultra_db": 33.48613596,
                "motor_DE_temp_c": 45.0854033,
                "motor_NDE_vib_band_1": 1.544664781,
                "motor_NDE_vib_band_2": 1.217967115,
                "motor_NDE_vib_band_3": 0.900527368,
                "motor_NDE_vib_band_4": 0.662899065,
                "motor_NDE_ultra_db": 33.54363904,
                "motor_NDE_temp_c": 44.99022578,
                "pump_DE_vib_band_1": 1.461269885,
                "pump_DE_vib_band_2": 1.229325783,
                "pump_DE_vib_band_3": 0.837184249,
                "pump_DE_vib_band_4": 0.763608938,
                "pump_DE_ultra_db": 38.92545003,
                "pump_DE_temp_c": 41.89732943,
                "pump_NDE_vib_band_1": 1.660899428,
                "pump_NDE_vib_band_2": 1.300512511,
                "pump_NDE_vib_band_3": 0.788595853,
                "pump_NDE_vib_band_4": 0.783702421,
                "pump_NDE_ultra_db": 38.76656361,
                "pump_NDE_temp_c": 41.96118122
            },
            {
                "timestamp": "2025-12-26 02:27:00",
                "motor_DE_vib_band_1": 1.576307608,
                "motor_DE_vib_band_2": 1.19294846,
                "motor_DE_vib_band_3": 0.901450766,
                "motor_DE_vib_band_4": 0.660879104,
                "motor_DE_ultra_db": 34.0158238,
                "motor_DE_temp_c": 45.05127398,
                "motor_NDE_vib_band_1": 1.518850037,
                "motor_NDE_vib_band_2": 1.116686568,
                "motor_NDE_vib_band_3": 0.878285096,
                "motor_NDE_vib_band_4": 0.621997864,
                "motor_NDE_ultra_db": 33.78044605,
                "motor_NDE_temp_c": 44.93548346,
                "pump_DE_vib_band_1": 1.561162902,
                "pump_DE_vib_band_2": 1.227853616,
                "pump_DE_vib_band_3": 0.856325219,
                "pump_DE_vib_band_4": 0.754893545,
                "pump_DE_ultra_db": 38.84358919,
                "pump_DE_temp_c": 42.10347408,
                "pump_NDE_vib_band_1": 1.429246286,
                "pump_NDE_vib_band_2": 1.272591257,
                "pump_NDE_vib_band_3": 0.872881717,
                "pump_NDE_vib_band_4": 0.751777053,
                "pump_NDE_ultra_db": 38.66216924,
                "pump_NDE_temp_c": 42.03541642
            },
            {
                "timestamp": "2025-12-26 02:28:00",
                "motor_DE_vib_band_1": 1.470823682,
                "motor_DE_vib_band_2": 1.188093689,
                "motor_DE_vib_band_3": 0.839527531,
                "motor_DE_vib_band_4": 0.655761934,
                "motor_DE_ultra_db": 33.74864541,
                "motor_DE_temp_c": 44.90020115,
                "motor_NDE_vib_band_1": 1.515903832,
                "motor_NDE_vib_band_2": 1.249209849,
                "motor_NDE_vib_band_3": 0.803556846,
                "motor_NDE_vib_band_4": 0.664289905,
                "motor_NDE_ultra_db": 34.35879603,
                "motor_NDE_temp_c": 45.11716193,
                "pump_DE_vib_band_1": 1.461562601,
                "pump_DE_vib_band_2": 1.174443622,
                "pump_DE_vib_band_3": 0.817478591,
                "pump_DE_vib_band_4": 0.763882617,
                "pump_DE_ultra_db": 39.05441658,
                "pump_DE_temp_c": 42.10181976,
                "pump_NDE_vib_band_1": 1.616908889,
                "pump_NDE_vib_band_2": 1.217671999,
                "pump_NDE_vib_band_3": 0.869399924,
                "pump_NDE_vib_band_4": 0.787296369,
                "pump_NDE_ultra_db": 38.99225418,
                "pump_NDE_temp_c": 42.00777298
            },
            {
                "timestamp": "2025-12-26 02:29:00",
                "motor_DE_vib_band_1": 1.394094764,
                "motor_DE_vib_band_2": 1.195782618,
                "motor_DE_vib_band_3": 0.857604371,
                "motor_DE_vib_band_4": 0.679493034,
                "motor_DE_ultra_db": 34.19659297,
                "motor_DE_temp_c": 44.88447441,
                "motor_NDE_vib_band_1": 1.523737796,
                "motor_NDE_vib_band_2": 1.24235743,
                "motor_NDE_vib_band_3": 0.862057202,
                "motor_NDE_vib_band_4": 0.630773857,
                "motor_NDE_ultra_db": 34.09091853,
                "motor_NDE_temp_c": 44.78118631,
                "pump_DE_vib_band_1": 1.633889128,
                "pump_DE_vib_band_2": 1.274013431,
                "pump_DE_vib_band_3": 0.891552082,
                "pump_DE_vib_band_4": 0.766334856,
                "pump_DE_ultra_db": 39.115516,
                "pump_DE_temp_c": 41.97157577,
                "pump_NDE_vib_band_1": 1.573209933,
                "pump_NDE_vib_band_2": 1.171697874,
                "pump_NDE_vib_band_3": 0.843003587,
                "pump_NDE_vib_band_4": 0.765196849,
                "pump_NDE_ultra_db": 39.19460686,
                "pump_NDE_temp_c": 41.86475492
            },
            {
                "timestamp": "2025-12-26 02:30:00",
                "motor_DE_vib_band_1": 1.532808021,
                "motor_DE_vib_band_2": 1.237502452,
                "motor_DE_vib_band_3": 0.842141359,
                "motor_DE_vib_band_4": 0.644934686,
                "motor_DE_ultra_db": 33.80389438,
                "motor_DE_temp_c": 45.04166907,
                "motor_NDE_vib_band_1": 1.610376646,
                "motor_NDE_vib_band_2": 1.178279538,
                "motor_NDE_vib_band_3": 0.854935882,
                "motor_NDE_vib_band_4": 0.632447313,
                "motor_NDE_ultra_db": 34.00853703,
                "motor_NDE_temp_c": 44.97913829,
                "pump_DE_vib_band_1": 1.491872437,
                "pump_DE_vib_band_2": 1.23991908,
                "pump_DE_vib_band_3": 0.868606096,
                "pump_DE_vib_band_4": 0.718351181,
                "pump_DE_ultra_db": 38.7712206,
                "pump_DE_temp_c": 41.68167548,
                "pump_NDE_vib_band_1": 1.538962548,
                "pump_NDE_vib_band_2": 1.2238636,
                "pump_NDE_vib_band_3": 0.824719169,
                "pump_NDE_vib_band_4": 0.731123522,
                "pump_NDE_ultra_db": 38.95882097,
                "pump_NDE_temp_c": 42.00165072
            },
            {
                "timestamp": "2025-12-26 02:31:00",
                "motor_DE_vib_band_1": 1.505292018,
                "motor_DE_vib_band_2": 1.249818803,
                "motor_DE_vib_band_3": 0.863206844,
                "motor_DE_vib_band_4": 0.680174992,
                "motor_DE_ultra_db": 33.880981,
                "motor_DE_temp_c": 45.11656651,
                "motor_NDE_vib_band_1": 1.614602882,
                "motor_NDE_vib_band_2": 1.252676283,
                "motor_NDE_vib_band_3": 0.815238009,
                "motor_NDE_vib_band_4": 0.687251409,
                "motor_NDE_ultra_db": 34.11766809,
                "motor_NDE_temp_c": 44.79235633,
                "pump_DE_vib_band_1": 1.459725935,
                "pump_DE_vib_band_2": 1.28709558,
                "pump_DE_vib_band_3": 0.849646079,
                "pump_DE_vib_band_4": 0.765114495,
                "pump_DE_ultra_db": 39.36322137,
                "pump_DE_temp_c": 42.03041893,
                "pump_NDE_vib_band_1": 1.540425957,
                "pump_NDE_vib_band_2": 1.21789603,
                "pump_NDE_vib_band_3": 0.819333553,
                "pump_NDE_vib_band_4": 0.704959081,
                "pump_NDE_ultra_db": 38.69654468,
                "pump_NDE_temp_c": 41.77258977
            },
            {
                "timestamp": "2025-12-26 02:32:00",
                "motor_DE_vib_band_1": 1.463834908,
                "motor_DE_vib_band_2": 1.134914553,
                "motor_DE_vib_band_3": 0.778638711,
                "motor_DE_vib_band_4": 0.62368626,
                "motor_DE_ultra_db": 33.93145905,
                "motor_DE_temp_c": 45.03795404,
                "motor_NDE_vib_band_1": 1.536669562,
                "motor_NDE_vib_band_2": 1.218558964,
                "motor_NDE_vib_band_3": 0.824456089,
                "motor_NDE_vib_band_4": 0.656085782,
                "motor_NDE_ultra_db": 34.31056447,
                "motor_NDE_temp_c": 44.91139706,
                "pump_DE_vib_band_1": 1.636470007,
                "pump_DE_vib_band_2": 1.123330425,
                "pump_DE_vib_band_3": 0.854907036,
                "pump_DE_vib_band_4": 0.74557266,
                "pump_DE_ultra_db": 38.91656636,
                "pump_DE_temp_c": 41.94210279,
                "pump_NDE_vib_band_1": 1.500675338,
                "pump_NDE_vib_band_2": 1.213045935,
                "pump_NDE_vib_band_3": 0.822032389,
                "pump_NDE_vib_band_4": 0.783112474,
                "pump_NDE_ultra_db": 39.26407395,
                "pump_NDE_temp_c": 42.06571214
            },
            {
                "timestamp": "2025-12-26 02:33:00",
                "motor_DE_vib_band_1": 1.480420235,
                "motor_DE_vib_band_2": 1.283613238,
                "motor_DE_vib_band_3": 0.883620109,
                "motor_DE_vib_band_4": 0.636816245,
                "motor_DE_ultra_db": 34.41228674,
                "motor_DE_temp_c": 45.14587847,
                "motor_NDE_vib_band_1": 1.5444521,
                "motor_NDE_vib_band_2": 1.298740034,
                "motor_NDE_vib_band_3": 0.769484142,
                "motor_NDE_vib_band_4": 0.603784065,
                "motor_NDE_ultra_db": 34.07172129,
                "motor_NDE_temp_c": 45.02955333,
                "pump_DE_vib_band_1": 1.586370423,
                "pump_DE_vib_band_2": 1.103907426,
                "pump_DE_vib_band_3": 0.835850454,
                "pump_DE_vib_band_4": 0.759841707,
                "pump_DE_ultra_db": 39.19649815,
                "pump_DE_temp_c": 42.00755183,
                "pump_NDE_vib_band_1": 1.575727986,
                "pump_NDE_vib_band_2": 1.300026484,
                "pump_NDE_vib_band_3": 0.798601619,
                "pump_NDE_vib_band_4": 0.782257177,
                "pump_NDE_ultra_db": 38.93454069,
                "pump_NDE_temp_c": 41.91154973
            },
            {
                "timestamp": "2025-12-26 02:34:00",
                "motor_DE_vib_band_1": 1.630454949,
                "motor_DE_vib_band_2": 1.276532403,
                "motor_DE_vib_band_3": 0.843651944,
                "motor_DE_vib_band_4": 0.65354967,
                "motor_DE_ultra_db": 34.17711869,
                "motor_DE_temp_c": 44.94736723,
                "motor_NDE_vib_band_1": 1.538749065,
                "motor_NDE_vib_band_2": 1.323926029,
                "motor_NDE_vib_band_3": 0.813113334,
                "motor_NDE_vib_band_4": 0.660156801,
                "motor_NDE_ultra_db": 34.32043139,
                "motor_NDE_temp_c": 45.1115911,
                "pump_DE_vib_band_1": 1.58340761,
                "pump_DE_vib_band_2": 1.281271418,
                "pump_DE_vib_band_3": 0.816187233,
                "pump_DE_vib_band_4": 0.765587917,
                "pump_DE_ultra_db": 38.90155065,
                "pump_DE_temp_c": 41.94006919,
                "pump_NDE_vib_band_1": 1.584736241,
                "pump_NDE_vib_band_2": 1.256088175,
                "pump_NDE_vib_band_3": 0.935718843,
                "pump_NDE_vib_band_4": 0.774684889,
                "pump_NDE_ultra_db": 39.63907618,
                "pump_NDE_temp_c": 42.04659989
            }
        ],
        "expected_fault": "belt_slip_or_drive_issue_proxy"
    }
    
    # Run prediction test
    result = test_window_prediction(
        test_data["window_data"],
        test_data["expected_fault"]
    )
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
