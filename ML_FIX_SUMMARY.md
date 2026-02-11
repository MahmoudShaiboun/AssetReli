# ML PREDICTION FIX - ROOT CAUSE ANALYSIS

## Problem Summary
User reported: "i am simulating faults like cooling_failure and the frontend gives me (stuck_sensor_flatline, instrument_scaling_error)"

Later discovered: "i tried electrical_fluting and this return air_gas_ingress. but in the notebook return the correct fault"

## Root Cause
The ML model was trained on **statistical features** (mean, std, min, max, etc.) extracted from time-series windows, but the live MQTT system was sending **raw flattened sensor values**. Additionally, there was a critical **sensor ordering mismatch**.

## Two Critical Issues Found

### Issue 1: Feature Type Mismatch
**Problem:**
- **Notebook/Training**: Used statistical features (14 stats per sensor × 24 sensors = 336 features)
  - For each sensor: mean, std, min, max, median, percentiles, range, variance, RMS, MAD, sum, sum_squares, max/min_ratio
- **Live System**: Was flattening raw values (14 timesteps × 24 sensors = 336 features)
  - Just concatenating raw sensor readings

**Impact:**
- Model trained on statistical aggregates couldn't interpret raw time-series values
- Accuracy dropped to 6.2% (1/16 patterns)
- After fix: **75% accuracy (12/16 patterns)**

### Issue 2: Sensor Column Ordering Mismatch
**Problem:**
- **Notebook Order** (Correct):
  ```
  1. Motor DE: vib_band_1-4, ultra_db, temp_c
  2. Motor NDE: vib_band_1-4, ultra_db, temp_c
  3. Pump DE: vib_band_1-4, ultra_db, temp_c
  4. Pump NDE: vib_band_1-4, ultra_db, temp_c
  ```

- **MQTT Client Order** (Wrong):
  ```
  1. Motor DE: vib_band_1-4
  2. Motor NDE: vib_band_1-4
  3. Motor DE/NDE: ultra_db (both)
  4. Motor DE/NDE: temp_c (both)
  5. Pump DE: vib_band_1-4
  6. Pump NDE: vib_band_1-4
  7. Pump DE/NDE: ultra_db (both)
  8. Pump DE/NDE: temp_c (both)
  ```

**Impact:**
- Features were in wrong positions
- Model couldn't correctly interpret sensor readings
- electrical_fluting → predicted as instrument_scaling_error (48% confidence)
- After fix: electrical_fluting → **electrical_fluting (96% confidence)**

## Files Modified

### 1. `test_all_anomalies.py`
**Changes:**
- Replaced `flatten_window_to_features()` with `extract_window_features()`
- Now calculates 14 statistical features per sensor (matching notebook)
- Added numpy import for statistical calculations

**Before:**
```python
def flatten_window_to_features(window_data):
    features = []
    for reading in window_data[:14]:
        for key in SENSOR_COLUMNS:
            features.append(reading.get(key, 0.0))
    return features  # Raw values
```

**After:**
```python
def extract_window_features(window_data):
    features = []
    for sensor_col in SENSOR_COLUMNS:
        values = np.array([reading.get(sensor_col, 0.0) for reading in window_data])
        features.extend([
            np.mean(values), np.std(values), np.min(values), np.max(values),
            np.median(values), np.percentile(values, 25), np.percentile(values, 75),
            np.max(values) - np.min(values), np.var(values),
            np.sqrt(np.mean(values**2)), np.mean(np.abs(values - np.mean(values))),
            np.sum(values), np.sum(values**2),
            np.max(values) / (np.min(values) + 1e-8)
        ])
    return features  # Statistical features
```

### 2. `mqtt-ingestion/app/mqtt_client.py`
**Changes:**
- Fixed `_extract_24_features_from_data()` sensor ordering
- Added `_extract_statistical_features_from_window()` method
- Modified prediction logic to use statistical features instead of raw flattening
- Added numpy import

**Before (raw flattening):**
```python
# Flatten window: 14 timesteps × 24 features = 336 features
features = []
for timestep_features in self.sensor_windows[sensor_id]:
    features.extend(timestep_features)
```

