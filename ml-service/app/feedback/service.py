"""
FeedbackService — stores user feedback in PostgreSQL.
"""

import logging
import uuid as uuid_mod
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Feedback

logger = logging.getLogger(__name__)

# Default tenant/user IDs for backward compatibility (single-tenant mode).
# Phase 3 will pass real tenant/user context.
_DEFAULT_TENANT_ID = None  # Set by seed data
_DEFAULT_USER_ID = None


class FeedbackService:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory

    async def store_feedback(
        self,
        features: list,
        original_prediction: str,
        corrected_label: str,
        feedback_type: str,
        confidence: float = None,
        notes: str = None,
        tenant_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        asset_id: Optional[UUID] = None,
        sensor_id: Optional[UUID] = None,
        prediction_id: Optional[str] = None,
    ) -> str:
        feedback_id = uuid_mod.uuid4()

        async with self.session_factory() as session:
            # Resolve tenant_id: use provided or look up default
            if tenant_id is None:
                tenant_id = await self._get_default_tenant_id(session)
            if created_by is None:
                created_by = await self._get_default_user_id(session)

            fb = Feedback(
                id=feedback_id,
                tenant_id=tenant_id,
                asset_id=asset_id,
                sensor_id=sensor_id,
                prediction_id=prediction_id,
                prediction_label=original_prediction,
                probability=confidence,
                new_label=corrected_label,
                correction=notes,
                feedback_type=feedback_type,
                payload_normalized=features,
                created_by=created_by,
            )
            session.add(fb)
            await session.commit()

        logger.info(f"Stored feedback: {feedback_id}")
        return str(feedback_id)

    async def get_feedback_count(self, tenant_id: Optional[UUID] = None) -> int:
        async with self.session_factory() as session:
            stmt = select(func.count(Feedback.id))
            if tenant_id:
                stmt = stmt.where(Feedback.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def get_feedback_stats(self, tenant_id: Optional[UUID] = None) -> dict:
        async with self.session_factory() as session:
            base = select(Feedback)
            if tenant_id:
                base = base.where(Feedback.tenant_id == tenant_id)

            total = await session.execute(
                select(func.count(Feedback.id)).select_from(base.subquery())
            )
            corrections = await session.execute(
                select(func.count(Feedback.id)).where(
                    Feedback.feedback_type == "correction",
                    *([Feedback.tenant_id == tenant_id] if tenant_id else []),
                )
            )
            new_faults = await session.execute(
                select(func.count(Feedback.id)).where(
                    Feedback.feedback_type == "new_fault",
                    *([Feedback.tenant_id == tenant_id] if tenant_id else []),
                )
            )
            false_positives = await session.execute(
                select(func.count(Feedback.id)).where(
                    Feedback.feedback_type == "false_positive",
                    *([Feedback.tenant_id == tenant_id] if tenant_id else []),
                )
            )

            return {
                "total": total.scalar() or 0,
                "corrections": corrections.scalar() or 0,
                "new_faults": new_faults.scalar() or 0,
                "false_positives": false_positives.scalar() or 0,
            }

    async def get_feedback_for_retraining(
        self, tenant_id: Optional[UUID] = None
    ) -> dict:
        """Load all feedback features and labels for retraining."""
        async with self.session_factory() as session:
            stmt = select(Feedback)
            if tenant_id:
                stmt = stmt.where(Feedback.tenant_id == tenant_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            features = []
            labels = []
            for row in rows:
                if row.payload_normalized:
                    features.append(row.payload_normalized)
                    labels.append(row.new_label)

            return {"features": features, "labels": labels, "count": len(features)}

    async def _get_default_tenant_id(self, session) -> UUID:
        global _DEFAULT_TENANT_ID
        if _DEFAULT_TENANT_ID is None:
            from app.db.models import Tenant
            result = await session.execute(
                select(Tenant.id).where(
                    Tenant.tenant_code == "default",
                    Tenant.is_deleted == False,
                ).limit(1)
            )
            tid = result.scalar_one_or_none()
            if tid:
                _DEFAULT_TENANT_ID = tid
            else:
                raise RuntimeError("No default tenant found. Run seed migration first.")
        return _DEFAULT_TENANT_ID

    async def _get_default_user_id(self, session) -> UUID:
        global _DEFAULT_USER_ID
        if _DEFAULT_USER_ID is None:
            from app.db.models import Tenant
            from sqlalchemy import text
            # Get first user in default tenant
            result = await session.execute(
                text(
                    "SELECT id FROM users WHERE tenant_id = "
                    "(SELECT id FROM tenants WHERE tenant_code = 'default' LIMIT 1) "
                    "LIMIT 1"
                )
            )
            uid = result.scalar_one_or_none()
            if uid:
                _DEFAULT_USER_ID = uid
            else:
                # Use the tenant_id as a fallback (will be replaced in Phase 3)
                _DEFAULT_USER_ID = await self._get_default_tenant_id(session)
        return _DEFAULT_USER_ID
