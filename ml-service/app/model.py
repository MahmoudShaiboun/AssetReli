import pickle
import numpy as np
import xgboost as xgb
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages ML model loading, prediction, and versioning"""
    
    def __init__(self, model_dir: str, current_model_dir: str):
        self.model_dir = Path(model_dir)
        self.current_model_dir = Path(current_model_dir)
        
        self.model = None
        self.label_encoder = None
        self.scaler = None
        self.current_version = None
        self.metadata = {}
    
    def load_current_model(self):
        """Load the current active model"""
        try:
            # Load XGBoost model
            model_path = self.current_model_dir / "xgboost_anomaly_detector.json"
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(model_path))
            logger.info(f"✅ Loaded XGBoost model from {model_path}")
            
            # Load label encoder
            encoder_path = self.current_model_dir / "label_encoder.pkl"
            if not encoder_path.exists():
                raise FileNotFoundError(f"Label encoder not found: {encoder_path}")
            
            with open(encoder_path, 'rb') as f:
                self.label_encoder = pickle.load(f)
            logger.info(f"✅ Loaded label encoder ({len(self.label_encoder.classes_)} classes)")
            
            # Load scaler
            scaler_path = self.current_model_dir / "feature_scaler.pkl"
            if not scaler_path.exists():
                raise FileNotFoundError(f"Scaler not found: {scaler_path}")
            
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            logger.info(f"✅ Loaded feature scaler")
            
            # Load metadata if exists
            metadata_path = self.current_model_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                    self.current_version = self.metadata.get('version', 'v1')
            else:
                self.current_version = 'v1'
                self.metadata = {
                    'version': 'v1',
                    'created_at': datetime.utcnow().isoformat(),
                    'num_classes': len(self.label_encoder.classes_)
                }
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def predict(self, features: List[float], top_k: int = 3) -> Dict[str, Any]:
        """
        Make prediction from features.
        
        Args:
            features: Feature vector (list of floats)
            top_k: Number of top predictions to return
        
        Returns:
            Dictionary with prediction, confidence, and top_k predictions
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_current_model() first.")
        
        try:
            # Convert to numpy array and reshape
            features_array = np.array(features).reshape(1, -1)
            
            # Scale features
            features_scaled = self.scaler.transform(features_array)
            
            # Make prediction
            prediction = self.model.predict(features_scaled)[0]
            probabilities = self.model.predict_proba(features_scaled)[0]
            
            # Get top-K predictions
            top_k_indices = np.argsort(probabilities)[-top_k:][::-1]
            top_k_labels = [self.label_encoder.classes_[i] for i in top_k_indices]
            top_k_probs = [float(probabilities[i]) for i in top_k_indices]
            
            return {
                'prediction': self.label_encoder.classes_[prediction],
                'confidence': float(probabilities[prediction]),
                'top_predictions': [
                    {'label': label, 'confidence': prob}
                    for label, prob in zip(top_k_labels, top_k_probs)
                ]
            }
        
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise
    
    def get_current_version(self) -> str:
        """Get current model version"""
        return self.current_version or "unknown"
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """List all available model versions"""
        versions = []
        
        # Add current version
        if self.current_version:
            versions.append({
                'version': self.current_version,
                'created_at': self.metadata.get('created_at'),
                'num_classes': len(self.label_encoder.classes_) if self.label_encoder else 0,
                'metrics': self.metadata.get('metrics'),
                'training_samples': self.metadata.get('training_samples'),
                'feedback_samples': self.metadata.get('feedback_samples'),
                'is_active': True
            })
        
        # Add versions from versions directory
        versions_dir = self.model_dir / "versions"
        if versions_dir.exists():
            for version_dir in sorted(versions_dir.iterdir()):
                if version_dir.is_dir():
                    metadata_path = version_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            versions.append({
                                'version': metadata.get('version'),
                                'created_at': metadata.get('created_at'),
                                'num_classes': metadata.get('num_classes'),
                                'metrics': metadata.get('metrics'),
                                'training_samples': metadata.get('training_samples'),
                                'feedback_samples': metadata.get('feedback_samples'),
                                'is_active': False
                            })
        
        return versions
    
    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific version"""
        versions = self.list_versions()
        for v in versions:
            if v['version'] == version:
                return v
        return None
    
    def activate_version(self, version: str) -> bool:
        """Activate a specific model version"""
        try:
            version_dir = self.model_dir / "versions" / version
            if not version_dir.exists():
                logger.error(f"Version {version} not found")
                return False
            
            # Copy files to current directory
            import shutil
            
            # Backup current version
            backup_dir = self.model_dir / "versions" / self.current_version
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            for file in ['xgboost_anomaly_detector.json', 'label_encoder.pkl', 'feature_scaler.pkl', 'metadata.json']:
                src = self.current_model_dir / file
                if src.exists():
                    shutil.copy(src, backup_dir / file)
            
            # Copy new version to current
            for file in ['xgboost_anomaly_detector.json', 'label_encoder.pkl', 'feature_scaler.pkl', 'metadata.json']:
                src = version_dir / file
                if src.exists():
                    shutil.copy(src, self.current_model_dir / file)
            
            # Reload model
            self.load_current_model()
            
            logger.info(f"✅ Activated version {version}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to activate version {version}: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current model metrics"""
        return {
            'version': self.current_version,
            'num_classes': len(self.label_encoder.classes_) if self.label_encoder else 0,
            'metrics': self.metadata.get('metrics', {}),
            'training_samples': self.metadata.get('training_samples'),
            'feedback_samples': self.metadata.get('feedback_samples', 0)
        }
    
    def save_new_version(
        self,
        version: str,
        model: Any,
        label_encoder: Any,
        scaler: Any,
        metrics: Dict[str, float],
        training_samples: int,
        feedback_samples: int
    ):
        """Save a new model version"""
        try:
            version_dir = self.model_dir / "versions" / version
            version_dir.mkdir(parents=True, exist_ok=True)
            
            # Save model
            model.save_model(str(version_dir / "xgboost_anomaly_detector.json"))
            
            # Save encoder and scaler
            with open(version_dir / "label_encoder.pkl", 'wb') as f:
                pickle.dump(label_encoder, f)
            
            with open(version_dir / "feature_scaler.pkl", 'wb') as f:
                pickle.dump(scaler, f)
            
            # Save metadata
            metadata = {
                'version': version,
                'created_at': datetime.utcnow().isoformat(),
                'num_classes': len(label_encoder.classes_),
                'metrics': metrics,
                'training_samples': training_samples,
                'feedback_samples': feedback_samples
            }
            
            with open(version_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"✅ Saved new version {version}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to save version {version}: {e}")
            return False
