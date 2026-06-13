"""
api/v1/emissions.py
--------------------
FastAPI router for emission records and summary.

GET  /emissions/                  List raw emission records
GET  /emissions/summary           Company-level Scope 1+2 summary
GET  /emissions/{id}              Get single emission record
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_company_id, get_current_user, get_db
from app.schemas.emission import (
    EmissionRecordListResponse,
    EmissionRecordResponse,
    EmissionSummary,
)
from app.services.emission_service import EmissionService

router = APIRouter(prefix="/emissions", tags=["Emissions"])


@router.get(
    "/summary",
    response_model=EmissionSummary,
    summary="Company-level Scope 1 + 2 emission summary",
    description=(
        "Rolls up all emission records for the given period. "
        "This is the primary input for BRSR Section C reporting."
    ),
)
async def get_summary(
    period_start:   datetime,
    period_end:     datetime,
    financial_year: str      = Query(
        default="2025-26",
        description="Indian financial year e.g. 2025-26",
    ),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EmissionSummary:
    return await EmissionService.get_summary(
        db,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        financial_year=financial_year,
    )


@router.get(
    "/",
    response_model=EmissionRecordListResponse,
    summary="List raw emission records",
)
async def list_records(
    facility_id:  UUID | None     = Query(default=None),
    scope:        str | None      = Query(
        default=None,
        description="Scope 1 or Scope 2",
    ),
    period_start: datetime | None = Query(default=None),
    period_end:   datetime | None = Query(default=None),
    page:         int             = Query(default=1, ge=1),
    page_size:    int             = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EmissionRecordListResponse:
    return await EmissionService.list_records(
        db,
        company_id=company_id,
        facility_id=facility_id,
        scope=scope,
        period_start=period_start,
        period_end=period_end,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{emission_id}",
    response_model=EmissionRecordResponse,
    summary="Get a single emission record",
)
async def get_record(
    emission_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_current_company_id),
    _=Depends(get_current_user),
) -> EmissionRecordResponse:
    from sqlalchemy import select
    from app.models.emission import EmissionRecord

    result = await db.execute(
        select(EmissionRecord).where(
            EmissionRecord.id == emission_id,
            EmissionRecord.company_id == company_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission record {emission_id} not found.",
        )
    return EmissionRecordResponse(
        **{
            c.key: getattr(record, c.key)
            for c in EmissionRecord.__table__.columns
        },
        co2e_tonnes=round(float(record.co2e_kg) / 1000, 6),
    )