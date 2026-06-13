"""
models/water_quantity.py
------------------------
Tracks water withdrawal, consumption, recycled, and discharged
volumes at a facility. Used for BRSR water intensity metrics.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class WaterSource(str, enum.Enum):
    MUNICIPAL          = "MUNICIPAL"
    GROUNDWATER        = "GROUNDWATER"
    RAINWATER          = "RAINWATER"
    SURFACE_WATER      = "SURFACE_WATER"
    RECYCLED           = "RECYCLED"
    TANKER             = "TANKER"
    OTHER              = "OTHER"


class WaterCategory(str, enum.Enum):
    WITHDRAWAL   = "WITHDRAWAL"    # Water taken in
    CONSUMPTION  = "CONSUMPTION"   # Water used (not returned)
    RECYCLED     = "RECYCLED"      # Water reused internally
    DISCHARGED   = "DISCHARGED"    # Water released (treated/untreated)


class WaterQuantityRecord(Base):
    __tablename__ = "water_quantity_records"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"),
                         nullable=True)

    # What and where
    water_source   = Column(Enum(WaterSource),   nullable=False)
    water_category = Column(Enum(WaterCategory), nullable=False)
    quantity_kl    = Column(Numeric(14, 4), nullable=False)   # kilolitres

    # Cost
    cost_inr       = Column(Numeric(14, 2), nullable=True)

    # Period
    period_start   = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end     = Column(DateTime(timezone=True), nullable=False)

    # Meter reference
    meter_number   = Column(String(100), nullable=True)

    # Provenance
    entry_method   = Column(String(50), nullable=False, default="MANUAL")
    notes          = Column(Text, nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    facility = relationship("Facility")
    document = relationship("Document")

    def __repr__(self):
        return f"<WaterQuantity {self.water_category} {self.quantity_kl} kL>"
