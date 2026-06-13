"""
schemas/document.py
-------------------
Pydantic schemas for document upload and response.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.document import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    id:                UUID
    company_id:        UUID
    facility_id:       Optional[UUID]
    document_type:     DocumentType
    original_filename: str
    file_size_bytes:   Optional[int]
    status:            DocumentStatus
    extracted_data:    Optional[str]
    error_message:     Optional[str]
    period_start:      Optional[datetime]
    period_end:        Optional[datetime]
    created_at:        datetime

    model_config = {"from_attributes": True}