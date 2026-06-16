"""
models/production.py
---------------------
Monthly production output per facility.
Used by the intensity calculator to derive
kWh/unit and KL/unit ratios for gap estimation.

Examples:
  Textiles:       metres woven, kg of yarn
  Food processing: kg output, cases packed
  Chemicals:      litres produced, kg of product
  Engineering:    units manufactured
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProductionRecord(Base):
    __tablename__ = "production_records"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id",
                          ondelete="CASCADE"), nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id",
                          ondelete="CASCADE"), nullable=False, index=True)

    # Period — monthly
    year        = Column(String(4),  nullable=False)   # e.g. "2025"
    month       = Column(String(2),  nullable=False)   # e.g. "04" for April
    period_label= Column(String(7),  nullable=True)    # e.g. "2025-04"

    # Production output
    quantity    = Column(Numeric(14, 4), nullable=False)
    unit        = Column(String(50),     nullable=False)  # tonnes, metres, units, kg
    product     = Column(String(255),    nullable=True)   # e.g. "Yarn", "Fabric"

    # Data quality
    is_estimated = Column(String(5), nullable=False, default="false")
    notes        = Column(Text,      nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    facility = relationship("Facility")

    def __repr__(self):
        return (
            f"<ProductionRecord {self.period_label} "
            f"{self.quantity} {self.unit}>"
        )