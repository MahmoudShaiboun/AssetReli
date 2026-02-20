"""
RetrainingPipeline — training logic only.

Feedback is read from PostgreSQL via FeedbackService.
After retraining, version metadata is written to PG ml_model_versions.
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional
from uuid import UUID

import numpy as np
import xgboost as xgb
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight

from app.config import settings

logger = logging.getLogger(__name__)


class RetrainingPipeline:
    def __init__(self, model_manager, feedback_service, session_factory: async_sessionmaker):
        self.model_manager = model_manager
        self.feedback_service = feedback_service
        self.session_factory = session_factory

        # Concurrency guard: one retrain per (tenant_id, model_id)
        self._locks: dict[tuple, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def retrain_model(
        self,
        selected_data_ids: list = None,
        tenant_id: Optional[UUID] = None,
        model_id: Optional[UUID] = None,
    ) -> dict:
        """Retrain the model using feedback data from PostgreSQL."""
        lock_key = (str(tenant_id), str(model_id))
        lock = self._locks[lock_key]

        if lock.locked():
            return {
                "success": False,
                "message": "Retraining already in progress for this tenant/model",
                "status": "already_running",
            }

        async with lock:
            return await self._do_retrain(selected_data_ids, tenant_id, model_id)

    async def _do_retrain(
        self,
        selected_data_ids: list = None,
        tenant_id: Optional[UUID] = None,
        model_id: Optional[UUID] = None,
    ) -> dict:
        try:
            # Load feedback from PG (tenant-scoped if provided)
            feedback_data = await self.feedback_service.get_feedback_for_retraining(
                tenant_id=tenant_id
            )

            if feedback_data["count"] == 0:
                return {"success": False, "message": "No feedback data available"}

            logger.info(
                f"Starting model retraining with {feedback_data['count']} feedback samples"
                f"{f' for tenant {tenant_id}' if tenant_id else ''}..."
            )

            feedback_features = np.array(feedback_data["features"])
            feedback_labels = feedback_data["labels"]

            # Detect new fault classes
            original_classes = set(self.model_manager.label_encoder.classes_)
            feedback_classes = set(feedback_labels)
            new_classes = feedback_classes - original_classes

            if new_classes:
                logger.info(f"New fault types detected: {new_classes}")
                all_classes = sorted(list(original_classes | feedback_classes))
                label_encoder = LabelEncoder()
                label_encoder.classes_ = np.array(all_classes)
            else:
                label_encoder = self.model_manager.label_encoder

            feedback_y = label_encoder.transform(feedback_labels)

            # 3C.9: Load original training data to prevent catastrophic forgetting
            original_features, original_labels = self._load_original_training_data(
                label_encoder
            )

            if original_features is not None and settings.INCLUDE_ORIGINAL_DATA_ON_RETRAIN:
                original_y = label_encoder.transform(original_labels)

                # Weight feedback samples higher (FEEDBACK_WEIGHT_MULTIPLIER)
                multiplier = max(1, int(settings.FEEDBACK_WEIGHT_MULTIPLIER))
                if multiplier > 1:
                    feedback_features_weighted = np.repeat(
                        feedback_features, multiplier, axis=0
                    )
                    feedback_y_weighted = np.repeat(feedback_y, multiplier)
                else:
                    feedback_features_weighted = feedback_features
                    feedback_y_weighted = feedback_y

                # Merge original + weighted feedback
                all_features = np.vstack([original_features, feedback_features_weighted])
                all_y = np.concatenate([original_y, feedback_y_weighted])
                logger.info(
                    f"Merged {len(original_features)} original + "
                    f"{len(feedback_features_weighted)} weighted feedback samples "
                    f"(multiplier={multiplier})"
                )
            else:
                all_features = feedback_features
                all_y = feedback_y
                if settings.INCLUDE_ORIGINAL_DATA_ON_RETRAIN:
                    logger.warning(
                        "Original training data not found, training on feedback only"
                    )

            X_train, X_val, y_train, y_val = train_test_split(
                all_features,
                all_y,
                test_size=0.2,
                random_state=42,
                stratify=all_y if len(np.unique(all_y)) > 1 else None,
            )

            # Fit a new scaler on the training data (3C.10)
            new_scaler = StandardScaler()
            X_train = new_scaler.fit_transform(X_train)
            X_val = new_scaler.transform(X_val)

            class_weights = compute_class_weight(
                "balanced", classes=np.unique(y_train), y=y_train
            )
            sample_weights = np.array([class_weights[y] for y in y_train])

            new_model = xgb.XGBClassifier(
                objective="multi:softprob",
                num_class=len(label_encoder.classes_),
                max_depth=settings.XGBOOST_MAX_DEPTH,
                learning_rate=settings.XGBOOST_LEARNING_RATE,
                n_estimators=settings.XGBOOST_N_ESTIMATORS,
                subsample=settings.XGBOOST_SUBSAMPLE,
                colsample_bytree=settings.XGBOOST_COLSAMPLE_BYTREE,
                random_state=42,
            )

            training_start = datetime.utcnow()
            new_model.fit(
                X_train,
                y_train,
                sample_weight=sample_weights,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
            training_end = datetime.utcnow()

            y_val_pred = new_model.predict(X_val)
            metrics = {
                "accuracy": float(accuracy_score(y_val, y_val_pred)),
                "balanced_accuracy": float(balanced_accuracy_score(y_val, y_val_pred)),
                "f1_score": float(f1_score(y_val, y_val_pred, average="weighted")),
            }

            # Determine version number from PG
            new_version, semantic_version = await self._next_version(tenant_id)

            self.model_manager.save_new_version(
                version=new_version,
                model=new_model,
                label_encoder=label_encoder,
                scaler=new_scaler,
                metrics=metrics,
                training_samples=len(X_train),
                feedback_samples=feedback_data["count"],
            )

            # Write version metadata to PG
            await self._write_version_to_pg(
                version_label=new_version,
                semantic_version=semantic_version,
                metrics=metrics,
                training_start=training_start,
                training_end=training_end,
                feedback_samples=feedback_data["count"],
                tenant_id=tenant_id,
                model_id=model_id,
            )

            logger.info(
                f"Retrained model {new_version}: "
                f"acc={metrics['accuracy']:.4f}, "
                f"bal_acc={metrics['balanced_accuracy']:.4f}, "
                f"f1={metrics['f1_score']:.4f}"
            )

            return {
                "success": True,
                "message": "Model retrained successfully",
                "version": new_version,
                "metrics": metrics,
            }

        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            return {"success": False, "message": f"Retraining failed: {str(e)}"}

    def _load_original_training_data(
        self, label_encoder: LabelEncoder
    ) -> tuple[Optional[np.ndarray], Optional[list]]:
        """Load original training data from the current model's artifact directory.

        Looks for training_data.npz (features + labels) saved alongside the model.
        Returns (features, labels) or (None, None) if not available.
        """
        try:
            from pathlib import Path

            model_dir = Path(self.model_manager.current_model_dir)
            data_path = model_dir / "training_data.npz"
            if data_path.exists():
                data = np.load(data_path, allow_pickle=True)
                features = data["features"]
                labels = list(data["labels"])

                # Filter to labels that exist in the current label_encoder
                valid_labels = set(label_encoder.classes_)
                mask = [l in valid_labels for l in labels]
                features = features[mask]
                labels = [l for l, m in zip(labels, mask) if m]

                logger.info(
                    f"Loaded {len(labels)} original training samples from {data_path}"
                )
                return features, labels

            # Also try CSV format
            csv_path = model_dir / "training_data.csv"
            if csv_path.exists():
                import csv

                features_list = []
                labels = []
                with open(csv_path, "r") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    for row in reader:
                        labels.append(row[-1])
                        features_list.append([float(x) for x in row[:-1]])

                valid_labels = set(label_encoder.classes_)
                filtered_features = []
                filtered_labels = []
                for feat, lab in zip(features_list, labels):
                    if lab in valid_labels:
                        filtered_features.append(feat)
                        filtered_labels.append(lab)

                if filtered_features:
                    logger.info(
                        f"Loaded {len(filtered_labels)} original training samples "
                        f"from {csv_path}"
                    )
                    return np.array(filtered_features), filtered_labels

            logger.info("No original training data found")
            return None, None
        except Exception:
            logger.exception("Error loading original training data")
            return None, None

    async def _next_version(self, tenant_id: Optional[UUID] = None) -> tuple[str, str]:
        """Determine next version number from PG ml_model_versions count."""
        from app.db.models import MLModelVersion

        async with self.session_factory() as session:
            stmt = select(func.count(MLModelVersion.id))
            if tenant_id:
                stmt = stmt.where(MLModelVersion.tenant_id == tenant_id)
            result = await session.execute(stmt)
            count = result.scalar() or 0
            version_num = count + 1
            return f"v{version_num}", f"1.0.{version_num}"

    async def _write_version_to_pg(
        self,
        version_label: str,
        semantic_version: str,
        metrics: dict,
        training_start: datetime,
        training_end: datetime,
        feedback_samples: int,
        tenant_id: Optional[UUID] = None,
        model_id: Optional[UUID] = None,
    ) -> None:
        """Write model version metadata to PostgreSQL."""
        from app.db.models import MLModel, MLModelVersion, Tenant

        async with self.session_factory() as session:
            # Resolve tenant
            if tenant_id is None:
                result = await session.execute(
                    select(Tenant.id).where(
                        Tenant.tenant_code == "default",
                        Tenant.is_deleted == False,
                    ).limit(1)
                )
                tenant_id = result.scalar_one_or_none()
                if not tenant_id:
                    logger.warning("No default tenant found, skipping PG version write")
                    return

            # Resolve model
            if model_id is None:
                result = await session.execute(
                    select(MLModel).where(
                        MLModel.tenant_id == tenant_id,
                        MLModel.model_name == "fault_classifier",
                        MLModel.is_deleted == False,
                    )
                )
                model = result.scalar_one_or_none()
                if not model:
                    logger.warning("No fault_classifier model found in PG")
                    return
                model_id = model.id

            full_label = f"fault_classifier:{semantic_version}"

            version = MLModelVersion(
                tenant_id=tenant_id,
                model_id=model_id,
                semantic_version=semantic_version,
                full_version_label=full_label,
                stage="staging",
                model_artifact_path=f"models/versions/{version_label}",
                training_start=training_start,
                training_end=training_end,
                accuracy=metrics.get("accuracy"),
                f1_score=metrics.get("f1_score"),
            )
            session.add(version)
            await session.commit()

            logger.info(f"Wrote version {full_label} to PG (stage=staging)")
