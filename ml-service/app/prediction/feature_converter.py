"""
Convert structured sensor data to a 336-feature array.
"""

from app.prediction.schemas import PredictionRequest


def convert_structured_to_features(request: PredictionRequest) -> list[float]:
    """
    If features array is provided, use it directly.
    Otherwise, construct from structured sensor fields.
    """
    if request.features and len(request.features) > 0:
        return request.features

    features = [
        request.motor_DE_vib_band_1 or 0.0,
        request.motor_DE_vib_band_2 or 0.0,
        request.motor_DE_vib_band_3 or 0.0,
        request.motor_DE_vib_band_4 or 0.0,
        request.motor_NDE_vib_band_1 or 0.0,
        request.motor_NDE_vib_band_2 or 0.0,
        request.motor_NDE_vib_band_3 or 0.0,
        request.motor_NDE_vib_band_4 or 0.0,
        request.motor_DE_ultra_db or 0.0,
        request.motor_NDE_ultra_db or 0.0,
        request.motor_DE_temp_c or 0.0,
        request.motor_NDE_temp_c or 0.0,
        request.pump_DE_vib_band_1 or 0.0,
        request.pump_DE_vib_band_2 or 0.0,
        request.pump_DE_vib_band_3 or 0.0,
        request.pump_DE_vib_band_4 or 0.0,
        request.pump_NDE_vib_band_1 or 0.0,
        request.pump_NDE_vib_band_2 or 0.0,
        request.pump_NDE_vib_band_3 or 0.0,
        request.pump_NDE_vib_band_4 or 0.0,
        request.pump_DE_ultra_db or 0.0,
        request.pump_NDE_ultra_db or 0.0,
        request.pump_DE_temp_c or 0.0,
        request.pump_NDE_temp_c or 0.0,
    ]

    # 24 * 14 = 336 features to match training structure
    features = features * 14
    return features
