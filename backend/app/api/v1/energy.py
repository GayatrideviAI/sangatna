"""
api/v1/energy.py
----------------
FastAPI router for energy activity records.

POST   /energy/                    Manual energy data entry
GET    /energy/                    List activity records with filters
GET    /energy/summary             Aggregated summary for a period
GET    /energy/{id}                Get single record
PATCH  /energy/{id}                Update record
DELETE /energy/{id}                Delete record
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.models.energy import EnergySource
from app.schemas.energy import (
    EnergyActivityCreate,
    EnergyActivityListResponse,
    EnergyActivityResponse,
    EnergyActivityUpdate,
    EnergySummary,
)
from app.services.energy_service import EnergyService

router = APIRouter(prefix="/energy", tags=["Energy"])


@router.post(
    "/",
    response_model=EnergyActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a manual energy consumption record",
    description=(
        "Use this for manual data entry when you don't have a bill to upload. "
        "Automatically calculates and saves the CO2e emission record."
    ),
)
async def create_activity(
    payload: EnergyActivityCreate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    current_user=Depends(get_current_user),
) -> EnergyActivityResponse:
    return await EnergyService.create_activity(
        db, company_id, current_user.id, payload
    )


@router.get(
    "/summary",
    response_model=EnergySummary,
    summary="Aggregated energy summary for a facility and period",
    description="Used by the BRSR generator and dashboard KPIs.",
)
async def get_summary(
    facility_id:  UUID,
    period_start: datetime,
    period_end:   datetime,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EnergySummary:
    try:
        return await EnergyService.get_summary(
            db, company_id, facility_id, period_start, period_end
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/",
    response_model=EnergyActivityListResponse,
    summary="List energy activity records",
)
async def list_activities(
    facility_id:   UUID | None      = Query(default=None),
    energy_source: EnergySource | None = Query(default=None),
    period_start:  datetime | None  = Query(default=None),
    period_end:    datetime | None  = Query(default=None),
    page:          int              = Query(default=1, ge=1),
    page_size:     int              = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EnergyActivityListResponse:
    return await EnergyService.list_activities(
        db,
        company_id=company_id,
        facility_id=facility_id,
        energy_source=energy_source,
        period_start=period_start,
        period_end=period_end,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{activity_id}",
    response_model=EnergyActivityResponse,
    summary="Get a single energy activity record",
)
async def get_activity(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EnergyActivityResponse:
    activity = await EnergyService.get_activity(db, activity_id, company_id)
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Energy activity {activity_id} not found.",
        )
    return EnergyActivityResponse.model_validate(activity)


@router.patch(
    "/{activity_id}",
    response_model=EnergyActivityResponse,
    summary="Update an energy activity record",
)
async def update_activity(
    activity_id: UUID,
    payload: EnergyActivityUpdate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EnergyActivityResponse:
    activity = await EnergyService.update_activity(
        db, activity_id, company_id, payload
    )
    if not activity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Energy activity {activity_id} not found.",
        )
    return activity


@router.delete(
    "/{activity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an energy activity record",
)
async def delete_activity(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> None:
    deleted = await EnergyService.delete_activity(db, activity_id, company_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Energy activity {activity_id} not found.",
        )