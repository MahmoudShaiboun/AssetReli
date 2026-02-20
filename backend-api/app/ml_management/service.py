import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MLModel,
    MLModelVersion,
    MLModelDeployment,
    Feedback,
    User,
)
from app.ml_management.schemas import (
    MLModelOut,
    MLModelVersionOut,
    DeploymentOut,
    FeedbackStatsOut,
)

logger = logging.getLogger(__name__)


async def list_models(session: AsyncSession, tenant_id: UUID) -> list[MLModelOut]:
    result = await session.execute(
        select(MLModel).where(
            MLModel.tenant_id == tenant_id,
            MLModel.is_deleted == False,
        ).order_by(MLModel.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        MLModelOut(
            id=r.id,
            model_name=r.model_name,
            model_type=r.model_type,
            description=r.model_description,
            is_active=r.is_active,
        )
        for r in rows
    ]


async def get_model(session: AsyncSession, tenant_id: UUID, model_id: UUID) -> MLModelOut | None:
    result = await session.execute(
        select(MLModel).where(
            MLModel.id == model_id,
            MLModel.tenant_id == tenant_id,
            MLModel.is_deleted == False,
        )
    )
    r = result.scalar_one_or_none()
    if r is None:
        return None
    return MLModelOut(
        id=r.id,
        model_name=r.model_name,
        model_type=r.model_type,
        description=r.model_description,
        is_active=r.is_active,
    )


async def list_model_versions(
    session: AsyncSession, tenant_id: UUID, model_id: UUID
) -> list[MLModelVersionOut]:
    result = await session.execute(
        select(MLModelVersion).where(
            MLModelVersion.model_id == model_id,
            MLModelVersion.tenant_id == tenant_id,
            MLModelVersion.is_deleted == False,
        ).order_by(MLModelVersion.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        MLModelVersionOut(
            id=r.id,
            version=r.semantic_version,
            stage=r.stage,
            accuracy=r.accuracy,
            f1_score=r.f1_score,
            training_date=r.created_at,
        )
        for r in rows
    ]


async def list_deployments(session: AsyncSession, tenant_id: UUID) -> list[DeploymentOut]:
    result = await session.execute(
        select(
            MLModelDeployment,
            MLModel.model_name,
            MLModelVersion.full_version_label,
            User.username,
        )
        .join(MLModel, MLModelDeployment.model_id == MLModel.id)
        .join(MLModelVersion, MLModelDeployment.model_version_id == MLModelVersion.id)
        .outerjoin(User, MLModelDeployment.created_by == User.id)
        .where(MLModelDeployment.tenant_id == tenant_id)
        .order_by(MLModelDeployment.created_at.desc())
    )
    rows = result.all()
    return [
        DeploymentOut(
            id=dep.id,
            model_name=model_name,
            version_label=version_label,
            is_production=dep.is_production,
            deployed_at=dep.deployment_start,
            deployed_by=username or "system",
        )
        for dep, model_name, version_label, username in rows
    ]


async def get_feedback_stats(session: AsyncSession, tenant_id: UUID) -> FeedbackStatsOut:
    # Total count
    total_result = await session.execute(
        select(func.count(Feedback.id)).where(Feedback.tenant_id == tenant_id)
    )
    total = total_result.scalar() or 0

    # Breakdown by feedback_type
    breakdown_result = await session.execute(
        select(Feedback.feedback_type, func.count(Feedback.id))
        .where(Feedback.tenant_id == tenant_id)
        .group_by(Feedback.feedback_type)
    )
    breakdown = {row[0]: row[1] for row in breakdown_result.all()}

    return FeedbackStatsOut(total_count=total, breakdown=breakdown)
