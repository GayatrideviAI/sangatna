"""
services/intelligence/intensity_calculator.py
----------------------------------------------
Module 2 — Calculates energy and water intensity ratios
from actual bill data and production records.

Intensity ratios:
  Energy intensity = kWh consumed / production units
  Water intensity  = KL consumed  / production units

These ratios are used by the gap estimator to fill
missing months using production data alone.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import EnergyActivity, EnergySource, EnergyUnit
from app.models.production import ProductionRecord
from app.models.water_quantity import WaterCategory, WaterQuantityRecord


class IntensityCalculator:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Energy intensity — kWh per production unit
    # ------------------------------------------------------------------

    async def calculate_energy_intensity(
        self,
        company_id: UUID,
        facility_id: UUID,
        financial_year: str,
    ) -> dict:
        """
        Calculates kWh per production unit from actual bills.

        Returns:
        {
            "kwh_per_unit":      float,
            "diesel_per_unit":   float,
            "data_points":       int,
            "unit":              str,
            "confidence":        "HIGH" / "MEDIUM" / "LOW",
            "period_label":      str,
        }
        """
        from app.utils.financial_year import fy_to_dates
        period_start, period_end = fy_to_dates(financial_year)

        # Get electricity consumption records
        energy_rows = (
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

        # Get diesel consumption records
        diesel_rows = (
            await self.db.execute(
                select(EnergyActivity).where(
                    EnergyActivity.company_id  == company_id,
                    EnergyActivity.facility_id == facility_id,
                    EnergyActivity.energy_source == EnergySource.DIESEL,
                    EnergyActivity.period_start >= period_start,
                    EnergyActivity.period_end   <= period_end,
                )
            )
        ).scalars().all()

        # Get production records for same period
        prod_rows = (
            await self.db.execute(
                select(ProductionRecord).where(
                    ProductionRecord.company_id  == company_id,
                    ProductionRecord.facility_id == facility_id,
                )
            )
        ).scalars().all()

        # Filter production to FY
        start_year = period_start.year
        end_year   = period_end.year
        fy_prod = [
            r for r in prod_rows
            if (int(r.year) == start_year and int(r.month) >= 4)
            or (int(r.year) == end_year   and int(r.month) <= 3)
        ]

        total_kwh     = sum(float(r.quantity) for r in energy_rows
                            if r.unit == EnergyUnit.KWH)
        total_diesel  = sum(float(r.quantity) for r in diesel_rows)
        total_prod    = sum(float(r.quantity) for r in fy_prod)
        prod_unit     = fy_prod[0].unit if fy_prod else "units"

        if total_prod == 0:
            return {
                "kwh_per_unit":    None,
                "diesel_per_unit": None,
                "data_points":     0,
                "unit":            prod_unit,
                "confidence":      "NONE",
                "message":         "No production data found for this period.",
            }

        kwh_per_unit    = round(total_kwh    / total_prod, 4)
        diesel_per_unit = round(total_diesel / total_prod, 4)

        # Confidence based on data points
        data_points = len(energy_rows)
        confidence  = (
            "HIGH"   if data_points >= 6 else
            "MEDIUM" if data_points >= 3 else
            "LOW"
        )

        return {
            "kwh_per_unit":    kwh_per_unit,
            "diesel_per_unit": diesel_per_unit,
            "total_kwh":       round(total_kwh, 2),
            "total_diesel":    round(total_diesel, 2),
            "total_production": round(total_prod, 2),
            "data_points":     data_points,
            "unit":            prod_unit,
            "confidence":      confidence,
            "financial_year":  financial_year,
        }

    # ------------------------------------------------------------------
    # Water intensity — KL per production unit
    # ------------------------------------------------------------------

    async def calculate_water_intensity(
        self,
        company_id: UUID,
        facility_id: UUID,
        financial_year: str,
    ) -> dict:
        """
        Calculates KL per production unit from actual water records.
        """
        from app.utils.financial_year import fy_to_dates
        period_start, period_end = fy_to_dates(financial_year)

        water_rows = (
            await self.db.execute(
                select(WaterQuantityRecord).where(
                    WaterQuantityRecord.company_id  == company_id,
                    WaterQuantityRecord.facility_id == facility_id,
                    WaterQuantityRecord.water_category == WaterCategory.WITHDRAWAL,
                    WaterQuantityRecord.period_start >= period_start,
                    WaterQuantityRecord.period_end   <= period_end,
                )
            )
        ).scalars().all()

        prod_rows = (
            await self.db.execute(
                select(ProductionRecord).where(
                    ProductionRecord.company_id  == company_id,
                    ProductionRecord.facility_id == facility_id,
                )
            )
        ).scalars().all()

        start_year = period_start.year
        end_year   = period_end.year
        fy_prod = [
            r for r in prod_rows
            if (int(r.year) == start_year and int(r.month) >= 4)
            or (int(r.year) == end_year   and int(r.month) <= 3)
        ]

        total_kl   = sum(float(r.quantity_kl) for r in water_rows)
        total_prod = sum(float(r.quantity)    for r in fy_prod)
        prod_unit  = fy_prod[0].unit if fy_prod else "units"

        if total_prod == 0:
            return {
                "kl_per_unit": None,
                "data_points": 0,
                "unit":        prod_unit,
                "confidence":  "NONE",
                "message":     "No production data found.",
            }

        kl_per_unit = round(total_kl / total_prod, 6)
        data_points = len(water_rows)
        confidence  = (
            "HIGH"   if data_points >= 6 else
            "MEDIUM" if data_points >= 3 else
            "LOW"
        )

        return {
            "kl_per_unit":      kl_per_unit,
            "total_kl":         round(total_kl, 2),
            "total_production": round(total_prod, 2),
            "data_points":      data_points,
            "unit":             prod_unit,
            "confidence":       confidence,
            "financial_year":   financial_year,
        }