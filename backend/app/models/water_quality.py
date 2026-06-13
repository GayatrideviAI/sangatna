"""
models/water_quality.py
-----------------------
Two tables:
  WaterQualitySample  — one lab report = one sample event
  WaterQualityReading — one row per parameter per sample
                        e.g. pH=7.2, BOD=12 mg/L, Lead=0.02 mg/L

Compliance status is evaluated against WHO, BIS, CPCB, EPA
limits stored in reference_data/compliance_standards/.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class WaterType(str, enum.Enum):
    DRINKING        = "DRINKING"
    PROCESS         = "PROCESS"
    WASTEWATER      = "WASTEWATER"
    GROUNDWATER     = "GROUNDWATER"
    SURFACE_WATER   = "SURFACE_WATER"
    TREATED_EFFLUENT= "TREATED_EFFLUENT"


class ComplianceStatus(str, enum.Enum):
    SAFE            = "SAFE"
    EXCEEDS_LIMIT   = "EXCEEDS_LIMIT"
    NO_LIMIT        = "NO_LIMIT"        # parameter has no standard limit
    NO_DATA         = "NO_DATA"         # value was estimated / missing


class WaterQualitySample(Base):
    """One lab report or sampling event."""
    __tablename__ = "water_quality_samples"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"),
                         nullable=True)

    # Sample metadata
    sample_id       = Column(String(100), nullable=True)   # lab's own sample ID
    water_type      = Column(Enum(WaterType), nullable=False)
    collection_date = Column(DateTime(timezone=True), nullable=False, index=True)
    location_desc   = Column(String(255), nullable=True)   # e.g. "Borewell inlet"
    lab_name        = Column(String(255), nullable=True)
    lab_report_ref  = Column(String(100), nullable=True)

    # Overall compliance summary (computed after readings are saved)
    overall_status  = Column(Enum(ComplianceStatus), nullable=True)
    parameters_safe = Column(Numeric(5, 0), nullable=True)
    parameters_exceeded = Column(Numeric(5, 0), nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    facility = relationship("Facility")
    readings = relationship("WaterQualityReading", back_populates="sample",
                            cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WaterQualitySample {self.sample_id} {self.collection_date.date()}>"


class WaterQualityReading(Base):
    """One parameter reading within a sample."""
    __tablename__ = "water_quality_readings"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id = Column(UUID(as_uuid=True), ForeignKey("water_quality_samples.id",
                       ondelete="CASCADE"), nullable=False, index=True)
    company_id= Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                       nullable=False, index=True)

    # Parameter
    parameter_name = Column(String(100), nullable=False)  # e.g. "pH", "BOD", "Lead"
    parameter_code = Column(String(50),  nullable=True)   # e.g. "PB", "DO"
    category       = Column(String(50),  nullable=True)   # Physical/Chemical/Biological

    # Measured value
    measured_value = Column(Numeric(14, 6), nullable=True)
    unit           = Column(String(30),     nullable=True)   # mg/L, NTU, CFU/100mL
    is_estimated   = Column(String(5),      nullable=False, default="false")

    # Compliance evaluation
    who_limit      = Column(Numeric(14, 6), nullable=True)
    bis_limit      = Column(Numeric(14, 6), nullable=True)
    cpcb_limit     = Column(Numeric(14, 6), nullable=True)
    epa_limit      = Column(Numeric(14, 6), nullable=True)
    compliance_status = Column(Enum(ComplianceStatus), nullable=True)
    compliance_notes  = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    sample = relationship("WaterQualitySample", back_populates="readings")

    def __repr__(self):
        return f"<WaterQualityReading {self.parameter_name}={self.measured_value}{self.unit}>"
