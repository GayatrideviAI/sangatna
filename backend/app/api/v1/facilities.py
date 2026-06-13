"""
api/v1/facilities.py
--------------------
FastAPI router for facility management.
All endpoints are scoped to the authenticated user's company.

POST   /facilities/         Add a new facility
GET    /facilities/         List all facilities
GET    /facilities/{id}     Get one facility
PATCH  /facilities/{id}     Update facility
DELETE /facilities/{id}     Delete facility
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.schemas.facility import (
    FacilityCreate,
    FacilityListResponse,
    FacilityResponse,
    FacilityUpdate,
)
from app.services.facility_service import FacilityService

router = APIRouter(prefix="/facilities", tags=["Facilities"])


@router.post(
    "/",
    response_model=FacilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new facility to your company",
)
async def create_facility(
    payload: FacilityCreate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> FacilityResponse:
    return await FacilityService.create_facility(db, company_id, payload)


@router.get(
    "/",
    response_model=FacilityListResponse,
    summary="List all facilities for your company",
)
async def list_facilities(
    page:      int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> FacilityListResponse:
    return await FacilityService.list_facilities(
        db, company_id, page=page, page_size=page_size
    )


@router.get(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Get a single facility",
)
async def get_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> FacilityResponse:
    facility = await FacilityService.get_facility(db, facility_id, company_id)
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility {facility_id} not found.",
        )
    return FacilityResponse.model_validate(facility)


@router.patch(
    "/{facility_id}",
    response_model=FacilityResponse,
    summary="Update a facility",
)
async def update_facility(
    facility_id: UUID,
    payload: FacilityUpdate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> FacilityResponse:
    facility = await FacilityService.update_facility(
        db, facility_id, company_id, payload
    )
    if not facility:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility {facility_id} not found.",
        )
    return facility


@router.delete(
    "/{facility_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a facility",
)
async def delete_facility(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> None:
    deleted = await FacilityService.delete_facility(db, facility_id, company_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility {facility_id} not found.",
        )