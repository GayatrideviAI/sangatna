"""
models/company.py
-----------------
Company is the top-level tenant in SANGATNA.
Every MSME onboarded is a Company record.
A Consultant manages one or more Companies.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic identity
    name          = Column(String(255), nullable=False)
    legal_name    = Column(String(255), nullable=True)
    cin           = Column(String(21),  nullable=True, unique=True)  # MCA company number
    gstin         = Column(String(15),  nullable=True, unique=True)
    pan           = Column(String(10),  nullable=True, unique=True)

    # Classification
    industry      = Column(String(100), nullable=True)  # e.g. Textiles, Food Processing
    msme_category = Column(String(20),  nullable=True)  # Micro / Small / Medium
    employee_count= Column(String(20),  nullable=True)  # e.g. "50-100"

    # Location
    address       = Column(Text,        nullable=True)
    city          = Column(String(100), nullable=True)
    state         = Column(String(100), nullable=True)
    pincode       = Column(String(6),   nullable=True)
    country       = Column(String(100), nullable=False, default="India")

    # Contact
    website       = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20),  nullable=True)

    # Reporting
    financial_year_end = Column(String(5), nullable=False, default="03-31")  # MM-DD
    reporting_currency = Column(String(3), nullable=False, default="INR")

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)

    # Relationships (add as other models are created)
    users      = relationship("User",     back_populates="company", cascade="all, delete-orphan")
    facilities = relationship("Facility", back_populates="company", cascade="all, delete-orphan")
    reports    = relationship("Report",   back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Company {self.name} ({self.id})>"



class ConsultantClient(Base):
    """
    Links a CONSULTANT user to the MSME companies they manage.
    A consultant can manage many companies.
    A company can have many consultants.
    """
    __tablename__ = "consultant_clients"
    __table_args__ = (
        UniqueConstraint("consultant_id", "client_company_id",
                         name="uq_consultant_client"),
    )

    id                = Column(UUID(as_uuid=True), primary_key=True,
                               default=uuid.uuid4)
    consultant_id     = Column(UUID(as_uuid=True),
                               ForeignKey("users.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    client_company_id = Column(UUID(as_uuid=True),
                               ForeignKey("companies.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    created_at        = Column(DateTime(timezone=True),
                               server_default=func.now(), nullable=False)

    consultant = relationship("User",    foreign_keys=[consultant_id])
    client     = relationship("Company", foreign_keys=[client_company_id])