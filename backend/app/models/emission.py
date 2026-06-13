"""
models/emission.py
------------------
Stores calculated CO2e emission records.
One row per activity record after the calculation engine runs.

This table is the source of truth for all carbon reporting —
BRSR, investor reports, carbon summaries all read from here.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EmissionRecord(Base):
    __tablename__ = "emission_records"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="CASCADE"),
                         nullable=False, index=True)

    # Source activity
    source_type     = Column(String(50),  nullable=False)   # ELECTRICITY, DIESEL, LPG etc.
    scope           = Column(String(10),  nullable=False)   # Scope 1 / Scope 2
    activity_id     = Column(UUID(as_uuid=True), nullable=True)  # FK to energy_activities
    activity_table  = Column(String(100), nullable=True)    # "energy_activities"

    # Calculation inputs
    activity_data   = Column(Numeric(14, 4), nullable=False)  # e.g. 1000 litres
    activity_unit   = Column(String(20),     nullable=False)  # e.g. litres
    emission_factor = Column(Numeric(10, 6), nullable=False)  # e.g. 2.68 kg CO2e/litre
    ef_source       = Column(String(100),    nullable=True)   # e.g. "IPCC AR6"
    ef_unit         = Column(String(50),     nullable=True)   # e.g. "kg CO2e/litre"

    # Result
    co2e_kg         = Column(Numeric(14, 4), nullable=False)  # activity × EF

    # GHG breakdown (optional — populated when available)
    co2_kg          = Column(Numeric(14, 4), nullable=True)
    ch4_kg          = Column(Numeric(14, 4), nullable=True)
    n2o_kg          = Column(Numeric(14, 4), nullable=True)

    # Period
    period_start    = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end      = Column(DateTime(timezone=True), nullable=False)

    # Audit
    calculated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes         = Column(Text, nullable=True)

    # Relationships
    facility = relationship("Facility")

    def __repr__(self):
        return f"<EmissionRecord {self.scope} {self.source_type} {self.co2e_kg}kg CO2e>"
