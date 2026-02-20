import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func


class AuditMixin:
    """
    Maps to reference ERD BaseModel:
    TenantId, CreatedAt, CreatedBy, UpdatedAt, UpdatedBy, DeletedAt, DeletedBy, IsActive, IsDeleted
    """

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
