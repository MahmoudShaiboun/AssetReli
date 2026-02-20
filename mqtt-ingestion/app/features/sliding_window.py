import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SlidingWindowManager:
    """Manages per-sensor sliding window buffers for feature engineering."""

    def __init__(self, window_size: int = 14):
        self.window_size = window_size
        # Key: sensor_id (str) — Phase 3B changes to (tenant_id, asset_id, sensor_id)
        self._windows: Dict[str, List[List[float]]] = {}

    def add_reading(self, sensor_id: str, features: List[float]) -> Optional[List[List[float]]]:
        """
        Add a reading to the sensor's window buffer.

        Returns the full window (list of readings) if the buffer has reached
        window_size, otherwise returns None.
        """
        if sensor_id not in self._windows:
            self._windows[sensor_id] = []
            logger.info(f"Initialized sliding window for sensor: {sensor_id}")

        window = self._windows[sensor_id]
        window.append(features)

        # FIFO eviction
        if len(window) > self.window_size:
            window.pop(0)

        if len(window) >= self.window_size:
            return list(window)  # return a copy

        logger.info(
            f"Window building for {sensor_id}: {len(window)}/{self.window_size} readings"
        )
        return None

    def get_window(self, sensor_id: str) -> Optional[List[List[float]]]:
        window = self._windows.get(sensor_id)
        if window and len(window) >= self.window_size:
            return list(window)
        return None

    def clear(self, sensor_id: str) -> None:
        self._windows.pop(sensor_id, None)

    def clear_all(self) -> None:
        self._windows.clear()
