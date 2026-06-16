"""
api/v1/brsr.py
--------------
BRSR Lite Excel report generation endpoint.

GET /brsr/readiness          Check data completeness before generating
GET /brsr/download           Generate and download BRSR Lite Excel
"""

from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_company_id, get_current_user, get_db
from app.models.company import Company
from app.models.emission import EmissionRecord
from app.models.energy import EnergyActivity, EnergySource, EnergyUnit
from app.models.facility import Facility
from app.models.water_quality import WaterQualityReading, WaterQualitySample
from app.models.water_quantity import WaterCategory, WaterQuantityRecord
from app.services.intelligence.brsr_readiness import BRSRReadinessChecker
from app.services.reporting.brsr_lite_generator import generate_brsr_lite
from app.utils.financial_year import fy_to_dates

router = APIRouter(prefix="/brsr", tags=["BRSR Report"])


@router.get(
    "/readiness",
    summary="Check BRSR data readiness",
)
async def brsr_readiness(
    financial_year: str      = Query(default="2025-26"),
    db: AsyncSession         = Depends(get_db),
    company_id: UUID         = Depends(get_active_company_id),
    _=Depends(get_current_user),
) -> dict:
    checker = BRSRReadinessChecker(db)
    return await checker.check(company_id, financial_year)


@router.get(
    "/download",
    summary="Generate and download BRSR Lite Excel report",
)
async def download_brsr(
    financial_year: str      = Query(default="2025-26"),
    db: AsyncSession         = Depends(get_db),
    company_id: UUID         = Depends(get_active_company_id),
    _=Depends(get_current_user),
):
    period_start, period_end = fy_to_dates(financial_year)

    # Load company
    company_result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = company_result.scalar_one_or_none()

    # Load facilities
    facilities_result = await db.execute(
        select(Facility).where(Facility.company_id == company_id)
    )
    facilities = facilities_result.scalars().all()
    facility_ids = [f.id for f in facilities]
    facility_map = {f.id: f for f in facilities}

    # Load energy activities
    energy_rows = (
        await db.execute(
            select(EnergyActivity).where(
                EnergyActivity.company_id.in_([company_id]),
                EnergyActivity.facility_id.in_(facility_ids),
                EnergyActivity.period_start >= period_start,
                EnergyActivity.period_end   <= period_end,
            ).order_by(EnergyActivity.period_start)
        )
    ).scalars().all()

    # Load emission records
    emission_rows = (
        await db.execute(
            select(EmissionRecord).where(
                EmissionRecord.company_id.in_([company_id]),
                EmissionRecord.facility_id.in_(facility_ids),
                EmissionRecord.period_start >= period_start,
                EmissionRecord.period_end   <= period_end,
            )
        )
    ).scalars().all()

    # Load water records
    water_rows = (
        await db.execute(
            select(WaterQuantityRecord).where(
                WaterQuantityRecord.company_id.in_([company_id]),
                WaterQuantityRecord.facility_id.in_(facility_ids),
                WaterQuantityRecord.period_start >= period_start,
                WaterQuantityRecord.period_end   <= period_end,
            ).order_by(WaterQuantityRecord.period_start)
        )
    ).scalars().all()

    # Load water quality samples
    wq_samples_result = await db.execute(
        select(WaterQualitySample).where(
            WaterQualitySample.company_id.in_([company_id]),
            WaterQualitySample.facility_id.in_(facility_ids),
        )
    )
    wq_samples = wq_samples_result.scalars().all()

    # Load water quality readings
    wq_data = []
    for sample in wq_samples:
        readings_result = await db.execute(
            select(WaterQualityReading).where(
                WaterQualityReading.sample_id == sample.id
            )
        )
        readings = readings_result.scalars().all()
        wq_data.append({
            "lab_name":        sample.lab_name,
            "collection_date": sample.collection_date.strftime("%d %b %Y")
                               if sample.collection_date else "",
            "water_type":      sample.water_type.value,
            "overall_status":  sample.overall_status.value
                               if sample.overall_status else "NO_DATA",
            "readings": [
                {
                    "parameter":     r.parameter_name,
                    "category":      r.category,
                    "measured_value": float(r.measured_value)
                                     if r.measured_value else None,
                    "unit":          r.unit,
                    "bis_limit":     float(r.bis_limit)
                                     if r.bis_limit else None,
                    "cpcb_limit":    float(r.cpcb_limit)
                                     if r.cpcb_limit else None,
                    "status":        r.compliance_status.value
                                     if r.compliance_status else "NO_DATA",
                }
                for r in readings
            ],
        })

    # Build energy monthly data
    energy_monthly = []
    for r in energy_rows:
        fac  = facility_map.get(r.facility_id)
        emit = next(
            (e for e in emission_rows if e.activity_id == r.id), None
        )
        energy_monthly.append({
            "period":        r.period_start.strftime("%Y-%m"),
            "facility_name": fac.name if fac else "",
            "source":        r.energy_source.value,
            "kwh":           float(r.quantity)
                             if r.energy_source == EnergySource.ELECTRICITY
                             else None,
            "diesel_litres": float(r.quantity)
                             if r.energy_source == EnergySource.DIESEL
                             else None,
            "co2e_tonnes":   round(float(emit.co2e_kg) / 1000, 4)
                             if emit else None,
            "is_estimated":  "ESTIMATED" in (r.notes or ""),
        })

    # Build water monthly data
    water_monthly = []
    for r in water_rows:
        fac = facility_map.get(r.facility_id)
        water_monthly.append({
            "period":        r.period_start.strftime("%Y-%m"),
            "facility_name": fac.name if fac else "",
            "source":        r.water_source.value,
            "category":      r.water_category.value,
            "quantity_kl":   float(r.quantity_kl),
            "is_estimated":  r.entry_method == "ESTIMATED",
        })

    # Aggregations
    total_kwh    = sum(
        float(r.quantity) for r in energy_rows
        if r.energy_source == EnergySource.ELECTRICITY
        and r.unit == EnergyUnit.KWH
    )
    total_diesel = sum(
        float(r.quantity) for r in energy_rows
        if r.energy_source == EnergySource.DIESEL
    )
    scope1_co2e  = sum(
        float(e.co2e_kg) / 1000 for e in emission_rows
        if e.scope == "Scope 1"
    )
    scope2_co2e  = sum(
        float(e.co2e_kg) / 1000 for e in emission_rows
        if e.scope == "Scope 2"
    )

    # Source breakdown
    sources: dict = {}
    for e in emission_rows:
        sources[e.source_type] = sources.get(e.source_type, 0) + \
                                  float(e.co2e_kg) / 1000

    # Water aggregations
    total_withdrawal  = sum(
        float(r.quantity_kl) for r in water_rows
        if r.water_category == WaterCategory.WITHDRAWAL
    )
    total_consumption = sum(
        float(r.quantity_kl) for r in water_rows
        if r.water_category == WaterCategory.CONSUMPTION
    )
    total_recycled    = sum(
        float(r.quantity_kl) for r in water_rows
        if r.water_category == WaterCategory.RECYCLED
    )
    total_discharged  = sum(
        float(r.quantity_kl) for r in water_rows
        if r.water_category == WaterCategory.DISCHARGED
    )

    # Data quality
    checker   = BRSRReadinessChecker(db)
    readiness = await checker.check(company_id, financial_year)

    actual_months    = sum(
        1 for r in energy_rows
        if "ESTIMATED" not in (r.notes or "")
    )
    estimated_months = sum(
        1 for r in energy_rows
        if "ESTIMATED" in (r.notes or "")
    )

    # Build final data dict
    report_data = {
        "company": {
            "name":           company.name if company else "",
            "industry":       company.industry if company else "",
            "city":           company.city    if company else "",
            "state":          company.state   if company else "",
            "gstin":          company.gstin   if company else "",
            "financial_year": financial_year,
        },
        "facilities": [
            {"id": str(f.id), "name": f.name,
             "state": f.state, "city": f.city}
            for f in facilities
        ],
        "energy": {
            "scope1_co2e_tonnes":  round(scope1_co2e,  4),
            "scope2_co2e_tonnes":  round(scope2_co2e,  4),
            "total_co2e_tonnes":   round(scope1_co2e + scope2_co2e, 4),
            "total_kwh":           round(total_kwh,    2),
            "total_diesel_litres": round(total_diesel, 2),
            "monthly":             energy_monthly,
        },
        "water": {
            "total_withdrawal_kl":  round(total_withdrawal,  2),
            "total_consumption_kl": round(total_consumption, 2),
            "total_recycled_kl":    round(total_recycled,    2),
            "total_discharged_kl":  round(total_discharged,  2),
            "monthly":              water_monthly,
        },
        "water_quality": wq_data,
        "emissions": {
            "scope1_co2e_tonnes": round(scope1_co2e, 4),
            "scope2_co2e_tonnes": round(scope2_co2e, 4),
            "total_co2e_tonnes":  round(scope1_co2e + scope2_co2e, 4),
            "sources":            {k: round(v, 4) for k, v in sources.items()},
        },
        "data_quality": {
            "overall_score":   readiness.get("overall_score", 0),
            "overall_status":  readiness.get("overall_status", ""),
            "actual_months":   actual_months,
            "estimated_months": estimated_months,
            "missing_months":  12 - actual_months - estimated_months,
            "facilities":      readiness.get("facilities", []),
        },
        "generated_at": datetime.now().strftime("%d %b %Y %H:%M"),
    }

    # Generate Excel
    excel_bytes = generate_brsr_lite(report_data)

    filename = (
        f"BRSR_Lite_{company.name.replace(' ', '_')}_{financial_year}.xlsx"
        if company else f"BRSR_Lite_{financial_year}.xlsx"
    )

    return StreamingResponse(
        iter([excel_bytes]),
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )