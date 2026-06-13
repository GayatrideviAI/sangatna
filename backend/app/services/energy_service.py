"""
services/energy_service.py
---------------------------
Business logic for energy activity records.
Handles manual entry, listing, summary aggregation,
and triggering Scope 1/2 calculations.
"""

import math
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import EnergyActivity, EnergySource, EnergyUnit
from app.models.facility import Facility
from app.schemas.energy import (
    EnergyActivityCreate,
    EnergyActivityListResponse,
    EnergyActivityResponse,
    EnergyActivityUpdate,
    EnergySummary,
)


class EnergyService:

    # ------------------------------------------------------------------
    # Create — manual entry
    # ------------------------------------------------------------------

    @staticmethod
    async def create_activity(
        db: AsyncSession,
        company_id: UUID,
        user_id: UUID,
        payload: EnergyActivityCreate,
    ) -> EnergyActivityResponse:
        """
        Create a manual energy activity record and
        immediately trigger CO2e calculation.
        """
        from app.models.energy import DataEntryMethod

        activity = EnergyActivity(
            company_id=company_id,
            facility_id=payload.facility_id,
            energy_source=payload.energy_source,
            quantity=payload.quantity,
            unit=payload.unit,
            cost_inr=payload.cost_inr,
            period_start=payload.period_start,
            period_end=payload.period_end,
            meter_number=payload.meter_number,
            asset_id=payload.asset_id,
            entry_method=DataEntryMethod.MANUAL,
            notes=payload.notes,
            created_by=user_id,
        )
        db.add(activity)
        await db.flush()

        # Auto-calculate emissions for this activity
        await EnergyService._calculate_emissions(db, activity, company_id)

        await db.commit()
        await db.refresh(activity)
        return EnergyActivityResponse.model_validate(activity)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_activity(
        db: AsyncSession,
        activity_id: UUID,
        company_id: UUID,
    ) -> EnergyActivity | None:
        result = await db.execute(
            select(EnergyActivity).where(
                EnergyActivity.id == activity_id,
                EnergyActivity.company_id == company_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_activities(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID | None = None,
        energy_source: EnergySource | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> EnergyActivityListResponse:

        query = select(EnergyActivity).where(
            EnergyActivity.company_id == company_id
        )
        count_query = select(func.count()).select_from(EnergyActivity).where(
            EnergyActivity.company_id == company_id
        )

        if facility_id:
            query = query.where(EnergyActivity.facility_id == facility_id)
            count_query = count_query.where(
                EnergyActivity.facility_id == facility_id
            )
        if energy_source:
            query = query.where(EnergyActivity.energy_source == energy_source)
            count_query = count_query.where(
                EnergyActivity.energy_source == energy_source
            )
        if period_start:
            query = query.where(EnergyActivity.period_start >= period_start)
            count_query = count_query.where(
                EnergyActivity.period_start >= period_start
            )
        if period_end:
            query = query.where(EnergyActivity.period_end <= period_end)
            count_query = count_query.where(
                EnergyActivity.period_end <= period_end
            )

        total = (await db.execute(count_query)).scalar_one()
        rows = (
            await db.execute(
                query.order_by(EnergyActivity.period_start.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return EnergyActivityListResponse(
            items=[EnergyActivityResponse.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 1,
        )

    # ------------------------------------------------------------------
    # Summary — feeds BRSR and dashboard
    # ------------------------------------------------------------------

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        company_id: UUID,
        facility_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> EnergySummary:
        """
        Aggregated energy consumption for a facility and period.
        Used by the BRSR generator and dashboard.
        """
        # Load facility for name and state
        facility_result = await db.execute(
            select(Facility).where(
                Facility.id == facility_id,
                Facility.company_id == company_id,
            )
        )
        facility = facility_result.scalar_one_or_none()
        if not facility:
            raise ValueError(f"Facility {facility_id} not found.")

        rows = (
            await db.execute(
                select(EnergyActivity).where(
                    EnergyActivity.company_id == company_id,
                    EnergyActivity.facility_id == facility_id,
                    EnergyActivity.period_start >= period_start,
                    EnergyActivity.period_end <= period_end,
                )
            )
        ).scalars().all()

        total_kwh = sum(
            float(r.quantity)
            for r in rows
            if r.energy_source == EnergySource.ELECTRICITY
            and r.unit == EnergyUnit.KWH
        )
        total_diesel = sum(
            float(r.quantity)
            for r in rows
            if r.energy_source == EnergySource.DIESEL
        )
        total_lpg = sum(
            float(r.quantity)
            for r in rows
            if r.energy_source == EnergySource.LPG
        )
        total_cost = sum(
            float(r.cost_inr) for r in rows if r.cost_inr
        )

        return EnergySummary(
            facility_id=facility_id,
            facility_name=facility.name,
            state=facility.state,
            period_start=period_start,
            period_end=period_end,
            total_kwh=round(total_kwh, 2),
            total_diesel_litres=round(total_diesel, 2),
            total_lpg_kg=round(total_lpg, 2),
            total_cost_inr=round(total_cost, 2),
            record_count=len(rows),
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    async def update_activity(
        db: AsyncSession,
        activity_id: UUID,
        company_id: UUID,
        payload: EnergyActivityUpdate,
    ) -> EnergyActivityResponse | None:
        activity = await EnergyService.get_activity(db, activity_id, company_id)
        if not activity:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(activity, field, value)
        await db.commit()
        await db.refresh(activity)
        return EnergyActivityResponse.model_validate(activity)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_activity(
        db: AsyncSession,
        activity_id: UUID,
        company_id: UUID,
    ) -> bool:
        activity = await EnergyService.get_activity(db, activity_id, company_id)
        if not activity:
            return False
        await db.delete(activity)
        await db.commit()
        return True

    # ------------------------------------------------------------------
    # Internal — auto-calculate emissions after save
    # ------------------------------------------------------------------

    @staticmethod
    async def _calculate_emissions(
        db: AsyncSession,
        activity: EnergyActivity,
        company_id: UUID,
    ) -> None:
        """
        Automatically calculates and saves an EmissionRecord
        whenever a new EnergyActivity is created.
        """
        from app.models.emission import EmissionRecord
        from app.models.facility import Facility
        from app.services.calculation.emission_factors import (
            get_fuel_emission_factor,
            get_grid_emission_factor,
        )

        # Load facility for state (needed for grid EF)
        facility_result = await db.execute(
            select(Facility).where(Facility.id == activity.facility_id)
        )
        facility = facility_result.scalar_one_or_none()
        if not facility:
            return

        # Determine emission factor and scope
        if activity.energy_source == EnergySource.ELECTRICITY:
            if facility.custom_grid_ef:
                ef = float(facility.custom_grid_ef)
                ef_source = f"Custom EF — {facility.name}"
            else:
                ef, ef_source = get_grid_emission_factor(facility.state)
            ef_unit = "kg CO2e/kWh"
            scope = "Scope 2"

        elif activity.energy_source == EnergySource.SOLAR:
            # Renewable — zero emission, skip
            return

        else:
            # Scope 1 fuel
            try:
                ef, ef_unit, ef_source = get_fuel_emission_factor(
                    activity.energy_source.value
                )
                scope = "Scope 1"
            except ValueError:
                return

        co2e_kg = round(float(activity.quantity) * ef, 4)

        emission = EmissionRecord(
            company_id=company_id,
            facility_id=activity.facility_id,
            source_type=activity.energy_source.value,
            scope=scope,
            activity_id=activity.id,
            activity_table="energy_activities",
            activity_data=activity.quantity,
            activity_unit=activity.unit.value,
            emission_factor=ef,
            ef_source=ef_source,
            ef_unit=ef_unit,
            co2e_kg=co2e_kg,
            period_start=activity.period_start,
            period_end=activity.period_end,
        )
        db.add(emission)