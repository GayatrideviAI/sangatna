"""
models/report.py
----------------
Generated ESG reports — BRSR, Investor, CSR, Water Quality, Carbon Summary.
Status moves: PENDING → PROCESSING → READY → FAILED
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ReportType(str, enum.Enum):
    BRSR            = "BRSR"
    INVESTOR_ESG    = "INVESTOR_ESG"
    CSR_FUNDING     = "CSR_FUNDING"
    WATER_QUALITY   = "WATER_QUALITY"
    CARBON_SUMMARY  = "CARBON_SUMMARY"


class ReportStatus(str, enum.Enum):
    PENDING     = "PENDING"
    PROCESSING  = "PROCESSING"
    READY       = "READY"
    FAILED      = "FAILED"


class ReportFormat(str, enum.Enum):
    PDF     = "PDF"
    EXCEL   = "EXCEL"
    JSON    = "JSON"


class Report(Base):
    __tablename__ = "reports"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    report_type   = Column(Enum(ReportType),   nullable=False)
    report_format = Column(Enum(ReportFormat), nullable=False, default=ReportFormat.PDF)
    status        = Column(Enum(ReportStatus), nullable=False,
                           default=ReportStatus.PENDING, index=True)

    period_start   = Column(DateTime(timezone=True), nullable=False)
    period_end     = Column(DateTime(timezone=True), nullable=False)
    financial_year = Column(String(9), nullable=True)

    file_url          = Column(Text,    nullable=True)
    file_size_bytes   = Column(Integer, nullable=True)
    page_count        = Column(Integer, nullable=True)
    celery_task_id    = Column(String(255), nullable=True)
    error_message     = Column(Text,    nullable=True)
    generation_seconds= Column(Integer, nullable=True)

    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(),
                          onupdate=func.now(), nullable=False)

    company          = relationship("Company", back_populates="reports")
    requested_by_user= relationship("User")
    