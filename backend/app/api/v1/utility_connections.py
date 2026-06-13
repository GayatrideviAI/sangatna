"""
api/v1/utility_connections.py
------------------------------
Endpoints for viewing and managing utility connections.

GET  /utility-connections/              List all connections for company
GET  /utility-connections/gaps          Check for missing billing periods
GET  /utility-connections/{facility_id} Get connections for one facility
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_company_id, get_current_user, get_db
from app.services.utility_connection_service import UtilityConnectionService

from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/utility-connections", tags=["Utility Connections"])


@router.get(
    "/",
    summary="List all utility connections for your company",
    description=(
        "Shows all electricity, water, and gas connections "
        "auto-registered from uploaded bills."
    ),
)
async def list_connections(
    facility_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> list[dict]:
    connections = await UtilityConnectionService.list_connections(
        db, company_id, facility_id=facility_id
    )
    return [
        {
            "id":                   str(c.id),
            "facility_id":          str(c.facility_id),
            "utility_type":         c.utility_type,
            "utility_provider":     c.utility_provider,
            "consumer_number":      c.consumer_number,
            "meter_number":         c.meter_number,
            "tariff_category":      c.tariff_category,
            "supply_voltage":       c.supply_voltage,
            "sanctioned_load":      c.sanctioned_load,
            "first_bill_date":      c.first_bill_date.isoformat()
                                    if c.first_bill_date else None,
            "last_bill_date":       c.last_bill_date.isoformat()
                                    if c.last_bill_date else None,
            "billing_cycle_months": c.billing_cycle_months,
        }
        for c in connections
    ]


@router.get(
    "/gaps",
    summary="Check for missing billing periods",
    description=(
        "Before generating a BRSR report, call this endpoint to see "
        "which bills are missing for the requested period. "
        "Upload the missing bills before generating the report."
    ),
)
@router.get(
    "/gaps",
    summary="Check for missing billing periods before generating BRSR",
    description=(
        "Pass either financial_year (e.g. '2025-26') OR "
        "period_start + period_end. "
        "financial_year takes priority if both are provided."
    ),
)

async def get_coverage_gaps(
    financial_year: str | None      = Query(
        default=None,
        description="Indian FY e.g. 2025-26",
    ),
    period_start:   datetime | None = Query(default=None),
    period_end:     datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> dict:
    from app.utils.financial_year import fy_to_dates, fy_label

    # Resolve dates
    if financial_year:
        period_start, period_end = fy_to_dates(financial_year)
        label = fy_label(financial_year)
    elif period_start and period_end:
        from app.utils.financial_year import date_to_fy
        financial_year = date_to_fy(period_start)
        label = fy_label(financial_year)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either financial_year or period_start + period_end.",
        )

    gaps = await UtilityConnectionService.get_coverage_gaps(
        db, company_id, period_start, period_end
    )

    return {
        "financial_year":  financial_year,
        "period_label":    label,
        "period_start":    period_start.isoformat(),
        "period_end":      period_end.isoformat(),
        "total_gaps":      len(gaps),
        "data_complete":   len(gaps) == 0,
        "gaps":            gaps,
        "message": (
            f"All billing periods have data for {label}. Ready to generate BRSR."
            if len(gaps) == 0
            else
            f"{len(gaps)} utility connection(s) have missing bills for {label}. "
            f"Upload the missing bills before generating the BRSR report."
        ),
    }


@router.get(
    "/{facility_id}",
    summary="Get utility connections for a specific facility",
)
async def get_facility_connections(
    facility_id: UUID,
    db: AsyncSession = Depends(get_db),
    company_id: UUID = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> list[dict]:
    connections = await UtilityConnectionService.list_connections(
        db, company_id, facility_id=facility_id
    )
    return [
        {
            "id":               str(c.id),
            "utility_type":     c.utility_type,
            "utility_provider": c.utility_provider,
            "consumer_number":  c.consumer_number,
            "meter_number":     c.meter_number,
            "tariff_category":  c.tariff_category,
            "first_bill_date":  c.first_bill_date.isoformat()
                                if c.first_bill_date else None,
            "last_bill_date":   c.last_bill_date.isoformat()
                                if c.last_bill_date else None,
        }
        for c in connections
    ]