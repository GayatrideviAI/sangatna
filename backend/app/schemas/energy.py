"""
schemas/energy.py
-----------------
Pydantic schemas for energy activity records.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.energy import DataEntryMethod, EnergySource, EnergyUnit


class EnergyActivityCreate(BaseModel):
    """Manual data entry for energy consumption."""
    facility_id:   UUID
    energy_source: EnergySource
    quantity:      float         = Field(..., gt=0)
    unit:          EnergyUnit
    cost_inr:      Optional[float] = None
    period_start:  datetime
    period_end:    datetime
    meter_number:  Optional[str] = None
    asset_id:      Optional[str] = None
    notes:         Optional[str] = None


class EnergyActivityUpdate(BaseModel):
    quantity:     Optional[float]   = None
    unit:         Optional[EnergyUnit] = None
    cost_inr:     Optional[float]   = None
    period_start: Optional[datetime] = None
    period_end:   Optional[datetime] = None
    meter_number: Optional[str]     = None
    notes:        Optional[str]     = None


class EnergyActivityResponse(BaseModel):
    id:            UUID
    company_id:    UUID
    facility_id:   UUID
    document_id:   Optional[UUID]
    energy_source: EnergySource
    quantity:      float
    unit:          EnergyUnit
    cost_inr:      Optional[float]
    period_start:  datetime
    period_end:    datetime
    meter_number:  Optional[str]
    asset_id:      Optional[str]
    entry_method:  DataEntryMethod
    notes:         Optional[str]
    created_at:    datetime
    updated_at:    datetime

    model_config = {"from_attributes": True}


class EnergyActivityListResponse(BaseModel):
    items:     list[EnergyActivityResponse]
    total:     int
    page:      int
    page_size: int
    pages:     int


class EnergySummary(BaseModel):
    """Aggregated energy consumption for a period."""
    facility_id:         UUID
    facility_name:       str
    state:               str
    period_start:        datetime
    period_end:          datetime
    total_kwh:           float
    total_diesel_litres: float
    total_lpg_kg:        float
    total_cost_inr:      float
    record_count:        int