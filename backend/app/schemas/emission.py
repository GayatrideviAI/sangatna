"""
schemas/emission.py
-------------------
Pydantic schemas for emission records and summary responses.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EmissionRecordResponse(BaseModel):
    id:              UUID
    company_id:      UUID
    facility_id:     UUID
    source_type:     str
    scope:           str
    activity_data:   float
    activity_unit:   str
    emission_factor: float
    ef_source:       Optional[str]
    ef_unit:         Optional[str]
    co2e_kg:         float
    co2e_tonnes:     float
    period_start:    datetime
    period_end:      datetime
    calculated_at:   datetime
    notes:           Optional[str]

    model_config = {"from_attributes": True}


class EmissionRecordListResponse(BaseModel):
    items:     list[EmissionRecordResponse]
    total:     int
    page:      int
    page_size: int
    pages:     int


class FacilityEmissionSummary(BaseModel):
    """Scope 1 + 2 breakdown for one facility."""
    facility_id:          UUID
    facility_name:        str
    state:                str
    scope1_co2e_tonnes:   float
    scope2_co2e_tonnes:   float
    total_co2e_tonnes:    float
    scope1_sources:       dict   # e.g. {"DIESEL": 1.34, "LPG": 0.5}
    scope2_sources:       dict   # e.g. {"ELECTRICITY": 4.25}
    record_count:         int


class EmissionSummary(BaseModel):
    """Full company-level emission summary for a period — feeds BRSR."""
    company_id:           UUID
    financial_year:       str
    period_start:         datetime
    period_end:           datetime
    scope1_co2e_tonnes:   float
    scope2_co2e_tonnes:   float
    total_co2e_tonnes:    float
    facilities:           list[FacilityEmissionSummary]
    top_source:           Optional[str]
    intensity_per_kwh:    Optional[float]
    generated_at:         datetime