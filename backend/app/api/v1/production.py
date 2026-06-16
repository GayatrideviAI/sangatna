"""
api/v1/production.py
---------------------
FastAPI router for production records and intelligence modules.

POST   /production/                     Add monthly production record
GET    /production/                     List records
GET    /production/summary              Annual summary for a facility
PATCH  /production/{id}                 Update record
DELETE /production/{id}                 Delete record
GET    /production/intensity            Calculate energy + water intensity
POST   /production/estimate-gaps        Fill missing periods with estimates
GET    /production/brsr-readiness       BRSR data readiness check
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_company_id, get_current_user, get_db
from app.schemas.production import (
    ProductionRecordCreate,
    ProductionRecordResponse,
    ProductionRecordUpdate,
    ProductionSummary,
)
from app.services.intelligence.brsr_readiness import BRSRReadinessChecker
from app.services.intelligence.gap_estimator import GapEstimator
from app.services.intelligence.intensity_calculator import IntensityCalculator
from app.services.production_service import ProductionService

router = APIRouter(prefix="/production", tags=["Production & Intelligence"])


# ---------------------------------------------------------------------------
# Production CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ProductionRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add monthly production output for a facility",
)
async def create_record(
    payload: ProductionRecordCreate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    current_user=Depends(get_current_user),
) -> ProductionRecordResponse:
    return await ProductionService.create_record(
        db, company_id, current_user.id, payload
    )


@router.get(
    "/",
    response_model=list[ProductionRecordResponse],
    summary="List production records",
)
async def list_records(
    facility_id: UUID | None = Query(default=None),
    year:        str | None  = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> list[ProductionRecordResponse]:
    return await ProductionService.list_records(
        db, company_id,
        facility_id=facility_id,
        year=year,
    )


@router.get(
    "/summary",
    response_model=ProductionSummary,
    summary="Annual production summary for a facility",
)
async def get_summary(
    facility_id:    UUID,
    financial_year: str = Query(default="2025-26"),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> ProductionSummary:
    try:
        return await ProductionService.get_summary(
            db, company_id, facility_id, financial_year
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/{record_id}",
    response_model=ProductionRecordResponse,
    summary="Update a production record",
)
async def update_record(
    record_id: UUID,
    payload:   ProductionRecordUpdate,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> ProductionRecordResponse:
    record = await ProductionService.update_record(
        db, record_id, company_id, payload
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a production record",
)
async def delete_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> None:
    deleted = await ProductionService.delete_record(db, record_id, company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found.")


# ---------------------------------------------------------------------------
# Intelligence endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/intensity",
    summary="Calculate energy and water intensity ratios",
    description=(
        "Calculates kWh per production unit and KL per production unit "
        "from actual bills. Used by gap estimator."
    ),
)
async def get_intensity(
    facility_id:    UUID,
    financial_year: str = Query(default="2025-26"),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> dict:
    calc = IntensityCalculator(db)
    energy = await calc.calculate_energy_intensity(
        company_id, facility_id, financial_year
    )
    water  = await calc.calculate_water_intensity(
        company_id, facility_id, financial_year
    )
    return {
        "facility_id":    str(facility_id),
        "financial_year": financial_year,
        "energy_intensity": energy,
        "water_intensity":  water,
    }


@router.post(
    "/estimate-gaps",
    summary="Fill missing billing periods with production-based estimates",
    description=(
        "Uses production intensity ratios to estimate missing months. "
        "Creates ESTIMATED energy and water records flagged clearly in BRSR."
    ),
)
async def estimate_gaps(
    facility_id:    UUID,
    financial_year: str = Query(default="2025-26"),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    current_user=Depends(get_current_user),
) -> dict:
    estimator = GapEstimator(db)
    return await estimator.estimate_missing_periods(
        company_id, facility_id, financial_year,
        user_id=current_user.id,
    )


@router.get(
    "/brsr-readiness",
    summary="Check BRSR data readiness for a financial year",
    description=(
        "Shows actual vs estimated vs missing months per facility. "
        "Run this before generating the BRSR report."
    ),
)
async def brsr_readiness(
    financial_year: str = Query(default="2025-26"),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> dict:
    checker = BRSRReadinessChecker(db)
    return await checker.check(company_id, financial_year)