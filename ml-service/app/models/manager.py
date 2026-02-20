"""
ModelManager — loads/serves a single XGBoost model. Relocated from model.py.
"""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import xgboost as xgb

logger = logging.getLogger(__name__)


class ModelManager:
    def __init__(self, model_dir: str, current_model_dir: str):
        self.model_dir = Path(model_dir)
        self.current_model_dir = Path(current_model_dir)

        self.model = None
        self.label_encoder = None
        self.scaler = None
        self.current_version = None
        self.metadata: Dict = {}

    def load_current_model(self) -> bool:
        try:
            model_path = self.current_model_dir / "xgboost_anomaly_detector.json"
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")

            self.model = xgb.XGBClassifier()
            self.model.load_model(str(model_path))
            logger.info(f"Loaded XGBoost model from {model_path}")

            encoder_path = self.current_model_dir / "label_encoder.pkl"
            if not encoder_path.exists():
                raise FileNotFoundError(f"Label encoder not found: {encoder_path}")
            with open(encoder_path, "rb") as f:
                self.label_encoder = pickle.load(f)
            logger.info(f"Loaded label encoder ({len(self.label_encoder.classes_)} classes)")

            scaler_path = self.current_model_dir / "feature_scaler.pkl"
            if not scaler_path.exists():
                raise FileNotFoundError(f"Scaler not found: {scaler_path}")
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
            logger.info("Loaded feature scaler")

            metadata_path = self.current_model_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    self.metadata = json.load(f)
                    self.current_version = self.metadata.get("version", "v1")
            else:
                self.current_version = "v1"
                self.metadata = {
                    "version": "v1",
                    "created_at": datetime.utcnow().isoformat(),
                    "num_classes": len(self.label_encoder.classes_),
                }

            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def predict(self, features: List[float], top_k: int = 3) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model not loaded.")

        features_array = np.array(features).reshape(1, -1)
        features_scaled = self.scaler.transform(features_array)
        prediction = self.model.predict(features_scaled)[0]
        probabilities = self.model.predict_proba(features_scaled)[0]

        top_k_indices = np.argsort(probabilities)[-top_k:][::-1]
        top_k_labels = [self.label_encoder.classes_[i] for i in top_k_indices]
        top_k_probs = [float(probabilities[i]) for i in top_k_indices]

        return {
            "prediction": self.label_encoder.classes_[prediction],
            "confidence": float(probabilities[prediction]),
            "top_predictions": [
                {"label": label, "confidence": prob}
                for label, prob in zip(top_k_labels, top_k_probs)
            ],
        }

    def get_current_version(self) -> str:
        return self.current_version or "unknown"

    def list_versions(self) -> List[Dict[str, Any]]:
        versions = []
        if self.current_version:
            versions.append(
                {
                    "version": self.current_version,
                    "created_at": self.metadata.get("created_at"),
                    "num_classes": len(self.label_encoder.classes_) if self.label_encoder else 0,
                    "metrics": self.metadata.get("metrics"),
                    "training_samples": self.metadata.get("training_samples"),
                    "feedback_samples": self.metadata.get("feedback_samples"),
                    "is_active": True,
                }
            )

        versions_dir = self.model_dir / "versions"
        if versions_dir.exists():
            for version_dir in sorted(versions_dir.iterdir()):
                if version_dir.is_dir():
                    metadata_path = version_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, "r") as f:
                            meta = json.load(f)
                            versions.append(
                                {
                                    "version": meta.get("version"),
                                    "created_at": meta.get("created_at"),
                                    "num_classes": meta.get("num_classes"),
                                    "metrics": meta.get("metrics"),
                                    "training_samples": meta.get("training_samples"),
                                    "feedback_samples": meta.get("feedback_samples"),
                                    "is_active": False,
                                }
                            )
        return versions

    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        for v in self.list_versions():
            if v["version"] == version:
                return v
        return None

    def activate_version(self, version: str) -> bool:
        try:
            import shutil

            version_dir = self.model_dir / "versions" / version
            if not version_dir.exists():
                logger.error(f"Version {version} not found")
                return False

            backup_dir = self.model_dir / "versions" / self.current_version
            backup_dir.mkdir(parents=True, exist_ok=True)

            for fname in [
                "xgboost_anomaly_detector.json",
                "label_encoder.pkl",
                "feature_scaler.pkl",
                "metadata.json",
            ]:
                src = self.current_model_dir / fname
                if src.exists():
                    shutil.copy(src, backup_dir / fname)

            for fname in [
                "xgboost_anomaly_detector.json",
                "label_encoder.pkl",
                "feature_scaler.pkl",
                "metadata.json",
            ]:
                src = version_dir / fname
                if src.exists():
                    shutil.copy(src, self.current_model_dir / fname)

            self.load_current_model()
            logger.info(f"Activated version {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to activate version {version}: {e}")
            return False

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "version": self.current_version,
            "num_classes": len(self.label_encoder.classes_) if self.label_encoder else 0,
            "metrics": self.metadata.get("metrics", {}),
            "training_samples": self.metadata.get("training_samples"),
            "feedback_samples": self.metadata.get("feedback_samples", 0),
        }

    def save_new_version(
        self,
        version: str,
        model: Any,
        label_encoder: Any,
        scaler: Any,
        metrics: Dict[str, float],
        training_samples: int,
        feedback_samples: int,
    ) -> bool:
        try:
            version_dir = self.model_dir / "versions" / version
            version_dir.mkdir(parents=True, exist_ok=True)

            model.save_model(str(version_dir / "xgboost_anomaly_detector.json"))
            with open(version_dir / "label_encoder.pkl", "wb") as f:
                pickle.dump(label_encoder, f)
            with open(version_dir / "feature_scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)

            metadata = {
                "version": version,
                "created_at": datetime.utcnow().isoformat(),
                "num_classes": len(label_encoder.classes_),
                "metrics": metrics,
                "training_samples": training_samples,
                "feedback_samples": feedback_samples,
            }
            with open(version_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Saved new version {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to save version {version}: {e}")
            return False
