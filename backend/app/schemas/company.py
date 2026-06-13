"""
schemas/company.py
------------------
Pydantic v2 schemas for Company request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CompanyCreate(BaseModel):
    """Used when a consultant registers a new MSME."""
    name:               str             = Field(..., min_length=2, max_length=255)
    legal_name:         Optional[str]   = None
    cin:                Optional[str]   = Field(None, max_length=21)
    gstin:              Optional[str]   = Field(None, max_length=15)
    pan:                Optional[str]   = Field(None, max_length=10)
    industry:           Optional[str]   = None
    msme_category:      Optional[str]   = Field(None, pattern="^(Micro|Small|Medium)$")
    employee_count:     Optional[str]   = None
    address:            Optional[str]   = None
    city:               Optional[str]   = None
    state:              Optional[str]   = None
    pincode:            Optional[str]   = Field(None, pattern="^[0-9]{6}$")
    country:            str             = "India"
    website:            Optional[str]   = None
    contact_email:      Optional[EmailStr] = None
    contact_phone:      Optional[str]   = None
    financial_year_end: str             = "03-31"
    reporting_currency: str             = "INR"


class CompanyUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    name:               Optional[str]      = None
    legal_name:         Optional[str]      = None
    cin:                Optional[str]      = None
    gstin:              Optional[str]      = None
    pan:                Optional[str]      = None
    industry:           Optional[str]      = None
    msme_category:      Optional[str]      = None
    employee_count:     Optional[str]      = None
    address:            Optional[str]      = None
    city:               Optional[str]      = None
    state:              Optional[str]      = None
    pincode:            Optional[str]      = None
    website:            Optional[str]      = None
    contact_email:      Optional[EmailStr] = None
    contact_phone:      Optional[str]      = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CompanyResponse(BaseModel):
    """Returned after create, update, or fetch."""
    id:                 UUID
    name:               str
    legal_name:         Optional[str]
    cin:                Optional[str]
    gstin:              Optional[str]
    pan:                Optional[str]
    industry:           Optional[str]
    msme_category:      Optional[str]
    employee_count:     Optional[str]
    address:            Optional[str]
    city:               Optional[str]
    state:              Optional[str]
    pincode:            Optional[str]
    country:            str
    website:            Optional[str]
    contact_email:      Optional[str]
    contact_phone:      Optional[str]
    financial_year_end: str
    reporting_currency: str
    created_at:         datetime
    updated_at:         datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """Paginated list of companies."""
    items:     list[CompanyResponse]
    total:     int
    page:      int
    page_size: int
    pages:     int