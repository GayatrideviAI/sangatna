"""
models/energy.py
----------------
Records energy consumption activity at a facility.
One row per meter reading or bill period.
Covers electricity, diesel, LPG, CNG, and other fuels.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EnergySource(str, enum.Enum):
    ELECTRICITY = "ELECTRICITY"   # Scope 2
    DIESEL      = "DIESEL"        # Scope 1
    LPG         = "LPG"           # Scope 1
    CNG         = "CNG"           # Scope 1
    FURNACE_OIL = "FURNACE_OIL"   # Scope 1
    COAL        = "COAL"          # Scope 1
    BIOMASS     = "BIOMASS"       # Scope 1
    SOLAR       = "SOLAR"         # Renewable — zero emission
    OTHER       = "OTHER"


class EnergyUnit(str, enum.Enum):
    KWH     = "kWh"
    LITRES  = "litres"
    KG      = "kg"
    MMBTU   = "MMBtu"
    GJ      = "GJ"


class DataEntryMethod(str, enum.Enum):
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"  # Claude read a bill
    MANUAL              = "MANUAL"               # User typed it in
    API_INTEGRATION     = "API_INTEGRATION"      # ERP/meter API
    CSV_UPLOAD          = "CSV_UPLOAD"           # Bulk spreadsheet


class EnergyActivity(Base):
    __tablename__ = "energy_activities"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"),
                         nullable=True)  # source document if extracted

    # What was consumed
    energy_source = Column(Enum(EnergySource), nullable=False)
    quantity      = Column(Numeric(14, 4), nullable=False)
    unit          = Column(Enum(EnergyUnit), nullable=False)

    # Cost (optional but useful for ROI reporting)
    cost_inr      = Column(Numeric(14, 2), nullable=True)

    # Period
    period_start  = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end    = Column(DateTime(timezone=True), nullable=False)
    reading_date  = Column(DateTime(timezone=True), nullable=True)  # meter read date

    # Meter / asset reference
    meter_number  = Column(String(100), nullable=True)
    asset_id      = Column(String(100), nullable=True)

    # Provenance
    entry_method  = Column(Enum(DataEntryMethod), nullable=False,
                            default=DataEntryMethod.MANUAL)
    notes         = Column(Text, nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    facility = relationship("Facility")
    document = relationship("Document")

    def __repr__(self):
        return f"<EnergyActivity {self.energy_source} {self.quantity}{self.unit}>"