**After (statistical features):**
```python
# Extract statistical features: 24 sensors × 14 stats = 336 features
features = self._extract_statistical_features_from_window(self.sensor_windows[sensor_id])
```

**Sensor Ordering Fix:**
```python
# OLD (Wrong order - grouped by feature type)
def _extract_24_features_from_data(self, data: dict):
    features = []
    # Motor DE vibration bands (4)
    for i in range(1, 5):
        features.append(data.get(f"motor_DE_vib_band_{i}", 0.0))
    # Motor NDE vibration bands (4)
    for i in range(1, 5):
        features.append(data.get(f"motor_NDE_vib_band_{i}", 0.0))
    # Motor ultrasonic (2)
    features.append(data.get("motor_DE_ultra_db", 0.0))
    features.append(data.get("motor_NDE_ultra_db", 0.0))
    # ... etc

# NEW (Correct order - grouped by sensor location)
def _extract_24_features_from_data(self, data: dict):
    features = []
    # Motor DE: vib_band_1-4, ultra_db, temp_c (6 features)
    for i in range(1, 5):
        features.append(data.get(f"motor_DE_vib_band_{i}", 0.0))
    features.append(data.get("motor_DE_ultra_db", 0.0))
    features.append(data.get("motor_DE_temp_c", 0.0))
    
    # Motor NDE: vib_band_1-4, ultra_db, temp_c (6 features)
    for i in range(1, 5):
        features.append(data.get(f"motor_NDE_vib_band_{i}", 0.0))
    features.append(data.get("motor_NDE_ultra_db", 0.0))
    features.append(data.get("motor_NDE_temp_c", 0.0))
    # ... etc
```

## Test Results

### Before Fix
```
Overall Accuracy: 1/16 (6.2%)
electrical_fluting → bearing_fit_loose_housing (FAIL)
cooling_failure → bearing_fit_loose_housing (FAIL)
```

### After Fix (Test Script)
```
Overall Accuracy: 12/16 (75%)
electrical_fluting → electrical_fluting (95.6% confidence) ✅
cooling_failure → cooling_failure (72.8% confidence) ✅
```

### After Fix (Live MQTT System)
```
electrical_fluting → electrical_fluting (96% confidence) ✅
cooling_failure → cooling_failure (82% confidence) ✅
```

## Key Learnings

1. **Feature Engineering Matters**: The model was trained on statistical features, not raw values. The live system must match training data format exactly.

2. **Column Ordering is Critical**: Even with correct feature types, wrong ordering causes complete failure. Feature position matters as much as feature value.

3. **Notebook Code is Truth**: The working notebook revealed the correct implementation. When system behavior doesn't match expected results, compare with training code.

4. **Test with Multiple Patterns**: Testing electrical_fluting revealed the ordering issue that cooling_failure alone didn't show clearly.

5. **Statistical Features > Raw Values**: For time-series anomaly detection, statistical aggregates (mean, std, etc.) provide better signal than raw timestep values.

## Validation Steps

1. **Test Script Validation**:
   ```bash
   python test_all_anomalies.py
   ```
   Result: 75% accuracy (12/16 patterns correct)

2. **Live MQTT Validation**:
   ```bash
   python test_electrical_fluting_live.py
   python test_cooling_failure_live.py
   ```
   Result: Both predict correctly with >80% confidence

3. **Feature Comparison**:
   ```bash
   python debug_features.py
   ```
   Result: Features now match between test script and MQTT client

## Next Steps

1. ✅ Test script predictions working
2. ✅ Live MQTT system predictions working
3. ✅ Sensor ordering fixed
4. ✅ Statistical feature extraction implemented
5. ⬜ Test remaining 4 failing patterns (bearing issues, belt_slip, phase_unbalance)
6. ⬜ Consider model retraining if certain patterns continue to fail
7. ⬜ Document feature extraction process for future reference

## Files for Reference

- `test_all_anomalies.py` - Comprehensive test suite
- `mqtt-ingestion/app/mqtt_client.py` - Live system feature extraction
- `Industrial_Anomaly_Prediction_XGBoost_KFold_WithFeedback_1.ipynb` - Training notebook
- `debug_features.py` - Feature comparison tool
- Anomaly files: `c:\Users\mahmo\Desktop\assetReli\anomalies\`
