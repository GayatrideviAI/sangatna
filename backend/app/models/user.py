"""
models/user.py
--------------
Users belong to a Company.
Roles:
  CONSULTANT  — manages multiple MSME companies
  MSME_OWNER  — sees only their own company
  ANALYST     — data entry and dashboards, no report generation
  VIEWER      — read-only access
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, enum.Enum):
    CONSULTANT = "CONSULTANT"
    MSME_OWNER = "MSME_OWNER"
    ANALYST    = "ANALYST"
    VIEWER     = "VIEWER"


class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    # Identity
    email      = Column(String(255), nullable=False, unique=True, index=True)
    full_name  = Column(String(255), nullable=False)
    phone      = Column(String(20),  nullable=True)

    # Auth
    hashed_password = Column(String(255), nullable=False)
    role            = Column(Enum(UserRole), nullable=False, default=UserRole.MSME_OWNER)
    is_active       = Column(Boolean, nullable=False, default=True)
    is_verified     = Column(Boolean, nullable=False, default=False)

    # Preferences
    language   = Column(String(10), nullable=False, default="en")  # en / ta / hi

    # Audit
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(),
                           onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="users")

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
