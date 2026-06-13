"""
api/v1/water_quantity.py
------------------------
FastAPI router for water quantity records.

POST   /water/quantity/              Add a water consumption record
GET    /water/quantity/              List records with filters
GET    /water/quantity/summary       Aggregated summary for BRSR
GET    /water/quantity/{id}          Get single record
PATCH  /water/quantity/{id}          Update record
DELETE /water/quantity/{id}          Delete record
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.models.water_quantity import WaterCategory
from app.schemas.water_quantity import (
    WaterQuantityCreate,
    WaterQuantityListResponse,
    WaterQuantityResponse,
    WaterQuantityUpdate,
    WaterSummary,
)
from app.services.water_quantity_service import WaterQuantityService

router = APIRouter(prefix="/water/quantity", tags=["Water Quantity"])


@router.post(
    "/",
    response_model=WaterQuantityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a water consumption record",
    description=(
        "Record water withdrawal, consumption, recycled, or discharged "
        "volumes for a facility. Used for BRSR water intensity reporting."
    ),
)
async def create_record(
    payload: WaterQuantityCreate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    current_user=Depends(get_current_user),
) -> WaterQuantityResponse:
    return await WaterQuantityService.create_record(
        db, company_id, current_user.id, payload
    )


@router.get(
    "/summary",
    response_model=WaterSummary,
    summary="Aggregated water summary for a facility and period",
    description="Used by the BRSR generator and dashboard water KPIs.",
)
async def get_summary(
    facility_id:  UUID,
    period_start: datetime,
    period_end:   datetime,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> WaterSummary:
    try:
        return await WaterQuantityService.get_summary(
            db, company_id, facility_id, period_start, period_end
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/",
    response_model=WaterQuantityListResponse,
    summary="List water quantity records",
)
async def list_records(
    facility_id:    UUID | None          = Query(default=None),
    water_category: WaterCategory | None = Query(default=None),
    period_start:   datetime | None      = Query(default=None),
    period_end:     datetime | None      = Query(default=None),
    page:           int                  = Query(default=1, ge=1),
    page_size:      int                  = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> WaterQuantityListResponse:
    return await WaterQuantityService.list_records(
        db,
        company_id=company_id,
        facility_id=facility_id,
        water_category=water_category,
        period_start=period_start,
        period_end=period_end,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{record_id}",
    response_model=WaterQuantityResponse,
    summary="Get a single water quantity record",
)
async def get_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> WaterQuantityResponse:
    record = await WaterQuantityService.get_record(db, record_id, company_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Water record {record_id} not found.",
        )
    return WaterQuantityResponse.model_validate(record)


@router.patch(
    "/{record_id}",
    response_model=WaterQuantityResponse,
    summary="Update a water quantity record",
)
async def update_record(
    record_id: UUID,
    payload: WaterQuantityUpdate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> WaterQuantityResponse:
    record = await WaterQuantityService.update_record(
        db, record_id, company_id, payload
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Water record {record_id} not found.",
        )
    return record


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a water quantity record",
)
async def delete_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> None:
    deleted = await WaterQuantityService.delete_record(
        db, record_id, company_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Water record {record_id} not found.",
        )