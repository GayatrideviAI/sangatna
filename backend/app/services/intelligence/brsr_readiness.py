"""
services/intelligence/brsr_readiness.py
-----------------------------------------
Module 4 — BRSR data readiness assessment.

Before generating a BRSR report, this module checks:
  - How many months have ACTUAL data
  - How many months have ESTIMATED data
  - How many months have NO data
  - Overall confidence score
  - What's missing and what action to take

Returns a readiness report the consultant sees
before triggering BRSR generation.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.energy import EnergyActivity, EnergySource
from app.models.facility import Facility
from app.models.production import ProductionRecord
from app.models.utility_connection import UtilityConnection
from app.models.water_quality import WaterQualitySample
from app.models.water_quantity import WaterCategory, WaterQuantityRecord
from app.utils.financial_year import fy_label, fy_to_dates


class BRSRReadinessChecker:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check(
        self,
        company_id: UUID,
        financial_year: str,
    ) -> dict:
        """
        Full BRSR readiness assessment for a company and financial year.
        """
        period_start, period_end = fy_to_dates(financial_year)

        # Load company
        company_result = await self.db.execute(
            select(Company).where(Company.id == company_id)
        )
        company = company_result.scalar_one_or_none()

        # Load all facilities
        facilities_result = await self.db.execute(
            select(Facility).where(Facility.company_id == company_id)
        )
        facilities = facilities_result.scalars().all()

        facility_reports = []
        total_score      = 0.0

        for facility in facilities:
            report = await self._check_facility(
                company_id, facility, financial_year,
                period_start, period_end,
            )
            facility_reports.append(report)
            total_score += report["readiness_score"]

        overall_score = round(
            total_score / len(facilities) if facilities else 0, 1
        )

        # Determine overall status
        if overall_score >= 90:
            status  = "READY"
            message = (
                f"Data is complete for {fy_label(financial_year)}. "
                f"Ready to generate BRSR report."
            )
        elif overall_score >= 60:
            status  = "PARTIAL"
            message = (
                f"Some data is missing for {fy_label(financial_year)}. "
                f"You can generate a BRSR with estimated values, "
                f"or upload missing bills first."
            )
        else:
            status  = "INSUFFICIENT"
            message = (
                f"Insufficient data for {fy_label(financial_year)}. "
                f"Please upload more bills or add production data "
                f"to enable estimation."
            )

        return {
            "company_id":      str(company_id),
            "company_name":    company.name if company else "",
            "financial_year":  financial_year,
            "period_label":    fy_label(financial_year),
            "overall_status":  status,
            "overall_score":   overall_score,
            "message":         message,
            "facilities":      facility_reports,
            "can_generate_brsr": overall_score >= 60,
            "actions_needed":  _collect_actions(facility_reports),
        }

    # ------------------------------------------------------------------
    # Per-facility readiness check
    # ------------------------------------------------------------------

    async def _check_facility(
        self,
        company_id: UUID,
        facility: Facility,
        financial_year: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict:
        fid = facility.id

        # Energy — actual vs estimated vs missing
        energy_rows = (
            await self.db.execute(
                select(EnergyActivity).where(
                    EnergyActivity.company_id  == company_id,
                    EnergyActivity.facility_id == fid,
                    EnergyActivity.energy_source == EnergySource.ELECTRICITY,
                    EnergyActivity.period_start >= period_start,
                    EnergyActivity.period_end   <= period_end,
                )
            )
        ).scalars().all()

        actual_energy    = [r for r in energy_rows
                            if "ESTIMATED" not in (r.notes or "")]
        estimated_energy = [r for r in energy_rows
                            if "ESTIMATED" in (r.notes or "")]
        missing_energy   = 12 - len(energy_rows)

        # Water quantity
        water_rows = (
            await self.db.execute(
                select(WaterQuantityRecord).where(
                    WaterQuantityRecord.company_id  == company_id,
                    WaterQuantityRecord.facility_id == fid,
                    WaterQuantityRecord.water_category == WaterCategory.WITHDRAWAL,
                    WaterQuantityRecord.period_start >= period_start,
                    WaterQuantityRecord.period_end   <= period_end,
                )
            )
        ).scalars().all()

        actual_water    = [r for r in water_rows
                           if r.entry_method != "ESTIMATED"]
        estimated_water = [r for r in water_rows
                           if r.entry_method == "ESTIMATED"]

        # Water quality samples
        wq_result = await self.db.execute(
            select(WaterQualitySample).where(
                WaterQualitySample.company_id  == company_id,
                WaterQualitySample.facility_id == fid,
            )
        )
        wq_samples = wq_result.scalars().all()

        # Production data
        prod_result = await self.db.execute(
            select(ProductionRecord).where(
                ProductionRecord.company_id  == company_id,
                ProductionRecord.facility_id == fid,
            )
        )
        prod_rows = prod_result.scalars().all()
        start_year = period_start.year
        end_year   = period_end.year
        fy_prod    = [
            r for r in prod_rows
            if (int(r.year) == start_year and int(r.month) >= 4)
            or (int(r.year) == end_year   and int(r.month) <= 3)
        ]

        # Utility connections
        conn_result = await self.db.execute(
            select(UtilityConnection).where(
                UtilityConnection.company_id  == company_id,
                UtilityConnection.facility_id == fid,
            )
        )
        connections = conn_result.scalars().all()

        # Score calculation
        # Energy:     40 points (actual=4pts, estimated=2pts per month, max 12)
        # Water qty:  20 points
        # Water qual: 15 points
        # Production: 15 points
        # Utility:    10 points
        energy_score = min(40, (
            len(actual_energy) * 4 +
            len(estimated_energy) * 2
        ))
        water_score  = min(20, len(actual_water) * 2 +
                           len(estimated_water) * 1)
        wq_score     = 15 if wq_samples else 0
        prod_score   = min(15, len(fy_prod) * 1.5)
        util_score   = 10 if connections else 0

        readiness_score = round(
            energy_score + water_score + wq_score + prod_score + util_score, 1
        )

        # Actions needed
        actions = []
        if missing_energy > 0 and not fy_prod:
            actions.append(
                f"Upload {missing_energy} missing electricity bill(s) "
                f"OR add production data to enable estimation"
            )
        elif missing_energy > 0 and fy_prod:
            actions.append(
                f"{missing_energy} electricity months can be estimated "
                f"— run gap estimator"
            )
        if not water_rows:
            actions.append("No water data — upload water bills")
        if not wq_samples:
            actions.append("No water quality tests — upload lab report")
        if not fy_prod:
            actions.append(
                "No production data — add monthly production records "
                "to enable gap estimation"
            )

        return {
            "facility_id":       str(fid),
            "facility_name":     facility.name,
            "state":             facility.state,
            "readiness_score":   readiness_score,
            "energy": {
                "actual_months":    len(actual_energy),
                "estimated_months": len(estimated_energy),
                "missing_months":   max(0, missing_energy),
                "total_kwh":        round(sum(
                    float(r.quantity) for r in energy_rows
                ), 2),
            },
            "water": {
                "actual_months":    len(actual_water),
                "estimated_months": len(estimated_water),
                "total_kl":         round(sum(
                    float(r.quantity_kl) for r in water_rows
                ), 2),
            },
            "water_quality": {
                "samples":          len(wq_samples),
                "has_data":         len(wq_samples) > 0,
            },
            "production": {
                "months_with_data": len(fy_prod),
                "can_estimate":     len(fy_prod) > 0,
            },
            "utility_connections": len(connections),
            "actions_needed":      actions,
        }


def _collect_actions(facility_reports: list[dict]) -> list[str]:
    """Collects all unique actions across facilities."""
    seen    = set()
    actions = []
    for report in facility_reports:
        for action in report.get("actions_needed", []):
            if action not in seen:
                seen.add(action)
                actions.append(f"{report['facility_name']}: {action}")
    return actions