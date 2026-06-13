"""
models/facility.py
------------------
A Facility is a physical location belonging to a Company.
Examples: Factory in Coimbatore, Warehouse in Chennai, Office in Bangalore.

All energy readings, water readings, and emission records
are attached to a Facility, not directly to a Company.
This allows multi-site MSMEs to track each location separately.
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class FacilityType(str, enum.Enum):
    FACTORY        = "FACTORY"
    WAREHOUSE      = "WAREHOUSE"
    OFFICE         = "OFFICE"
    RETAIL         = "RETAIL"
    COLD_STORAGE   = "COLD_STORAGE"
    DATA_CENTER    = "DATA_CENTER"
    OTHER          = "OTHER"


class Facility(Base):
    __tablename__ = "facilities"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    # Identity
    name          = Column(String(255), nullable=False)
    facility_type = Column(Enum(FacilityType), nullable=False, default=FacilityType.FACTORY)
    facility_code = Column(String(50),  nullable=True)   # internal reference e.g. "PLANT-001"

    # Location
    address = Column(Text,        nullable=True)
    city    = Column(String(100), nullable=True)
    state   = Column(String(100), nullable=False)        # used for grid emission factor lookup
    pincode = Column(String(6),   nullable=True)

    # Physical details
    area_sqft        = Column(Numeric(10, 2), nullable=True)
    production_unit  = Column(String(50),     nullable=True)   # e.g. "tonnes", "units", "kg"

    # Grid emission factor override
    # If null, state-level CEA factor is used automatically
    custom_grid_ef   = Column(Numeric(6, 4), nullable=True)    # kg CO2e per kWh

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    company = relationship("Company", back_populates="facilities")

    def __repr__(self):
        return f"<Facility {self.name} — {self.state} ({self.facility_type})>"
