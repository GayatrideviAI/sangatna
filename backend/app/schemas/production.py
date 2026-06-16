"""
schemas/production.py
----------------------
Pydantic schemas for production records.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProductionRecordCreate(BaseModel):
    facility_id:  UUID
    year:         str  = Field(..., pattern=r"^\d{4}$")
    month:        str  = Field(..., pattern=r"^(0[1-9]|1[0-2])$")
    quantity:     float = Field(..., gt=0)
    unit:         str
    product:      Optional[str] = None
    is_estimated: bool = False
    notes:        Optional[str] = None


class ProductionRecordUpdate(BaseModel):
    quantity:     Optional[float] = None
    unit:         Optional[str]   = None
    product:      Optional[str]   = None
    is_estimated: Optional[bool]  = None
    notes:        Optional[str]   = None


class ProductionRecordResponse(BaseModel):
    id:           UUID
    company_id:   UUID
    facility_id:  UUID
    year:         str
    month:        str
    period_label: Optional[str]
    quantity:     float
    unit:         str
    product:      Optional[str]
    is_estimated: str
    notes:        Optional[str]
    created_at:   datetime

    model_config = {"from_attributes": True}


class ProductionSummary(BaseModel):
    """Annual production summary for a facility."""
    facility_id:    UUID
    facility_name:  str
    financial_year: str
    total_quantity: float
    unit:           str
    months_with_data: int
    months_missing:   int
    monthly_data:   list[dict]