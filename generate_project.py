#!/usr/bin/env python3
"""
Complete project generator for Aastreli microservices
"""
import os
from pathlib import Path

def write_file(filepath, content):
    """Write content to file"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content.strip() + '\n')
    print(f"✅ {filepath}")

# ============================================================================
# ML SERVICE FILES
# ============================================================================

ML_RETRAIN = '''
import pickle
import numpy as np
import xgboost as xgb
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from datetime import datetime
import json
import logging
import uuid

logger = logging.getLogger(__name__)


class RetrainingPipeline:
    """Handles model retraining with feedback data"""
    
    def __init__(self, model_manager, feedback_dir: str):
        self.model_manager = model_manager
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.feedback_dir / "feedback_data.pkl"
        self.feedback_log = self.feedback_dir / "feedback_log.json"
        
        # Initialize feedback storage
        self._load_or_initialize_feedback()
    
    def _load_or_initialize_feedback(self):
        """Load or initialize feedback storage"""
        if self.feedback_file.exists():
            with open(self.feedback_file, 'rb') as f:
                self.feedback_storage = pickle.load(f)
            logger.info(f"Loaded {len(self.feedback_storage['features'])} feedback samples")
        else:
            self.feedback_storage = {
                'features': [],
                'original_predictions': [],
                'corrected_labels': [],
                'feedback_types': [],
                'timestamps': [],
                'confidences': [],
                'notes': [],
                'feedback_ids': []
            }
            logger.info("Initialized new feedback storage")
        
        if self.feedback_log.exists():
            with open(self.feedback_log, 'r') as f:
                self.feedback_log_data = json.load(f)
        else:
            self.feedback_log_data = {
                'total': 0,
                'corrections': 0,
                'new_faults': 0,
                'false_positives': 0,
                'retraining_history': []
            }
    
    def store_feedback(
        self,
        features: list,
        original_prediction: str,
        corrected_label: str,
        feedback_type: str,
        confidence: float = None,
        notes: str = None
    ) -> str:
        """Store feedback for retraining"""
        feedback_id = f"fb_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        self.feedback_storage['features'].append(features)
        self.feedback_storage['original_predictions'].append(original_prediction)
        self.feedback_storage['corrected_labels'].append(corrected_label)
        self.feedback_storage['feedback_types'].append(feedback_type)
        self.feedback_storage['timestamps'].append(datetime.utcnow().isoformat())
        self.feedback_storage['confidences'].append(confidence)
        self.feedback_storage['notes'].append(notes)
        self.feedback_storage['feedback_ids'].append(feedback_id)
        
        # Update log
        self.feedback_log_data['total'] += 1
        if feedback_type == 'correction':
            self.feedback_log_data['corrections'] += 1
        elif feedback_type == 'new_fault':
            self.feedback_log_data['new_faults'] += 1
        elif feedback_type == 'false_positive':
            self.feedback_log_data['false_positives'] += 1
        
        # Save to disk
        with open(self.feedback_file, 'wb') as f:
            pickle.dump(self.feedback_storage, f)
        
        with open(self.feedback_log, 'w') as f:
            json.dump(self.feedback_log_data, f, indent=2)
        
        logger.info(f"Stored feedback: {feedback_id}")
        return feedback_id
    
    def get_feedback_count(self) -> int:
        """Get total feedback count"""
        return len(self.feedback_storage['features'])
    
    def get_feedback_stats(self) -> dict:
        """Get feedback statistics"""
        return {
            'total': self.feedback_log_data['total'],
            'corrections': self.feedback_log_data['corrections'],
            'new_faults': self.feedback_log_data['new_faults'],
            'false_positives': self.feedback_log_data['false_positives'],
            'retraining_count': len(self.feedback_log_data['retraining_history'])
        }
    
    def retrain_model(self, selected_data_ids: list = None) -> dict:
        """Retrain model with feedback data"""
        try:
            if len(self.feedback_storage['features']) == 0:
                return {'success': False, 'message': 'No feedback data available'}
            
            logger.info("🔄 Starting model retraining...")
            
            # Load original training data (stub - in production load from database)
            # For now, we'll just use feedback data
            feedback_features = np.array(self.feedback_storage['features'])
            feedback_labels = self.feedback_storage['corrected_labels']
            
            # Check for new classes
            original_classes = set(self.model_manager.label_encoder.classes_)
            feedback_classes = set(feedback_labels)
            new_classes = feedback_classes - original_classes
            
            if new_classes:
                logger.info(f"🆕 New fault types: {new_classes}")
                # Update label encoder
                all_classes = sorted(list(original_classes | feedback_classes))
                from sklearn.preprocessing import LabelEncoder
                new_encoder = LabelEncoder()
                new_encoder.classes_ = np.array(all_classes)
                label_encoder = new_encoder
            else:
                label_encoder = self.model_manager.label_encoder
            
            # Encode labels
            feedback_y = label_encoder.transform(feedback_labels)
            
            # Split for validation
            X_train, X_val, y_train, y_val = train_test_split(
                feedback_features, feedback_y,
                test_size=0.2,
                random_state=42,
                stratify=feedback_y if len(np.unique(feedback_y)) > 1 else None
            )
            
            # Class weights
            class_weights = compute_class_weight(
                'balanced',
                classes=np.unique(y_train),
                y=y_train
            )
            sample_weights = np.array([class_weights[y] for y in y_train])
            
            # Train model
            from .config import settings
            new_model = xgb.XGBClassifier(
                objective='multi:softprob',
                num_class=len(label_encoder.classes_),
                max_depth=settings.XGBOOST_MAX_DEPTH,
                learning_rate=settings.XGBOOST_LEARNING_RATE,
                n_estimators=settings.XGBOOST_N_ESTIMATORS,
                subsample=settings.XGBOOST_SUBSAMPLE,
                colsample_bytree=settings.XGBOOST_COLSAMPLE_BYTREE,
                random_state=42
            )
            
            new_model.fit(
                X_train, y_train,
                sample_weight=sample_weights,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
            
            # Evaluate
            y_val_pred = new_model.predict(X_val)
            val_acc = accuracy_score(y_val, y_val_pred)
            val_bal_acc = balanced_accuracy_score(y_val, y_val_pred)
            val_f1 = f1_score(y_val, y_val_pred, average='weighted')
            
            metrics = {
                'accuracy': float(val_acc),
                'balanced_accuracy': float(val_bal_acc),
                'f1_score': float(val_f1)
            }
            
            # Generate new version
            version_num = len(self.feedback_log_data['retraining_history']) + 2
            new_version = f"v{version_num}"
            
            # Save new version
            self.model_manager.save_new_version(
                version=new_version,
                model=new_model,
                label_encoder=label_encoder,
                scaler=self.model_manager.scaler,
                metrics=metrics,
                training_samples=len(X_train),
                feedback_samples=len(self.feedback_storage['features'])
            )
            
            # Update log
            self.feedback_log_data['retraining_history'].append({
                'version': new_version,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': metrics,
                'feedback_samples': len(self.feedback_storage['features'])
            })
            
            with open(self.feedback_log, 'w') as f:
                json.dump(self.feedback_log_data, f, indent=2)
            
            logger.info(f"✅ Retrained model: {new_version}")
            logger.info(f"   Accuracy: {val_acc:.4f}")
            logger.info(f"   Balanced Acc: {val_bal_acc:.4f}")
            logger.info(f"   F1 Score: {val_f1:.4f}")
            
            return {
                'success': True,
                'message': 'Model retrained successfully',
                'version': new_version,
                'metrics': metrics
            }
        
        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            return {
                'success': False,
                'message': f'Retraining failed: {str(e)}'
            }
'''

ML_REQUIREMENTS = '''
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
xgboost==2.0.3
scikit-learn==1.4.0
numpy==1.26.3
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
pymongo==4.6.1
motor==3.3.2
'''

ML_DOCKERFILE = '''
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ app/
COPY models/ models/

# Create directories
RUN mkdir -p /app/feedback_data /app/models/current /app/models/versions

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
'''

print("Generating ML Service files...")
write_file("ml-service/app/retrain.py", ML_RETRAIN)
write_file("ml-service/requirements.txt", ML_REQUIREMENTS)
write_file("ml-service/Dockerfile", ML_DOCKERFILE)
write_file("ml-service/.dockerignore", "__pycache__\n*.pyc\n.env\nvenv/\n.git/")

print("\n✅ ML Service files created!")
print("Run: python3 generate_project.py")

