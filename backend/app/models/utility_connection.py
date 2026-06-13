"""
models/utility_connection.py
-----------------------------
Stores utility connection details per facility.
Auto-populated when the first bill is uploaded and extracted.
Used to:
  - Track which facilities have known utility connections
  - Identify missing billing periods when generating BRSR
  - Pre-fill data entry forms for future bills
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UtilityConnection(Base):
    __tablename__ = "utility_connections"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "utility_type", "consumer_number",
            name="uq_facility_utility_consumer",
        ),
    )

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id",
                          ondelete="CASCADE"), nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id",
                          ondelete="CASCADE"), nullable=False, index=True)

    # Utility details — extracted from first bill
    utility_type     = Column(String(50),  nullable=False)  # ELECTRICITY / WATER / GAS
    utility_provider = Column(String(255), nullable=True)   # TANGEDCO, BESCOM etc.
    consumer_number  = Column(String(100), nullable=True)   # account/consumer number
    meter_number     = Column(String(100), nullable=True)
    tariff_category  = Column(String(100), nullable=True)   # Industrial/Commercial/Domestic
    supply_voltage   = Column(String(20),  nullable=True)   # LT/HT
    sanctioned_load  = Column(String(50),  nullable=True)   # kW

    # Billing tracking
    first_bill_date  = Column(DateTime(timezone=True), nullable=True)
    last_bill_date   = Column(DateTime(timezone=True), nullable=True)
    last_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id",
                               ondelete="SET NULL"), nullable=True)

    # Billing cycle — helps detect missing months
    billing_cycle_months = Column(String(10), nullable=True,
                                  default="2")  # 1 = monthly, 2 = bi-monthly

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships
    facility      = relationship("Facility")
    last_document = relationship("Document", foreign_keys=[last_document_id])

    def __repr__(self):
        return (
            f"<UtilityConnection {self.utility_provider} "
            f"{self.consumer_number} — {self.utility_type}>"
        )