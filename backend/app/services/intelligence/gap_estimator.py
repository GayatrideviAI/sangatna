"""
services/intelligence/gap_estimator.py
----------------------------------------
Module 3 — Fills missing billing periods with estimates
using production intensity ratios.

For each missing month:
  1. Check if production data exists for that month
  2. Apply intensity ratio (kWh/unit or KL/unit)
  3. Create ESTIMATED EnergyActivity + EmissionRecord
  4. Flag clearly as is_estimated=true

BRSR allows estimated data with disclosure.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import DataEntryMethod, EnergyActivity, EnergySource, EnergyUnit
from app.models.facility import Facility
from app.models.production import ProductionRecord
from app.models.utility_connection import UtilityConnection
from app.models.water_quantity import WaterCategory, WaterQuantityRecord, WaterSource
from app.services.intelligence.intensity_calculator import IntensityCalculator


class GapEstimator:

    def __init__(self, db: AsyncSession):
        self.db         = db
        self.calculator = IntensityCalculator(db)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def estimate_missing_periods(
        self,
        company_id: UUID,
        facility_id: UUID,
        financial_year: str,
        user_id: UUID,
    ) -> dict:
        """
        Finds all missing billing periods and fills them with estimates.
        Returns a summary of what was estimated.
        """
        from app.utils.financial_year import fy_to_dates
        period_start, period_end = fy_to_dates(financial_year)

        # Calculate intensity ratios from actual data
        energy_intensity = await self.calculator.calculate_energy_intensity(
            company_id, facility_id, financial_year
        )
        water_intensity = await self.calculator.calculate_water_intensity(
            company_id, facility_id, financial_year
        )

        if energy_intensity.get("kwh_per_unit") is None:
            return {
                "status":  "INSUFFICIENT_DATA",
                "message": (
                    "Cannot estimate missing periods — no production data found. "
                    "Please add monthly production records first."
                ),
                "estimated_energy": 0,
                "estimated_water":  0,
            }

        # Find missing billing periods
        missing_periods = await self._find_missing_periods(
            company_id, facility_id, period_start, period_end
        )

        estimated_energy = 0
        estimated_water  = 0
        details          = []

        for period in missing_periods:
            # Get production for this period
            prod = await self._get_production_for_period(
                company_id, facility_id,
                period["year"], period["month"],
            )

            if not prod:
                details.append({
                    "period":  period["label"],
                    "status":  "SKIPPED",
                    "reason":  "No production data for this month",
                })
                continue

            # Estimate electricity
            if energy_intensity.get("kwh_per_unit"):
                kwh = round(
                    float(prod.quantity) * energy_intensity["kwh_per_unit"], 2
                )
                await self._create_estimated_energy(
                    company_id, facility_id, user_id,
                    period, kwh, prod,
                )
                estimated_energy += 1

            # Estimate water
            if water_intensity.get("kl_per_unit"):
                kl = round(
                    float(prod.quantity) * water_intensity["kl_per_unit"], 4
                )
                await self._create_estimated_water(
                    company_id, facility_id, user_id,
                    period, kl, prod,
                )
                estimated_water += 1

            details.append({
                "period":         period["label"],
                "status":         "ESTIMATED",
                "production":     float(prod.quantity),
                "unit":           prod.unit,
                "estimated_kwh":  round(
                    float(prod.quantity) * (energy_intensity.get("kwh_per_unit") or 0), 2
                ),
                "estimated_kl":   round(
                    float(prod.quantity) * (water_intensity.get("kl_per_unit") or 0), 4
                ) if water_intensity.get("kl_per_unit") else None,
            })

        await self.db.commit()

        return {
            "status":            "COMPLETE",
            "financial_year":    financial_year,
            "missing_periods":   len(missing_periods),
            "estimated_energy":  estimated_energy,
            "estimated_water":   estimated_water,
            "energy_intensity":  energy_intensity,
            "water_intensity":   water_intensity,
            "details":           details,
            "message": (
                f"Estimated {estimated_energy} missing energy periods and "
                f"{estimated_water} water periods using production intensity ratios. "
                f"These will be flagged as ESTIMATED in the BRSR report."
            ),
        }

    # ------------------------------------------------------------------
    # Find missing billing periods
    # ------------------------------------------------------------------

    async def _find_missing_periods(
        self,
        company_id: UUID,
        facility_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict]:
        """Returns list of months with no energy activity data."""
        existing = (
            await self.db.execute(
                select(EnergyActivity).where(
                    EnergyActivity.company_id  == company_id,
                    EnergyActivity.facility_id == facility_id,
                    EnergyActivity.energy_source == EnergySource.ELECTRICITY,
                    EnergyActivity.period_start >= period_start,
                    EnergyActivity.period_end   <= period_end,
                )
            )
        ).scalars().all()

        # Build set of months that have data
        covered = set()
        for r in existing:
            covered.add(
                f"{r.period_start.year}-{str(r.period_start.month).zfill(2)}"
            )

        # All FY months
        missing = []
        start_year = period_start.year
        end_year   = period_end.year

        for year, month in [
            (start_year, 4),  (start_year, 5),  (start_year, 6),
            (start_year, 7),  (start_year, 8),  (start_year, 9),
            (start_year, 10), (start_year, 11), (start_year, 12),
            (end_year,   1),  (end_year,   2),  (end_year,   3),
        ]:
            label = f"{year}-{str(month).zfill(2)}"
            if label not in covered:
                missing.append({
                    "year":  str(year),
                    "month": str(month).zfill(2),
                    "label": label,
                })

        return missing

    # ------------------------------------------------------------------
    # Get production for a specific month
    # ------------------------------------------------------------------

    async def _get_production_for_period(
        self,
        company_id: UUID,
        facility_id: UUID,
        year: str,
        month: str,
    ) -> ProductionRecord | None:
        result = await self.db.execute(
            select(ProductionRecord).where(
                ProductionRecord.company_id  == company_id,
                ProductionRecord.facility_id == facility_id,
                ProductionRecord.year  == year,
                ProductionRecord.month == month,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Create estimated energy activity
    # ------------------------------------------------------------------

    async def _create_estimated_energy(
        self,
        company_id: UUID,
        facility_id: UUID,
        user_id: UUID,
        period: dict,
        kwh: float,
        prod: ProductionRecord,
    ) -> None:
        from app.services.energy_service import EnergyService

        period_start = datetime(int(period["year"]), int(period["month"]), 1)
        # Last day of month
        import calendar
        last_day = calendar.monthrange(
            int(period["year"]), int(period["month"])
        )[1]
        period_end = datetime(int(period["year"]), int(period["month"]), last_day)

        activity = EnergyActivity(
            company_id=company_id,
            facility_id=facility_id,
            energy_source=EnergySource.ELECTRICITY,
            quantity=kwh,
            unit=EnergyUnit.KWH,
            period_start=period_start,
            period_end=period_end,
            entry_method=DataEntryMethod.MANUAL,
            notes=(
                f"ESTIMATED — based on {float(prod.quantity)} {prod.unit} "
                f"production × energy intensity ratio. "
                f"Not from actual bill."
            ),
            created_by=user_id,
        )
        self.db.add(activity)
        await self.db.flush()

        # Calculate emissions for estimated record
        await EnergyService._calculate_emissions(
            self.db, activity, company_id
        )

    # ------------------------------------------------------------------
    # Create estimated water record
    # ------------------------------------------------------------------

    async def _create_estimated_water(
        self,
        company_id: UUID,
        facility_id: UUID,
        user_id: UUID,
        period: dict,
        kl: float,
        prod: ProductionRecord,
    ) -> None:
        import calendar
        period_start = datetime(int(period["year"]), int(period["month"]), 1)
        last_day     = calendar.monthrange(
            int(period["year"]), int(period["month"])
        )[1]
        period_end   = datetime(int(period["year"]), int(period["month"]), last_day)

        record = WaterQuantityRecord(
            company_id=company_id,
            facility_id=facility_id,
            water_source=WaterSource.MUNICIPAL,
            water_category=WaterCategory.WITHDRAWAL,
            quantity_kl=kl,
            period_start=period_start,
            period_end=period_end,
            entry_method="ESTIMATED",
            notes=(
                f"ESTIMATED — based on {float(prod.quantity)} {prod.unit} "
                f"production × water intensity ratio. "
                f"Not from actual bill."
            ),
            created_by=user_id,
        )
        self.db.add(record)