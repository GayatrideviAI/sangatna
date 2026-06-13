"""
schemas/facility.py
-------------------
Pydantic schemas for Facility request/response.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.facility import FacilityType


class FacilityCreate(BaseModel):
    name:             str          = Field(..., min_length=2, max_length=255)
    facility_type:    FacilityType = FacilityType.FACTORY
    facility_code:    Optional[str] = None
    address:          Optional[str] = None
    city:             Optional[str] = None
    state:            str
    pincode:          Optional[str] = Field(None, pattern="^[0-9]{6}$")
    area_sqft:        Optional[float] = None
    production_unit:  Optional[str] = None
    custom_grid_ef:   Optional[float] = None


class FacilityUpdate(BaseModel):
    name:             Optional[str]          = None
    facility_type:    Optional[FacilityType] = None
    facility_code:    Optional[str]          = None
    address:          Optional[str]          = None
    city:             Optional[str]          = None
    state:            Optional[str]          = None
    pincode:          Optional[str]          = None
    area_sqft:        Optional[float]        = None
    production_unit:  Optional[str]          = None
    custom_grid_ef:   Optional[float]        = None


class FacilityResponse(BaseModel):
    id:               UUID
    company_id:       UUID
    name:             str
    facility_type:    FacilityType
    facility_code:    Optional[str]
    address:          Optional[str]
    city:             Optional[str]
    state:            str
    pincode:          Optional[str]
    area_sqft:        Optional[float]
    production_unit:  Optional[str]
    custom_grid_ef:   Optional[float]
    created_at:       datetime
    updated_at:       datetime

    model_config = {"from_attributes": True}


class FacilityListResponse(BaseModel):
    items:     list[FacilityResponse]
    total:     int
    page:      int
    page_size: int
    pages:     int