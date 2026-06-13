"""
models/document.py
------------------
Tracks every uploaded file — electricity bills, fuel receipts,
water bills, lab reports, Excel sheets.

Status moves: UPLOADED → PROCESSING → EXTRACTED → FAILED
"""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DocumentType(str, enum.Enum):
    ELECTRICITY_BILL     = "ELECTRICITY_BILL"
    FUEL_RECEIPT         = "FUEL_RECEIPT"
    WATER_BILL           = "WATER_BILL"
    WATER_QUALITY_REPORT = "WATER_QUALITY_REPORT"
    GENERATOR_LOG        = "GENERATOR_LOG"
    VEHICLE_LOG          = "VEHICLE_LOG"
    REFRIGERANT_LOG      = "REFRIGERANT_LOG"
    OTHER                = "OTHER"


class DocumentStatus(str, enum.Enum):
    UPLOADED    = "UPLOADED"     # File in S3, not yet processed
    PROCESSING  = "PROCESSING"   # Celery task running
    EXTRACTED   = "EXTRACTED"    # Claude extracted data successfully
    FAILED      = "FAILED"       # Extraction failed


class Document(Base):
    __tablename__ = "documents"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id  = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    facility_id = Column(UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="SET NULL"),
                         nullable=True, index=True)

    # File metadata
    document_type     = Column(Enum(DocumentType), nullable=False)
    original_filename = Column(String(255), nullable=False)
    s3_key            = Column(Text, nullable=False)
    file_size_bytes   = Column(Integer, nullable=True)
    mime_type         = Column(String(100), nullable=True)

    # Extraction
    status            = Column(Enum(DocumentStatus), nullable=False,
                                default=DocumentStatus.UPLOADED, index=True)
    celery_task_id    = Column(String(255), nullable=True)
    extracted_data    = Column(Text, nullable=True)   # raw JSON from Claude
    error_message     = Column(Text, nullable=True)
    extraction_model  = Column(String(100), nullable=True)  # e.g. claude-sonnet-4-6

    # Period the document covers
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end   = Column(DateTime(timezone=True), nullable=True)

    # Audit
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now(), nullable=False)

    # Relationships
    uploaded_by_user = relationship("User")

    def __repr__(self):
        return f"<Document {self.original_filename} ({self.status})>"
