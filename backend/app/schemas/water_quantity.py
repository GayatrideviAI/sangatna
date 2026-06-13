"""
schemas/water_quantity.py
--------------------------
Pydantic schemas for water quantity records.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.water_quantity import WaterCategory, WaterSource


class WaterQuantityCreate(BaseModel):
    facility_id:    UUID
    water_source:   WaterSource
    water_category: WaterCategory
    quantity_kl:    float         = Field(..., gt=0)
    cost_inr:       Optional[float] = None
    period_start:   datetime
    period_end:     datetime
    meter_number:   Optional[str] = None
    notes:          Optional[str] = None


class WaterQuantityUpdate(BaseModel):
    water_source:   Optional[WaterSource]   = None
    water_category: Optional[WaterCategory] = None
    quantity_kl:    Optional[float]         = None
    cost_inr:       Optional[float]         = None
    period_start:   Optional[datetime]      = None
    period_end:     Optional[datetime]      = None
    meter_number:   Optional[str]           = None
    notes:          Optional[str]           = None


class WaterQuantityResponse(BaseModel):
    id:             UUID
    company_id:     UUID
    facility_id:    UUID
    document_id:    Optional[UUID]
    water_source:   WaterSource
    water_category: WaterCategory
    quantity_kl:    float
    cost_inr:       Optional[float]
    period_start:   datetime
    period_end:     datetime
    meter_number:   Optional[str]
    entry_method:   str
    notes:          Optional[str]
    created_at:     datetime

    model_config = {"from_attributes": True}


class WaterQuantityListResponse(BaseModel):
    items:     list[WaterQuantityResponse]
    total:     int
    page:      int
    page_size: int
    pages:     int


class WaterSummary(BaseModel):
    """Aggregated water data for a facility and period — feeds BRSR."""
    facility_id:          UUID
    facility_name:        str
    state:                str
    period_start:         datetime
    period_end:           datetime
    total_withdrawal_kl:  float
    total_consumption_kl: float
    total_recycled_kl:    float
    total_discharged_kl:  float
    total_cost_inr:       float
    water_intensity:      Optional[float]  # kL per unit of production
    record_count:         int