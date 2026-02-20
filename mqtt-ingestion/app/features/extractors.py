"""
Feature extraction functions for sensor data.

extract_24_features_from_data: Extracts 24 base features from a raw MQTT payload.
extract_statistical_features_from_window: Computes 336 statistical features from a
    sliding window of 14 timesteps x 24 sensors.

NOTE: The old _extract_features_from_complex_data (which used random.uniform) has been
intentionally deleted — it produced non-deterministic features and was issue A7.
"""

from typing import List

import numpy as np


def extract_24_features_from_data(data: dict) -> List[float]:
    """
    Extract 24 base features from sensor data (for sliding window).

    Order MUST match notebook's SENSOR_COLUMNS:
    1. Motor DE: vib_band_1-4, ultra_db, temp_c
    2. Motor NDE: vib_band_1-4, ultra_db, temp_c
    3. Pump DE: vib_band_1-4, ultra_db, temp_c
    4. Pump NDE: vib_band_1-4, ultra_db, temp_c
    """
    features: List[float] = []

    for location in ("motor_DE", "motor_NDE", "pump_DE", "pump_NDE"):
        for i in range(1, 5):
            features.append(data.get(f"{location}_vib_band_{i}", 0.0))
        features.append(data.get(f"{location}_ultra_db", 0.0))
        features.append(data.get(f"{location}_temp_c", 0.0))

    return features  # 24 features


def extract_statistical_features_from_window(
    window: List[List[float]],
) -> List[float]:
    """
    Extract statistical features from sliding window — MATCHES NOTEBOOK EXACTLY.

    Args:
        window: List of 14 timesteps, each containing 24 sensor features.

    Returns:
        List of 336 features (24 sensors x 14 statistical features each).
    """
    features: List[float] = []

    window_array = np.array(window)  # Shape: (14, 24)

    for sensor_idx in range(24):
        values = window_array[:, sensor_idx]

        features.extend(
            [
                float(np.mean(values)),
                float(np.std(values)),
                float(np.min(values)),
                float(np.max(values)),
                float(np.median(values)),
                float(np.percentile(values, 25)),
                float(np.percentile(values, 75)),
                float(np.max(values) - np.min(values)),
                float(np.var(values)),
                float(np.sqrt(np.mean(values**2))),
                float(np.mean(np.abs(values - np.mean(values)))),
                float(np.sum(values)),
                float(np.sum(values**2)),
                float(np.max(values) / (np.min(values) + 1e-8)),
            ]
        )

    return features  # 336 features (24 x 14)
